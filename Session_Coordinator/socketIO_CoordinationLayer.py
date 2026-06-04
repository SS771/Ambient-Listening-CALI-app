from typing import Annotated
import asyncio, json, os, time
from uuid import uuid4
import websockets
import socketio
import uvicorn
import requests
import time
import base64
from urllib.parse import unquote
from openemr import connector
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from app import patient, transcript, encounter, medication, ai, domainterms
from app.middleware import wlc_auth
from app.middleware.wlc_auth import WlcUser, auth_middleware

# Initialize FastAPI
fastapi_app = FastAPI()

fastapi_app.include_router(wlc_auth.router)
fastapi_app.include_router(patient.router)
fastapi_app.include_router(transcript.router)
fastapi_app.include_router(encounter.router)
fastapi_app.include_router(medication.router)
fastapi_app.include_router(ai.router)
fastapi_app.include_router(domainterms.router)

fastapi_app.add_middleware( #https://fastapi.tiangolo.com/tutorial/cors/#use-corsmiddleware
    CORSMiddleware
    ,allow_origins=["*"]
    ,allow_credentials=False
    ,allow_methods=["*"]
    ,allow_headers=["*"]
)

@fastapi_app.get("/oauth2/default")
def receiveRedirect(request: Request):
    print("Redirect hit")
    current_millis = int(round(time.time() * 1000))
    query_params = request.query_params
    query_params = request.query_params
    connector.authorization_code = query_params["code"]
    print(f"Retrieving token for first time")
    openEMR_host_env = os.getenv("openemr_host", "")
    if openEMR_host_env:
        connector.openEMR_host = openEMR_host_env
    openEMR = f'{connector.openEMR_host}oauth2/default/token'
    openEMR_client_id = os.getenv("openemr_client_id", "")
    openEMR_client_secret = os.getenv("openEMR_client_secret", "")
    auth_string = openEMR_client_id + ":" + openEMR_client_secret
    auth_string_bytes = auth_string.encode('utf-8')
    base64_bytes = base64.b64encode(auth_string_bytes)
    base64_auth_string = base64_bytes.decode('ascii')
    full_auth_header = "Basic " + base64_auth_string
    # if set, use the env variable value for redirect uri
    redirect_uri_env = os.getenv("redirect_uri", "")
    if redirect_uri_env:
        connector.redirect_uri = redirect_uri_env
    data = {"grant_type": "authorization_code", "code": connector.authorization_code, "client_id": f"{openEMR_client_id}", "redirect_uri": f"{connector.redirect_uri}", "scope": "api:oemr api:fhir api:port openid fhirUser online_access offline_access patient/AllergyIntolerance.read patient/CarePlan.read patient/CareTeam.read patient/Condition.read patient/Device.read patient/DiagnosticReport.read patient/DocumentReference.read patient/Encounter.read patient/Goal.read patient/Immunization.read patient/Location.read patient/Medication.read patient/MedicationRequest.read patient/Observation.read patient/Organization.read patient/Patient.read patient/Practitioner.read patient/Procedure.read patient/Provenance.read"}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": full_auth_header}
    response = requests.post(openEMR, data=data, headers=headers)
    result = response.text
    result_data = json.loads(result)
    token = result_data["access_token"]
    # replace token so we can use it for next hour
    connector.millis_to_token["refresh_millis"] = current_millis
    connector.millis_to_token["token"] = token
    connector.refresh_token = result_data["refresh_token"]
    return token

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, fastapi_app)

def _getApikey():
    return os.environ["captioning_apikey"]

