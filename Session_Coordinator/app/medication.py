from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openemr import connector, fhir
from typing import Annotated
from .middleware.wlc_auth import WlcUser, auth_middleware

router = APIRouter(prefix = "/medication")
fhirClient = fhir.FhirConnector(connector._requestEMR)

@router.get("/list")
def list_medications(patient_UUID:str, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient
    r = fhirClient.getMedicationForPatient(user, patient_UUID)
    return r
