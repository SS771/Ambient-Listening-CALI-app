from app.middleware.wlc_auth import WlcUser
class FhirConnector:
    def __init__(self, network, *args, **kwargs):
        '''
                #Set network to a function accepting the following params; see connector._requestEMR for example implementor
                token:"emr auth token"
                , url:"'/api/endpoint' to append to openEMR_host"
                , methodName: "method of request, default GET" = "GET"
                , moreHeaders:"dict() additional headers or overwrites" = {}
                , requestParams:"additional parameters for request method" = {}
                , returnRawResponse:"don't extract/parse response if True" = False

        FhirConnector( myNetworkRequestFunction )
        '''
        self.network = network
    def getMedicationForPatient(self, user:WlcUser, patientUUID:str): #/fhir/Medication is useless; for x in entry: medName = x.resource.medicationCodeableConcept.text
        return self.network(
            user.emr_token
            ,f"/fhir/MedicationRequest?patient={patientUUID}"
            ,"GET"
        )