class TranslationSession:
    def __init__(
        self,
        sessionId,
        callId,
        apiKey, #api key that session will run on
        clientId, #human readable client ID for session tracking
        *args,
        **kwargs
    ):
        """
        Manages connection of client -> coordination layer (this code) -> service layer.
        """
        self.wsURI = os.environ.get("wlc_captions_host", "wss://live-captioning-wlc-staging.watsonmedia.ibm.com/speech-to-text/api/v2/recognize?model_id=fea68eb4-4a08-415a-a7d1-ec3080235fdb")
        self.authURL = os.getenv("wlc_auth_url", "https://api-wlc-staging.watsonmedia.ibm.com/authorization/api/v1/token")
        self.sessionId = sessionId
        self.callId = callId
        self.serviceConn = None
        self.serviceConn_none_since: float | None = None
        self.apiKey = apiKey
        self.headers = None
        self.timestamp = None
        self.clientId = clientId
    async def connectToServiceLayer(self, *args, **kwargs) -> bool:
        """
        open/ensure connection to service layer
        """
        token = requests.get(
            self.authURL
            ,headers={"Authorization":f"apikey {self.apiKey}"}
            ,verify=False
        ).text
        print(f"token: {token}\n")
        self.headers = {
            "X-Watson-Authorization-Token": token
            ,"x-wlc-hostname": self.clientId
        }
        self.serviceConn = await websockets.connect(self.wsURI, additional_headers=self.headers)
        await self.serviceConn.send(json.dumps(
            {
                "action":"start"
                ,"content-type":f"audio/wav;rate=16000"
            }
        ))

        try:
            connStat = await self.serviceConn.recv() #TODO - No data should be sent until listening message is received; when we do get it send back to client that they can send audio
            print("connection status:", connStat)
            await sio.emit('ok', 'ok', room = self.callId)
            return True
        except websockets.exceptions.ConnectionClosed: # might need something else here
            print("connection failed")
            return False

    async def run(self, *args, **kwargs) -> bool:
        """
        creates 2 websocket connections:
            1 for client to this code
            1 for this code to service layer
        """
        success = await asyncio.gather(
            self.connectToServiceLayer()
        )
        print(f"established connections ok call={self.callId}")
        await asyncio.gather(
            self.recvServiceLayerDataLoop()
        )

        print("end of run loop")
        return success

    async def disconnectFromServiceLayer(self): #sends a stop message & disconnects from live captioning
        await self.serviceConn.send('{"action":"stop"}')
        await self.serviceConn.close()
        self.serviceConn = None

    async def sendToServiceLayer(self, data:"dict", *args, **kwargs):
        """
        sends data to service layer connection
        """
        if not self.timestamp:
            self.timestamp = time.time()
        if self.serviceConn:
            try:
                await self.serviceConn.send(data)
            except websockets.exceptions.ConnectionClosed:
                print(f"service layer disconnected (sendToServiceLayer failed) :: call={self.callId}, session={self.sessionId}")
                # set to None to avoid sending audio again in above if, track when it was set
                self.serviceConn = None
                self.serviceConn_none_since = time.monotonic()
                # emit reconnect message
                await sio.emit("reconnecting", "begin_reconnecting", to = self.callId)
                # attempt reconnect - three times?
                print(f"Reconnecting, will attempt for 10 seconds")
                success = await asyncio.gather(self.run(), sio.save_session(self.callId, {"translator": self}))
                if success:
                    print(f"established connections ok call={self.callId}")
        else:
            print("NO SERVICE CONNECTION")
            if self.serviceConn is None:
                if self.serviceConn_none_since is None:
                    self.serviceConn_none_since = time.monotonic()
                elif time.monotonic() - self.serviceConn_none_since > 10:
                    print("FAILED reconnecting to captioning service, emitting failed message to UI")
                    await sio.emit("reconnecting", "reconnect_failed", to=self.callId)
                    return

    async def recvServiceLayerDataLoop(self, *args, **kwargs):
        """
        handler for when service layer sends data to this code
        """
        async for message in self.serviceConn:
            print("recvServiceLayerDataLoop::", message)
            if self.timestamp:
                ts = time.time()
                print("latency = ", ts - self.timestamp)
                self.timestamp = ts
                print("end of run loop")
            await sio.emit('transcript', message, room=self.callId)

@sio.on("connectCall")
async def on_connectCall(sid, data):
    jwtToken = data["token"]
    jwtData = None
    jwtData = wlc_auth._decodeJWT(jwtToken)
    if jwtData:
        roomName = f"{jwtData['x-wlc-user']}-{sid}"
        await sio.enter_room(sid, roomName)
        print("connectCall", sid)
        ts = TranslationSession(sid, roomName, _getApikey(), jwtData["x-wlc-user"])
        await asyncio.gather(ts.run(), sio.save_session(sid, {"translator": ts}))
        print("connectCall success", sid) #fyi this doesn't print until the above ts.run() is done; ie session is ended
    else:
        print("failure to connectCall for jwt=", jwtToken)
        await sio.emit("ok", "connection_failure", to = sid)


@sio.on("connect_error")
async def on_connectError(err):
    print("connect error::", err)
    await asyncio.sleep(1)

@sio.on("disconnect")
async def on_disconnect(sid, reason, *args, **kwargs):
    async with sio.session(sid) as session:
        await session["translator"].disconnectFromServiceLayer()
    print("DISCONNECT", sid, reason, *args, **kwargs)

@sio.on("audioData")
async def on_audioData(sid, data):
    session = await sio.get_session(sid)
    await session["translator"].sendToServiceLayer(data)

def main():
    uvicorn.run(app, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()#asyncio.run(main())
