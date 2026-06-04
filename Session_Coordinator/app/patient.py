from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openemr import connector
from typing import Union, Annotated
from .middleware.wlc_auth import WlcUser, auth_middleware

router = APIRouter(prefix = "/patient")

class PatientData(BaseModel): # https://fastapi.tiangolo.com/tutorial/body/#use-the-model
    fname: str
    lname: str
    title: Union[str, None] = None
    mname: Union[str, None] = None
    street: Union[str, None] = None
    postal_code: Union[str, None] = None
    city: Union[str, None] = None
    state: Union[str, None] = None
    country_code: Union[str, None] = None
    phone_contact: Union[str, None] = None
    DOB: str
    sex: str
    race: Union[str, None] = None
    ethnicity: Union[str, None] = None

@router.get("/list")
def list_patients(user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient
    r = connector.listPatientsOpenEMR(user.emr_token)
    return r

@router.get("/{patient_id}")
def get_patient(patient_id : str, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient/{puuid}
    r = connector.getPatientByUUID(user.emr_token, patient_id)
    return r

@router.post("/create")
def new_patient(patient_data: PatientData, user: Annotated[WlcUser, Depends(auth_middleware)]): #/api/patient
    pd_dict = patient_data.model_dump(exclude=["fname", "lname", "DOB", "sex"], exclude_defaults = True, exclude_unset= True)
    r = connector.createPatient(user.emr_token, patient_data.fname, patient_data.lname, patient_data.DOB, patient_data.sex, **pd_dict)
    return r
