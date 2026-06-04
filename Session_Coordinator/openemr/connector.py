import os, time, json
from datetime import datetime
from uuid import uuid4
import requests
import base64

# defaulting to what is needed for local testing
# wavelength value should be http://openemr.default.svc.cluster.local:80/
openEMR_host = os.getenv("openemr_host","http://localhost:8080/")
authorization_code = ""
refresh_token = ""
# defaulting to what is needed for local testing
# wavelength value should be https://session-cordination-wlc-atlanta.watsonmedia.ibm.com/oauth2/default
redirect_uri = os.getenv("auth_redirect_uri", "http://0.0.0.0:5000/oauth2/default")

def _requestEMR(
        openEMR_token
        , url:"'/api/endpoint' to append to openEMR_host"
        , methodName: "method of request, default GET" = "GET"
        , moreHeaders:"dict() additional headers or overwrites" = {}
        , requestParams:"additional parameters for request method" = {}
        , returnRawResponse:"don't extract/parse response if True" = False
    ):
    _reqUUID = uuid4()
    print(f"({_reqUUID})::start {methodName} request: {url}")
    global openEMR_host
    #openEMR_token = getOpenEMRToken_PasswordGrant()#getOpenEMRToken_Redirect()
    openEMR = f"{openEMR_host}apis/default{url}"
    auth_header = f"Bearer {openEMR_token}"
    headers = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": auth_header, **moreHeaders}
    response = requests.request(methodName, openEMR, headers=headers, **requestParams)
    print("RESPONSE IS", response)
    result_data = response
    if not returnRawResponse:
        result = response.text
        print("RESULT TEXT", result)
        result_data = json.loads(result)
    print(f"({_reqUUID})::stop {methodName} request: {url}")
    return result_data

# Previously had more logic to extract a full string from an array of json chunks, now transcript is just a string
def extractWordsFromTranscript(full_transcript_string, keep_sc_marks):
    fullText = full_transcript_string
    # if keep_sc_marks false, replace speaker change markers with newlines so model can better understand conversation
    # else add newlines in front of sc marks for saved transcript clarity
    if not keep_sc_marks:
        full_text_final = fullText.replace(">>", "\n")
    else:
        full_text_final = fullText.replace(">>", "\n>>")
    # add start and end bound tags, this greatly enhances the model's output
    full_text_final_bounded = "[transcript]\n" + full_text_final + "\n[end]"
    return full_text_final_bounded

def saveTranscriptToOpenEMR(token, full_session_transcript, patient_id, filename):
    transcript = extractWordsFromTranscript(full_session_transcript, True)
    return newDocumentOpenEMR(token, patient_id, transcript, filename)

