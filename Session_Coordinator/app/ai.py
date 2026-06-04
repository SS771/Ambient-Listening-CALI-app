from datetime import datetime, timedelta, timezone
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openemr import connector, fhir
from typing import Annotated, List
from .middleware.wlc_auth import WlcUser, auth_middleware
import requests

from .inference import agents

import unittest
from unittest.mock import patch

router = APIRouter(prefix = "/ai")
fhirClient = fhir.FhirConnector(connector._requestEMR)

def _aiPrompt(data):
    promptEngineUrl = "https://prompt-engine.1s2ddobfrh0f.us-south.codeengine.appdomain.cloud" #TODO FIXME hardcode -> envvar
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(promptEngineUrl, data=data, headers=headers)
    return response.text

class DomainTermResponse(BaseModel):
    domain_terms: List[str]

def _validateCharacters(s:str, invalidCharacters=["[", "]", "(", ")", "#", "$", "%", ":", ":"])->bool:
    '''
    returns true if only valid characters in the string
    '''
    for ch in invalidCharacters:
        if ch in s:
            return False
    return True

def _validateAiDomainTermOutput(s:str)->DomainTermResponse:
    sList = s.split("\n")
    r = []
    badOutput = []
    for line in sList:
        line = line.strip()
        if len(line) > 2 and len(line.split(" ")) < 5 and _validateCharacters(line): #longer than 2 characters and shorter than 5 space delimited words
            r.append(line)
        else:
            badOutput.append(line)
    print("_validateAiDomainTermOutput : discarded output : ->", badOutput)
    return DomainTermResponse(domain_terms=list(set(r)))

@router.get("/domainterms/patient/{patient_UUID}")
def suggestDomainTermsForPatientSession(patient_UUID:str, user: Annotated[WlcUser, Depends(auth_middleware)])->DomainTermResponse:
    discoveredTerms = []
    patientData = connector.getPatientByUUID(user.emr_token, patient_UUID)
    patientName = None
    try:
        patientName = patientData.get("data", {})
        patientName = patientName.get("fname", "") + " " + patientName.get("lname", "")
    except:
        raise HTTPException(404, detail="could not retrieve medication list for patient, is UUID valid?")
    if patientName:
        discoveredTerms.append(patientName)
    medications = fhirClient.getMedicationForPatient(user, patient_UUID)
    if medications.get("entry") != None:
        medications = [x["resource"]["medicationCodeableConcept"]["text"] for x in medications["entry"]]
    else:
        medications = []
    discoveredTerms = discoveredTerms + medications
    #username = user.username #TODO this will be an email that requires additional parsing, & is not useful for the scope of the current demo
    return DomainTermResponse(domain_terms=discoveredTerms)

@router.get("/domainterms/patient/{patient_id}/transcript/{transcript_id}")
def suggestDomainTermsForPatientTranscript(patient_id:str, transcript_id:str, user:Annotated[WlcUser, Depends(auth_middleware)])->DomainTermResponse:
    doc = connector.getDocumentOpenEMR(user.emr_token, patient_id, transcript_id)
    if doc == "":
        raise HTTPException(404, detail = "could not find patient document specified")
    prompt = "You are a summarization expert. Extract the names of people, medication, and medical procedures discussed in the following transcript and provide as a newline seperated list. Do not explain the terms. Do not provide additional information or context."
    data = {"prompt": prompt, "content": doc, "min_new_tokens": 10, "max_new_tokens": 150}
    return _validateAiDomainTermOutput(_aiPrompt(data))


class LLMQueryResponse(BaseModel):
    text: str
    ok: bool

class TextPayload(BaseModel):
    text: str

@router.post("/extract/medications")
def extractMedicationFromConversation(txt: TextPayload, user:Annotated[WlcUser, Depends(auth_middleware)])->LLMQueryResponse:
    return LLMQueryResponse(text = _aiPrompt({
        "prompt":"You are a medical summarization expert. Create a list of medications with any relevent dosage or dates mentioned in the following transcript. If there is no mention of any medications report that there were no medications discussed"
        , "content": connector.extractWordsFromTranscript(txt.text, False)
        , "min_new_tokens":5
        , "max_new_tokens":150
    })
    , ok = True
    )

