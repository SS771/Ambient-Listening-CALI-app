import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openemr import connector
from app.middleware.wlc_auth import WlcUser
import app.ai as ai
from app.ai import WlcEmrPrompt, WlcEmrTranscriptPrompt, WlcEmrCustomPrompt
import requests
import queue
import json
import time
from datetime import datetime, timedelta, timezone

''' # these tests are disabled for now, auth doesn't use this flow anymore
class Test_AuthEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(router)

    @patch('app.middleware.wlc_auth._getClientApikey')
    @patch('connector.getOpenEMRToken_PasswordGrant')
    def test_authorizeToApp_success(self, mock_getClientApikey):
        mock_getClientApikey.return_value = "c-fakeclientapikey"
        response = self.client.post('/auth', data={"username":"test@ibm.com", "password":"pass1234"})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.text)
        self.assertIn("ey", response_data["access_token"])

    @patch('app.middleware.wlc_auth._getClientApikey')
    @mock.patch.dict(os.environ, {"auth_password": "pass1234","allowed_users":"test@ibm.com,test2@ibm.com"}, clear=True)
    def test_authorizeToApp_wrongPassword(self, mock_getClientApikey):
        mock_getClientApikey.return_value = "c-fakeclientapikey"
        response = self.client.post('/auth', data={"username":"test@ibm.com", "password":"incorrectpassword"})
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.text)
        self.assertEqual(response_data["detail"], "Invalid login credentials provided")
'''

def loadTranscript(location):
    with open(location, "r") as f:
        return f.read()

class DataLogger:
    def __init__(self, *args, **kwargs):
        self.q = queue.Queue()
        self.sep = "\n==================================================\n"
    async def __call__(self, file, str):
        self.q.put((file,str))
    async def writeResult(self):
        files = {}
        while not self.q.empty():
            m = self.q.get()
            oldContent = files.get(m[0], "")
            newContent = "<!NO_CONTENT!>"
            finalContent = ""
            try: #in testing 'm[1] == None' sometimes, failing tests, seems to be triggered if vitals can't be parsed.
                newContent = m[1]
                finalContent = oldContent + newContent + self.sep
            except Exception as e:
                newContent = f"<!EXCEPTION> exception_name='{e}' data='{m}' <EXCEPTION!>"
                finalContent = oldContent + newContent + self.sep
            files[m[0]] = finalContent
        for k in files:
            with open(k, "w+") as f:
                f.write(files[k])