# 09/24 - we're reworking this flow for demos & presales to prevent logout issues & make client responsable for token management
# now the connector expects to be passed a valid token to use & just provides a method (ie this) for the wlc_auth middleware to use to validate passed user+pass
# DEPRECATED - OpenEMR team advises against this and says the password grant option will be going away in a future release
# This auth flow works similar to the WlC auth flow, make one request and get one token that is good for an hour
def getOpenEMRToken_PasswordGrant(
        openEMR_username = os.getenv("openemr_username", "")
        , openEMR_password = os.getenv("openemr_password", "")
    ):
    print(f"password grant start -> {openEMR_username}")
    openEMR = f'{openEMR_host}oauth2/default/token'
    openEMR_client_id = os.getenv("openemr_client_id", "")
    data = {
        "grant_type": "password"
        , "client_id": f"{openEMR_client_id}"
        , "scope": "openid offline_access api:oemr api:fhir user/allergy.read user/allergy.write user/appointment.read user/appointment.write user/dental_issue.read user/dental_issue.write user/document.read user/document.write user/drug.read user/encounter.read user/encounter.write user/facility.read user/facility.write user/immunization.read user/insurance.read user/insurance.write user/insurance_company.read user/insurance_company.write user/insurance_type.read user/list.read user/medical_problem.read user/medical_problem.write user/medication.read user/medication.write user/message.write user/patient.read user/patient.write user/practitioner.read user/practitioner.write user/prescription.read user/procedure.read user/soap_note.read user/soap_note.write user/surgery.read user/surgery.write user/transaction.read user/transaction.write user/vital.read user/vital.write user/AllergyIntolerance.read user/CareTeam.read user/Condition.read user/Coverage.read user/Encounter.read user/Immunization.read user/Location.read user/Medication.read user/MedicationRequest.read user/Observation.read user/Organization.read user/Organization.write user/Patient.read user/Patient.write user/Practitioner.read user/Practitioner.write user/PractitionerRole.read user/Procedure.read"
        ,"user_role": "users"
        , "username": f"{openEMR_username}"
        , "password": f"{openEMR_password}"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(openEMR, data=data, headers=headers)
    result = response.text
    #print(f"Response: {result}")
    result_data = json.loads(result)
    token = result_data["access_token"]
    return token

def createPatient(
        token,
        fname,
        lname,
        DOB,
        sex,
        title = "",
        mname = "",
        street = "NO STREET",
        postal_code = "NO POSTAL CODE",
        city = "NO CITY",
        state = "NO STATE",
        country_code = "NO COUNTRY",
        phone_contact = "NO PHONE",
        race = "NO RACE",
        ethnicity = "NO ETHNICITY"
    ):
    reqData = {
        "title": title,
        "fname": fname,
        "mname": mname,
        "lname": lname,
        "street": street,
        "postal_code": postal_code,
        "city": city,
        "state": state,
        "country_code": country_code,
        "phone_contact": phone_contact,
        "DOB": DOB,
        "sex": sex,
        "race": race,
        "ethnicity": ethnicity
    }
    data = _requestEMR(token, "/api/patient", methodName = "POST", requestParams={"json" : reqData})
    print("createPatient response :", data)
    data = data["data"]
    #patient_id = data["uuid"]
    return data

def clean_json_string(json_string): #TODO - rm
    """Removes brackets and quotes from a JSON string, if applicable."""
    try:
        data = json.loads(json_string)
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        if isinstance(data, str):
            data = data.replace('"', '')  # Remove quotes
        return data
    except json.JSONDecodeError:
         return json_string.replace('"', '')


def createEncounter(token, patient_id):
    date = datetime.today().strftime('%Y-%m-%d %H:%M')
    data = {
                "date": date,
                "onset_date": "",
                "reason": "Visit",
                "facility": "Default",
                "pc_catid": "2",
                "facility_id": "1",
                "billing_facility": "3",
                "sensitivity": "normal",
                "referral_source": "",
                "pos_code": "0",
                "external_id": "",
                "provider_id": "1",
                "class_code": "AMB"
            }
    data = _requestEMR(token, f"/api/patient/{patient_id}/encounter", methodName = "POST", requestParams={"json" : data})
    return data


def validateVitalsRequestBody(body:str)->str|None:
    # model may return extraneous junk, isolate json first
    #json_only = isolateJSON(body) #TODO - rm
    temp_json = {}
    # make sure body is valid json
    try:
        temp_json = json.loads(body)
    except ValueError:
        return None
    expected_fields = ["bps","bpd","weight","height","temperature","temp_method","pulse","respiration","note","waist_circ","head_circ","oxygen_saturation"]
    finalJson = {}
    for k in expected_fields:
        finalJson[k] = temp_json.get(k, "")
    if all(value == "" for value in finalJson.values()):
        return None
    else:
        return json.dumps(finalJson)
    '''
    # next validate that json contains all fields even if empty
    expected_fields = ["bps","bpd","weight","height","temperature","temp_method","pulse","respiration","note","waist_circ","head_circ","oxygen_saturation"]
    if all(sub in json_only for sub in expected_fields):
        return json_only
    else:
        return None
    '''

def isolateJSON(body):
    # if model sent back json with explanatory junk surrounding it, find just the json here
    open_index = body.find('{')
    close_index = body.find('}')
    if open_index == -1 & close_index == -1:
        return "Open and close brackets not found, will fail validation"
    else:
        json_only = body[open_index:close_index+1]
        return json_only

def newDocumentOpenEMR(token, patient_id, content, filename):
    openEMR_client_id = os.getenv("openemr_client_id", "")
    # short circuit doc save flow if openemr stuff is not set up
    if not openEMR_client_id:
        print("openemr_client_id not set, not attempting to save doc to OpenEMR")
        return ""
    
    # this block results in similar escaping that happens on the app side
    # some special characters like bullet points may still be showing up incorrectly
    bytes_content = content.encode('latin1', 'ignore')
    fixed_content = bytes_content.decode('utf8', errors='ignore')
    cleaned = clean_json_string(fixed_content)
    binary = cleaned.encode('utf-8')
    files=[
      ('document',(f"{filename}.txt", binary, 'text/plain'))
    ]
    print(f"openEMR posting new document")
    response = _requestEMR(
        token
        ,f"/api/patient/{patient_id}/document?path=Categories"
        , methodName = "POST"
        , moreHeaders={"Content-Type": None}
        , requestParams={
            "files":files
        }
    )
    return response

def getPatientIdByUuidOpenEMR(token, patient_id):
    result_data = _requestEMR(token, "/api/patient/{patient_id}")
    data = result_data["data"]
    pid = data["pid"]
    return pid

def listPatientsOpenEMR(token):
    result_data = _requestEMR(token, f"/api/patient")
    data = result_data["data"]
    return data

def newVitalsOpenEMR(token, patient_id, encounter_id, vitals_request_body):
    return _requestEMR(token, f"/api/patient/{patient_id}/encounter/{encounter_id}/vital", methodName = "POST", requestParams={"data" : vitals_request_body})

def getPatientByUUID(token, patient_id):
    return _requestEMR(token, f"/api/patient/{patient_id}")

def getDocumentOpenEMR(token, patient_id, document_id):
    res = _requestEMR(token, f"/api/patient/{patient_id}/document/{document_id}", returnRawResponse=True)
    data = res.text
    return data

def listDocumentsOpenEMR(token, patient_id):
    data = {"data":[]}
    try:
        data = _requestEMR(token, f"/api/patient/{patient_id}/document?path=Categories")
        if not data:
            return []
    except json.decoder.JSONDecodeError as je:
        print("listDocumentsOpenEMR no parseable json exception:", je)
        return []
    except Exception as e:
        print("listDocumentsOpenEMR exception:", e) #when no docs we get response text = 'null' which doesn't parse as json
        return []
    print("listDocumentsOpenEMR response OK: ", data)
    return data

def listEncountersOpenEMR(token, patient_uuid):
    data = {"data":[]}
    try:
        data = _requestEMR(token, f"/api/patient/{patient_uuid}/encounter")
        if not data:
            return []
    except json.decoder.JSONDecodeError as je:
        print("listEncountersOpenEMR no parseable json exception:", je)
        return []
    except Exception as e:
        print("listEncountersOpenEMR exception:", e) #when no docs we get response text = 'null' which doesn't parse as json
        return []
    print("listEncountersOpenEMR response OK: ", data)
    return data["data"]

def getVitalsOpenEMR(token, patient_id, encounter_id):
    data = []
    try:
        data = _requestEMR(token, f"/api/patient/{patient_id}/encounter/{encounter_id}/vital")
        if not data:
            return []
    except json.decoder.JSONDecodeError as je:
        print("getVitalsOpenEMR no parseable json exception:", je)
        return []
    except Exception as e:
        print("getVitalsOpenEMR exception:", e)
        return []
    return data