class TestsAiEndpointsLogic(unittest.TestCase):
    @patch("openemr.connector.getPatientByUUID", lambda user, puuid : {"data": {"fname": "John", "lname":"Smith"}})
    @patch("openemr.fhir.FhirConnector.getMedicationForPatient", lambda ref, user, puuid : {"entry": [{"resource":{"medicationCodeableConcept":{"text":"Test_Medication"}}}]})
    def test_suggestDomainTermsForPatientSession(self):
       results = suggestDomainTermsForPatientSession("0", WlcUser(username="test user", emr_token="token"))
       self.assertEqual(["John Smith", "Test_Medication"], results.domain_terms)

    @patch("openemr.connector.getPatientByUUID", lambda user, puuid : None)
    @patch("openemr.fhir.FhirConnector.getMedicationForPatient", lambda ref, user, puuid : {"entry": [{"resource":{"medicationCodeableConcept":{"text":"Test_Medication"}}}]})
    def test_suggestDomainTermsForPatientSession_noPatientFound(self):
        expectedErrorStr = "could not retrieve medication list for patient, is UUID valid?"
        with self.assertRaises(HTTPException) as err:
            results = suggestDomainTermsForPatientSession("0", WlcUser(emr_token="token", username="test user"))
        self.assertEqual(err.exception.detail, expectedErrorStr)
    
    @patch("app.ai._aiPrompt", lambda d : "I am a fake LLM model and this is the style of overly verbose output I'm prone to\n\n\nJohn Smith\nJane Doe\nTylenol")
    @patch("openemr.connector.getDocumentOpenEMR", lambda token, pid, tid : "Hello I'm John Smith, hello I'm Jane Doe. I see you're taking Tylenol daily.")
    def test_suggestDomainTermsForPatientTranscript(self):
        results = suggestDomainTermsForPatientTranscript("0", "0", WlcUser(emr_token="token", username="test user"))
        self.assertSetEqual({"John Smith", "Jane Doe", "Tylenol"}, set(results.domain_terms)) #output order may change
    
    @patch("app.ai._aiPrompt", lambda d : "test should raise error before this is called")
    @patch("openemr.connector.getDocumentOpenEMR", lambda token, pid, tid : "")
    def test_suggestDomainTermsForPatientTranscript_noTranscriptFound(self):
        expectedErrorStr = "could not find patient document specified"
        with self.assertRaises(HTTPException) as err:
            results = suggestDomainTermsForPatientTranscript("0", "0", WlcUser(emr_token="token", username="test user"))
        self.assertEqual(err.exception.detail, expectedErrorStr)
    
    @patch("app.ai._aiPrompt", lambda d : d["content"])
    def test_extractMedicationFromConversation(self):
        ts = ">> This is a\n>> transcript that has\n>> several speaker change markers"
        results = extractMedicationFromConversation(
            TextPayload(text=ts)
            ,WlcUser(emr_token="token", username="test user")
        )
        self.assertEqual(connector.extractWordsFromTranscript(ts, False), results.text)



def summarizeInWatsonx(content):
    prompt = "You are a medical summarization expert. Analyze the following patient visit. Summarize the patient visit transcript by simplifying word choices. Sentences should contain 15 words or less. Summarize everything that is discussed. Do not request feedback for your response."
    data = {"prompt": prompt, "content": content, "min_new_tokens": 50, "max_new_tokens": 300}
    result = _aiPrompt(data)
    return result

def shiftSummaryInWatsonx(content):
    prompt = "You are a medical summarization expert. Analyze the following patient visits. You will be compiling a shift hand-off report. Be brief and accurate. First summarize each transcript with simplified wording, then give a concise summary of all of the encounters."
    data = {"prompt": prompt, "content": content, "min_new_tokens": 50, "max_new_tokens": 900}
    result = _aiPrompt(data)
    return result

def healthMonitorInWatsonx(content):
    prompt = "You are a medical summarization expert. Analyze the following patient visits. Provide a short list of changes in the patients condition between visits. If the patients condition is unchanged report it as such."
    data = {"prompt":prompt, "content":content, "min_new_tokens":30, "max_new_tokens":200}
    result = _aiPrompt(data)
    return result

def vitalsInWatsonx(content):
    result = json.loads(agents.AI_VITALS.prompt(content).model_dump_json())
    result["oxygen_saturation"] = result.get("oxygen_saturation", "").replace("%", "") #ai likes to stick a % sign here that isn't accepted by the emr endpoint which requires user to fix as form isn't valid
    return result

