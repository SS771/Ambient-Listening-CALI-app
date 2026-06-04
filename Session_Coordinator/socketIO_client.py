import argparse, asyncio
import socketio

sio = socketio.AsyncClient()
AUDIO_DATA = [] #FIXME : nasty global var
def setad(d):
    AUDIO_DATA = d
@sio.on('transcript')
async def on_transcript(data):
    print("client received", data)

@sio.on('ok')
async def on_ok(data):
    print("starting captioning")
    for audioChunk in AUDIO_DATA:
        print("sending")
        await sio.emit("audioData", audioChunk)
        await asyncio.sleep(1)
    print("done w/ ok event")

async def start(id, apiKey, audioData):
    [AUDIO_DATA.append(x) for x in audioData]
    await sio.connect('http://0.0.0.0:5000')#"https://session-coordination-wlc-dev.watsonmedia.ibm.com")
    print("CONNECTED")
    await sio.emit("connectCall", {
        "callId": id
        , "apiKey": apiKey
    })
    await sio.wait()

def readData(file):
    d = []
    stride = 2 * 16000
    with open(file, "rb") as aStream:
        data=aStream.read(stride)
        while not(data==b""):
            d.append(data) #d.append(base64.b64encode(data).decode('ascii'))
            data=aStream.read(stride)
    return d

def genArgs(parser = argparse.ArgumentParser(description = "fakes a client for the session coordinator")):
    parser.add_argument("id", help = "id of the session")
    parser.add_argument("apiKey", help = "api key")
    parser.add_argument("wav_file", help = "wav file to read")
    return parser

if __name__ == "__main__":
    args = genArgs().parse_args()
    asyncio.run(start(args.id, args.inputLang, args.outputLang, readData(args.wav_file)))
