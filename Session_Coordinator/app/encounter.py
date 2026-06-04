from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openemr import connector
from typing import Annotated
from .middleware.wlc_auth import WlcUser, auth_middleware

router = APIRouter(prefix = "/encounter")

class EncounterData(BaseModel): # https://fastapi.tiangolo.com/tutorial/body/#use-the-model
    patient_id : str

@router.post("/create")
def new_encounter(encounter_data : EncounterData, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{patient_id}/encounter
    print("encounter create called")
    print(f"patient: {encounter_data.patient_id}")
    ed_dict = encounter_data.model_dump(exclude=["patient_id"], exclude_defaults = True, exclude_unset= True)
    r = connector.createEncounter(user.emr_token, encounter_data.patient_id, **ed_dict)
    return r

@router.get("/patient/{patient_uuid}/list")
def list_encounters(patient_uuid:str, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{puuid}/encounter
    return connector.listEncountersOpenEMR(user.emr_token, patient_uuid)

@router.get("/{encounter_id}/patient/{patient_id}/vitals")
def getVitalsForEncounter(encounter_id:str, patient_id:str, user: Annotated[WlcUser, Depends(auth_middleware)]):
    return connector.getVitalsOpenEMR(user.emr_token, patient_id, encounter_id)