def massageVitalsToJSON(content): #TODO depricate
    prompt = """You are a medical summarization expert. The following content lists a patient's vitals. Reformat this information into the example JSON format with the correct values applied, with empty strings appearing only for values that are not available. Respond with only the populated JSON. Example JSON format: {"bps":"130","bpd":"80","weight":"220","height":"70","temperature":"98","temp_method":"Oral","pulse":"60","respiration":"20","note":"Patient with difficulty standing, which made weight measurement difficult.","waist_circ":"37","head_circ":"22.2","oxygen_saturation":"96"}"""
    # wrap content to improve model response
    content = "[begin vitals]" + content + "[end vitals]"
    data = {"prompt": prompt, "content": content, "min_new_tokens": 20, "max_new_tokens": 150}
    result = _aiPrompt(data)
    return result

def followUpInWatsonx(content):
    prompt = "You are a medical summarization expert. Analyze the following patient visit. List a few helpful follow-up questions that the nurse might have forgotten to ask. Limit to four questions. Do not include a summary of the interaction and do not request feedback for your response."
    data = {"prompt": prompt, "content": content, "min_new_tokens": 50, "max_new_tokens": 300}
    result = _aiPrompt(data)
    return result

def additionalRecommendationsInWatsonx(content):
    result = agents.AI_ADDITIONAL_RECOMMENDATIONS.prompt(content)
    return result

def actionItemsInWatsonx(content):
    prompt = "You are a medical summarization expert. Analyze the following patient visit. If the nurse stated any intention of future action items, cleanly list them. Do not include a summary of the interaction and do not request feedback for your response."
    data = {"prompt": prompt, "content": content, "min_new_tokens": 50, "max_new_tokens": 300}
    result = _aiPrompt(data)
    return result

def physicalInWatsonx(content):
    response = json.loads(agents.AI_PHYSICAL_ASSESSMENT.prompt(content).model_dump_json())
    return "\n".join([f"- {k} : {response[k]}" for k in response])

def customPromptWatsonx(content, customPrompt):
    prompt = "You are a medical summarization expert. Analyze the following patient visit. " + customPrompt
    data = {"prompt": prompt, "content": content, "min_new_tokens": 50, "max_new_tokens": 300}
    result = _aiPrompt(data)
    return result

class WlcEmrPrompt(BaseModel):
    patient_id: str
    encounter_id: str

class WlcEmrTranscriptPrompt(WlcEmrPrompt):
    transcript: str

class WlcEmrCustomPrompt(WlcEmrTranscriptPrompt):
    query: str

class WlcEmrVitalsResponse(BaseModel):
    summary: str
    note: str
    bps: str
    bpd: str
    weight: str
    height: str
    temperature: str
    temperature_method: str
    pulse: str
    respiration: str
    waist_circ: str
    head_circ: str
    oxygen_saturation: str

class WlcEmrSaveVitals(WlcEmrPrompt, WlcEmrVitalsResponse):
    pass

@router.post("/summary")
async def emitSummary(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    medical_summary = summarizeInWatsonx(transcript)
    prompt_results_json = json.dumps([medical_summary], indent=4)
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_summary")
    return prompt_results_json

@router.post("/shiftSummary")
async def emitShiftSummary(promptReq : WlcEmrPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    combined_transcripts = ""
    # list transcripts
    # gather transcripts from certain date range (last 12 hours?)
    docs = connector.listDocumentsOpenEMR(user.emr_token, promptReq.patient_id)
    # filter for last (12?) hours based on date in filename, only consider files with transcript in the name
    twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
    shift_docs = []
    for one_doc in docs:
        filename = one_doc["filename"]
        if "_transcript_" in filename:
            file_time = parse_datetime_from_filename(filename)
            if file_time > twelve_hours_ago:
                shift_docs.append(one_doc["id"])
    for one_doc_id in shift_docs:
        doc_text = connector.getDocumentOpenEMR(user.emr_token, promptReq.patient_id, one_doc_id)
        combined_transcripts = combined_transcripts + "\n" + doc_text + "\n"
    combined_transcripts = combined_transcripts + "[end all shift transcripts]"
#     print(f"combined transcripts:\n{combined_transcripts}")
    shift_summary = shiftSummaryInWatsonx(combined_transcripts)
    prompt_results_json = json.dumps([shift_summary], indent=4)
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_shiftsummary")
    return prompt_results_json

@router.post("/vitals")
async def emitVitals(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)])->WlcEmrVitalsResponse:
    # grab transcript for prompting
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    vitals = vitalsInWatsonx(transcript)
    return WlcEmrVitalsResponse(**vitals)