# this test will actually do a real call to the prompt engine
# purpose of this is to make it easier to tell if prompt results are totally borked after something like a model or model param change
# OpenEMR doc save is mocked, we just want to see the prompt output in the terminal
class Test_AllPromptFunctions_ActuallyCallingPromptEngine(unittest.IsolatedAsyncioTestCase):
    @patch('openemr.connector.newDocumentOpenEMR')
    async def test_emitAll(self, mock_newDocumentOpenEMR):
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        test_requests = ( #Load test transcripts
            WlcEmrTranscriptPrompt(transcript = get_test_transcript(), patient_id = "dummy-patient-id", encounter_id = "1")
            , WlcEmrTranscriptPrompt(transcript = loadTranscript("./test/_jacksongi_shouldgetvitals_1.txt"), patient_id = "dummy-patient-id", encounter_id = "1001")
            , WlcEmrTranscriptPrompt(transcript = loadTranscript("./test/_mitchell_abdominal_1.txt"), patient_id = "dummy-patient-id", encounter_id = "1002")
            , WlcEmrTranscriptPrompt(transcript = loadTranscript("./test/_mitchell_abdominal_2.txt"), patient_id = "dummy-patient-id", encounter_id = "1003")
        )
        _timestamp = time.time()
        log = DataLogger()
        for test_request in test_requests: #run these ops for every piece of content
            summaryResult = await ai.emitSummary(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(summaryResult, "")
            #print("\n==================================\n")
            #print(f"Summary Result: \n{summaryResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitSummary.txt", summaryResult)
            

            vitalsResult = await ai.emitVitals(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(vitalsResult, "")
            #print("\n==================================\n")
            #print(f"Vitals Result: \n{vitalsResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitVitals.txt", vitalsResult.model_dump_json(indent = 4))

            '''
            #FIXME - this doesn't always work first try, moving to agentic approach should fix but disabling for now
            vitalsJsonResult = ai.massageVitalsToJSON(vitalsResult)
            self.assertNotEqual(vitalsResult, "")
            #print("\n==================================\n")
            #print(f"Vitals as JSON Result: \n{vitalsJsonResult}\n")
            validated_vitals_body = connector.validateVitalsRequestBody(vitalsJsonResult) 
            self.assertNotEqual(validated_vitals_body, None)
            #print(f"Validated Vitals JSON Result: \n{validated_vitals_body}\n")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_vitalsJson.txt", validated_vitals_body)
            '''

            physicalResult = await ai.emitPhysical(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(physicalResult.text, "")
            #print("\n==================================\n")
            #print(f"Physical Result: \n{physicalResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitPhysical.txt", physicalResult.text)
            

            addlRecsResult = await ai.emitAdditionalRecommendations(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(addlRecsResult, "")
            #print("\n==================================\n")
            #print(f"Additional Recommendations Result: \n{addlRecsResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitAdditionalRecommendations.txt", addlRecsResult)
            

            actionItemsResult = await ai.emitActionItems(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(actionItemsResult, "")
            #print("\n==================================\n")
            #print(f"Action items Result: \n{actionItemsResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitActionItems.txt", actionItemsResult)
            

            followUpsResult = await ai.emitFollowUps(test_request, WlcUser(username="test user", emr_token="token"))
            self.assertNotEqual(followUpsResult, "")
            #print("\n==================================\n")
            #print(f"Follow up Result: \n{followUpsResult}")
            #print("\n==================================\n")
            await log(f"{_timestamp}_{test_request.encounter_id}_emitFollowUps.txt", followUpsResult)
        

        test_query_request = WlcEmrCustomPrompt(transcript = get_test_transcript(), patient_id = "dummy-patient-id", query = "What procedure is the patient awaiting?", encounter_id = "1")
        queryResult = await ai.emitQuery(test_query_request, WlcUser(username="test user", emr_token="token"))
        self.assertNotEqual(queryResult, "")
        #print("\n==================================\n")
        #print(f"Query Result: \n{queryResult}")
        #print("\n==================================\n")
        await log(f"{_timestamp}_emitQueryCustom.txt", queryResult)

        await log.writeResult()


    @patch('openemr.connector.newDocumentOpenEMR')
    @patch('openemr.connector.listDocumentsOpenEMR')
    @patch('openemr.connector.getDocumentOpenEMR')
    async def test_emitShiftSummary(self, mock_getDocumentOpenEMR, mock_listDocumentsOpenEMR, mock_newDocumentOpenEMR):
        mock_getDocumentOpenEMR.side_effect = get_doc_mock
        mock_newDocumentOpenEMR.return_value = "Dummy response text"
        now = datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M")
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%m-%d-%Y %H:%M")
        four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%m-%d-%Y %H:%M")
        six_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%m-%d-%Y %H:%M")
        fifteen_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=15)).strftime("%m-%d-%Y %H:%M")
        mock_listDocumentsOpenEMR.return_value = [{"id":"1", "filename": f"encounter_2_transcript_{six_hours_ago}.txt"},{"id":"2", "filename": f"encounter_3_transcript_{four_hours_ago}.txt"},{"id":"3", "filename": f"encounter_9_transcript_{two_hours_ago}.txt"},{"id":"4", "filename": f"encounter_10_transcript_{now}.txt"},{"id":"5", "filename": f"encounter_1_transcript_{fifteen_hours_ago}.txt"}]
        test_vitals = """Dummy vitals string"""
        test_request = WlcEmrPrompt(transcript = get_test_transcript(), patient_id = "dummy-patient-id", encounter_id = "1", vitals = test_vitals)
        shiftSummaryResult = await ai.emitShiftSummary(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertNotEqual(shiftSummaryResult, "")
        print("\n==================================\n")
        print(f"Shift Summary Result: \n{shiftSummaryResult}")
        print("\n==================================\n")
        time.sleep(3)
    
    @patch('openemr.connector.listDocumentsOpenEMR')
    @patch('openemr.connector.getDocumentOpenEMR')
    async def test_emitHealthMonitorReport(self, mock_getDocumentOpenEMR, mock_listDocumentsOpenEMR):
        mock_getDocumentOpenEMR.side_effect = get_doc_mock
        now = datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M")
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%m-%d-%Y %H:%M")
        four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%m-%d-%Y %H:%M")
        six_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%m-%d-%Y %H:%M")
        fifteen_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=15)).strftime("%m-%d-%Y %H:%M")
        mock_listDocumentsOpenEMR.return_value = [{"id":"1", "filename": f"encounter_2_transcript_{six_hours_ago}.txt"},{"id":"2", "filename": f"encounter_3_transcript_{four_hours_ago}.txt"},{"id":"3", "filename": f"encounter_9_transcript_{two_hours_ago}.txt"},{"id":"4", "filename": f"encounter_10_transcript_{now}.txt"},{"id":"5", "filename": f"encounter_1_transcript_{fifteen_hours_ago}.txt"}]
        test_vitals = """Dummy vitals string"""
        test_request = WlcEmrPrompt(transcript = get_test_transcript(), patient_id = "dummy-patient-id", encounter_id = "1", vitals = test_vitals)
        healthMonitorResult = await ai.emitHealthMonitorReport(test_request, WlcUser(username="test user", emr_token="token"))
        self.assertNotEqual(healthMonitorResult.text, "")
        print("\n==================================\n")
        print(f"Health Monitor Result: \n{healthMonitorResult.text}")
        print("\n==================================\n")
        time.sleep(3)

# mock dynamic return values for getDocumentOpenEMR
def get_doc_mock(token, patient_id, document_id):
    if document_id == "1":
        return get_test_transcript()
    elif document_id == "2":
        return get_test_transcript_2()
    elif document_id == "3":
        return get_test_transcript_3()
    elif document_id == "4":
        return get_test_transcript_4()
    elif document_id == "5":
        return get_test_transcript_5()
    else:
        return "Unknown document content"

def get_test_transcript():
    transcript = """
    [transcript]
    Come in. Hey, I'm savannah. Hi, I'm Morgan. It's going to be hi. How are you doing today? Good. I'm good. Except for. This dizziness. If I could get this dizziness to go away, I think I'd feel a whole lot better. Yeah. Have you been dizzy.
    For a while or is that just start?
    No. It started. I don't know, it may have started before I even came in. I was bleeding for about two days before I came to the emergency room. And you know, I've been I've been dizzy down in the emergency room and. Here. Yeah. Okay.
    Well we're just going to take a quick assessment and then we'll let you know where we're going to go from there. Is that sound good? Yeah. Okay.
    Yeah. Do y'all know when I'm going to have that scope thing done? We aren't sure as of.
    Right now. I think we're still waiting on some doctor's orders. So as soon as we get a set time for that endoscopy we'll let you know.
    Thank you.
    And so vitals heart rate is going to be 84. SpO2 is 99. Respiratory rate is 20. Temperature is 98.6 and B.P. is 119 over 69.
    That's my blood pressure. Sounds good. Yeah.
    Are you having any any pain right now?
    Just a little. It's not bad. Not nearly as bad. When I first came in it was really bad.
    Where are you having a lot of that pain?
    Well let's see generalized in my abdomen. But occasionally I'll have some pain right here too.
    In your chest. Okay.
    Kind of like right here.
    Do you take anything for that chest pain? Okay.
    No, it just kind of comes and goes. It really just started.
    Gotcha.
    With this bleeding.
    Okay. Can I take a look at down here where you said it was hurting? Sure. Okay.
    Yeah. How are you?
    Oh, yeah. You're bleeding a little bit. Yeah, we'll just change that pad for you. Go ahead.
    This they changed this about a half hour ago.
    Okay. We'll definitely get that weighed and then put that in your chart for your doctor.
    Thank you. Let me see how much it is. Oh, gosh. Yeah. Okay. All right.
    All right.
    What's up? Thank you.
    All right. Are you going to do that?
    Okay.
    Alrighty.
    So listen to your lungs really quick if that's okay. And your heart rate.
    Again I'm just going to weigh this on the scale and then I'm going to put it in the right waist. Can. And I'm putting it in the chart.
    Now can you take a couple deep breaths for me.
    Okay.
    And I'm just going to listen to your stomach for a little bit.
    That bleeding from earlier is that about the amount that you were having at home or is that significantly more?
    That's I would say I didn't have those big pads so but I mean they just changed that right before I came here about a half hour ago.
    Okay.
    And they changed it twice down in the emergency room and it seemed like it was even worse in the ER. But I was down there longer than half hour. Yeah I guess about the same. Okay. It's heavy. It seems like it should be slowing down.
    Yeah well definitely give the doctor a call. And make them aware of that just because we want to get that to stop eventually just you know, if you're having if you're being if you're getting dizzy and stuff like that we want to check your hemoglobin and things like that just to make sure that your blood levels are all stable. So we'll give them a call and he'll probably order some blood tests so I'm sure someone from the lab or we will be back in to get those things.
    Perfect. I feel like two I don't know if this is me just kind of being nervous here, but I feel like I'm just a little bit short of breath too.
    Okay.
    Okay. Short of breath and real and just dizzy are my main things.
    Gotcha. Right now your oxygen saturation is 99%. I'm really the best you can get is is 100 so good. You're looking pretty good right now.
    No need to worry about that.
    We'll come back in and check on you in a minute. We have a few other patients to see, but we'll come back and check and see if you're still.
    Appreciate it. Yeah. All right. Thank you.
    You're welcome.
    Thanks.
    We'll come back.
    Let me know if you find out about that scope. Okay?
    Yes we will.
    Thank you.
    [end]
    """
    return transcript

def get_test_transcript_2():
    transcript = """
    [transcript]
    Hi, Ms. Jackson, I'm Casey, I'll be taking over your care for the evening shift.
    Hello.
    Can you confirm your date of birth for me?
    July third, 1980.
    Great, thank you. How are you feeling, are you still having any dizziness?
    Just a little bit.
    Gotcha, any other changes?
    I do feel a bit warm, I'm not sure if the air was turned off, or something.
    A little warm? I don't think the air has been changed, but I can check on that for you. Alright, let's get your vitals. (pause) So it looks like your heart rate is 85. SpO2 is 99, that looks good. Respiratory rate is 22. Temperature is 99.3. Blood pressure is 118 over 74. Temperature is looking a little warm, that's something we should keep an eye on.
    Oh, oh no
    Yeah, it's a small fever, but we will keep an eye on it. Do you mind if I take a look at your bleeding?
    Sure.
    Well I talked to Savannah at the end of her shift, looks like your bleeding is starting to slow down a bit.
    That's good news.
    Yeah, another thing we'll keep an eye on. I have some other patients to check on but I will be back in just a little bit.
    Thank you. Oh, before you go, could I ask a favor?
    Sure, what do you need?
    Can I get a little bit of water?
    Um, it sounds like you are still on NPO orders, so nothing by mouth just yet.
    Oh, okay.
    Yeah, sorry about that. I will be back in a little bit.
    Okay, thank you.
    [end]
    """
    return transcript

def get_test_transcript_3():
    transcript = """
    [transcript]
    Hi, Ms. Jackson, checking in again.
    Hello.
    Can you confirm your date of birth for me?
    July third, 1980.
    Great, thank you. How are you feeling?
    Feeling alright, just a little tired.
    A little tired? Still feeling a little warm?
    Not really.
    Okay, glad to hear it. Alright, let's get your vitals. (pause) Heart rate is 86. SpO2 is 99, that looks good. Respiratory rate is 21. Temperature is 99.8. Blood pressure is 119 over 70. You still look to have a slight fever, let's hope that goes back down.
    Oh, well I feel okay.
    We will keep an eye on it but I'm not too concerned.
    Can I get some help in here?
    Ah, that's another patient, uh, do you need anything else at the moment Ms. Jackson?
    No, I'll just try to get some rest.
    Perfect, I will be back in a little bit. Thanks.
    Thank you.
    [end]
    """
    return transcript

def get_test_transcript_4():
    transcript = """
    [transcript]
    Hi, Ms. Jackson, sorry about earlier.
    Oh, it's fine.
    Can you confirm your date of birth for me?
    July third, 1980.
    Great, thank you. Feeling okay? Did you get some rest?
    Oh yes, I got some sleep.
    Great. Let me grab your vitals... (pause) Heart rate, 88. SpO2 is 99. Respiratory rate is 20. Temperature is 98.7. Blood pressure is 117 over 67. Alright, looks like your fever is going back down.
    I wonder what that was about.
    I'll make sure to make a note of it. Is it okay if I check on your bleeding?
    Sure.
    Okay, bleeding looks like it has really slowed down. That's looking good.
    Does that mean I can go home?
    Haha, not quite yet. They are going to want to keep an eye on you for a little bit longer.
    I really want to go home.
    Well, let me see what information I can get for you. I'll be turning over the shift to Sara so she will be back in here in a little while, I hope you have a good night.
    Okay, thank you. You too.
    [end]
    """
    return transcript

def get_test_transcript_5():
    transcript = """
    [transcript]
    THIS DOCUMENT WILL BE MOCKED TO BE OLDER THAN 12 HOURS AGO AND SHOULD NOT APPEAR IN PROMPT CONTENT
    [end]
    """
    return transcript