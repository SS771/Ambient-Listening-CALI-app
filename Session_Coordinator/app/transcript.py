from fastapi import APIRouter, Depends
from typing import Annotated
from openemr import connector
from pydantic import BaseModel
from .middleware.wlc_auth import WlcUser, auth_middleware

router = APIRouter(prefix = "/transcript")

class PatientTranscript(BaseModel):
    patient_id: str
    document: str
    file_name: str

@router.post("/create")
def add_patient_transcript(patientTranscript: PatientTranscript, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{pid}/document
    connector.saveTranscriptToOpenEMR(user.emr_token, patientTranscript.document, patientTranscript.patient_id, patientTranscript.file_name)

@router.get("/patient/{patient_id}/document/{document_id}")
def get_patient_transcript(patient_id: str, document_id: str, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{pid}/document/{did}
    r = connector.getDocumentOpenEMR(user.emr_token, patient_id, document_id)
    return r

@router.post("/list")
def list_patient_transcripts(patient_id: str, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{pid}/document
    r = connector.listDocumentsOpenEMR(user.emr_token, patient_id)
    return r