@router.post("/saveVitals")
async def saveVitals(promptReq : WlcEmrSaveVitals, user: Annotated[WlcUser, Depends(auth_middleware)])->LLMQueryResponse:
    print(f"vitals content: {promptReq.model_dump_json()}")
    modelJsonStr = promptReq.model_dump_json(exclude=["patient_id", "encounter_id"], indent=4)
    validated_vitals_body = connector.validateVitalsRequestBody(modelJsonStr)
    if validated_vitals_body is not None:
        # create+save document of vitals
        vitalsJson = json.loads(validated_vitals_body)
        vitalsDoc = "\r\n".join([f"summary: {promptReq.summary}"] + [f"{k}: {vitalsJson[k]}" for k in vitalsJson])
        connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, vitalsDoc, "encounter_" + promptReq.encounter_id + "_vitals")
        #save results to vitals endpoint
        emr_upload_result = connector.newVitalsOpenEMR(user.emr_token, promptReq.patient_id, promptReq.encounter_id, validated_vitals_body)
        #FIXME TODO - there's no form validation on the backend - see CREATE TABLE `form_vitals` -> https://github.com/openemr/openemr/blob/master/sql/database.sql for the types; there is validation on the frontend currently
        # err format from emr_upload_result -> `{"oxygen_saturation":{"Numeric::NOT_NUMERIC":"oxygen saturation must be numeric"}}``
        # print("EMR UPLOAD", emr_upload_result) # since we save the doc before doing this, if we return ok=False that'd create a confusing user flow
        result = LLMQueryResponse(ok=True, text=vitalsDoc)
    else:
        result = LLMQueryResponse(ok = False, text="Vitals not posted to OpenEMR, massaged request body failed validation")
    print(result)
    return result

@router.post("/additionalRecommendations")
async def emitAdditionalRecommendations(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    additionalRecommendations = additionalRecommendationsInWatsonx(transcript)
    prompt_results_json = json.dumps([additionalRecommendations], indent=4)
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_additionalrecommendations")
    return prompt_results_json

@router.post("/actionItems")
async def emitActionItems(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    actionItems = actionItemsInWatsonx(transcript)
    prompt_results_json = json.dumps([actionItems], indent=4)
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_actionitems")
    return prompt_results_json


@router.post("/followup")
async def emitFollowUps(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    follow_ups = followUpInWatsonx(transcript)
    prompt_results_json = json.dumps([follow_ups], indent=4)
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_followup")
    return prompt_results_json

@router.post("/physical")
async def emitPhysical(promptReq : WlcEmrTranscriptPrompt, user: Annotated[WlcUser, Depends(auth_middleware)])->LLMQueryResponse:
    # grab transcript for prompting
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    
    physical = physicalInWatsonx(transcript)
    results = LLMQueryResponse(text = physical, ok = ( ("]" not in physical) and (not physical == "") ) )
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, physical, "encounter_" + promptReq.encounter_id + "_physical")
    return results

@router.post("/query")
async def emitQuery(promptReq : WlcEmrCustomPrompt, user: Annotated[WlcUser, Depends(auth_middleware)]):
    customQuery = promptReq.query
    transcript = connector.extractWordsFromTranscript(promptReq.transcript, False)
    answer = customPromptWatsonx(transcript, customQuery)
    prompt_results_json = json.dumps([answer], indent=4)
    # build result to save
    query_record = "\nCustom query:\n" + customQuery + "\nAnswer:\n" + prompt_results_json
    # save result in openemr
    connector.newDocumentOpenEMR(user.emr_token, promptReq.patient_id, query_record, "encounter_" + promptReq.encounter_id + "_custom_query")
    return prompt_results_json

@router.post("/healthMonitor")
async def emitHealthMonitorReport(promptReq : WlcEmrPrompt, user: Annotated[WlcUser, Depends(auth_middleware)])->LLMQueryResponse:
    combined_transcripts = ""
    docs = connector.listDocumentsOpenEMR(user.emr_token, promptReq.patient_id)
    maxDocs = 2 #max number of docs to use in context
    transcripts = [y for y in filter(lambda x : "_transcript_" in x["filename"], docs)]
    if len(transcripts) < 2:
        return LLMQueryResponse(
            ok=False
            ,text="Not enough patient transcripts to create health monitor report for this patient!"
        )
    transcripts.sort(key = lambda x : parse_datetime_from_filename(x["filename"]), reverse=True)
    for one_doc in transcripts[0:maxDocs]:
        doc_text = connector.getDocumentOpenEMR(user.emr_token, promptReq.patient_id, one_doc["id"])
        combined_transcripts = combined_transcripts + f"[transcript {one_doc['filename'].split("_")[-1].split(".")[0]}]" + "\n" + doc_text + "\n"
    combined_transcripts = combined_transcripts + "[end all transcripts]"
    print("\nemitHealthMonitorReport\n",combined_transcripts, "\n=====\n")
    healthSummary = healthMonitorInWatsonx(combined_transcripts)
    # save result in openemr
    #connector.newDocumentOpenEMR(promptReq.patient_id, prompt_results_json, "encounter_" + promptReq.encounter_id + "_shiftsummary")
    return LLMQueryResponse(
        ok=True
        ,text=healthSummary
    )

def parse_datetime_from_filename(filename):
    # filename format example: encounter_44_transcript_07-25-2025 12:43.txt
    try:
        # split filename
        file_date = filename.split('_transcript_')[-1].replace('.txt', '')

        # grab date
        date = datetime.strptime(f"{file_date} +0000", "%m-%d-%Y %H:%M %z")
        date.astimezone(timezone.utc)
        return date
    except Exception as e:
        raise ValueError(f"Could not parse date from filename: {filename}") from e
    
class Test_UtilityFunctions(unittest.TestCase):
    def test_parse_datetime_from_filename_success(self):
        filename = "encounter_44_transcript_07-25-2025 12:43.txt"
        date = parse_datetime_from_filename(filename)
        now = datetime.now(timezone.utc)
        self.assertTrue(date < now)

class Test_ResultEmittingFunctions(unittest.IsolatedAsyncioTestCase):
    @patch("app.ai._aiPrompt")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitSummary(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_callWatsonX.return_value = "Mocked Summary prompt result"
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1")
        result = await emitSummary(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, """[\n    "Mocked Summary prompt result"\n]""")

    @patch("app.ai.vitalsInWatsonx")
    async def test_emitVitals(self, mock_vitalsInWatsonx):
        mock_vitalsData = {
            "summary": "dummy summary"
            ,"note": "dummy note"
            ,"bps": "100"
            ,"bpd": "80"
            ,"weight": "200"
            ,"height": "5'9"
            ,"temperature": "98.6"
            ,"temperature_method": ""
            ,"pulse": "68"
            ,"respiration": "20"
            ,"waist_circ": ""
            ,"head_circ": ""
            ,"oxygen_saturation": "100%"
        }
        mock_vitalsInWatsonx.return_value = mock_vitalsData
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1")
        result = await emitVitals(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, WlcEmrVitalsResponse(**mock_vitalsData))

    @patch("app.ai.physicalInWatsonx")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitPhysical(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        mock_callWatsonX.return_value = "Mocked Physical prompt result"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_vitals = """Dummy vitals string"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1", vitals = test_vitals)
        result = await emitPhysical(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result.text, "Mocked Physical prompt result")

    @patch("app.ai.additionalRecommendationsInWatsonx")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitAdditionalRecommendations(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_callWatsonX.return_value = "Mocked Additional Recommendations prompt result"
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1")
        result = await emitAdditionalRecommendations(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, """[\n    "Mocked Additional Recommendations prompt result"\n]""")

    @patch("app.ai._aiPrompt")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitActionItems(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_callWatsonX.return_value = "Mocked Action Items prompt result"
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_vitals = """Dummy vitals string"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1", vitals = test_vitals)
        result = await emitActionItems(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, """[\n    "Mocked Action Items prompt result"\n]""")

    @patch("app.ai._aiPrompt")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitFollowUps(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_callWatsonX.return_value = "Mocked Follow Up prompt result"
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_request = WlcEmrTranscriptPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", encounter_id = "1")
        result = await emitFollowUps(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, """[\n    "Mocked Follow Up prompt result"\n]""")

    @patch("app.ai._aiPrompt")
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitQuery(self, mock_newDocumentOpenEMR, mock_callWatsonX):
        mock_callWatsonX.return_value = "Mocked Custom Query prompt result"
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_transcript = """[transcript] Dummy patient visit transcript [end]"""
        test_request = WlcEmrCustomPrompt(transcript = test_transcript, patient_id = "dummy-patient-id", query = "Why did the chicken cross the road?", encounter_id = "1")
        result = await emitQuery(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertEqual(result, """[\n    "Mocked Custom Query prompt result"\n]""")
