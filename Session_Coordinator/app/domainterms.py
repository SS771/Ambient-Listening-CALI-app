import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openemr import connector, fhir
from typing import Annotated, List
from .middleware.wlc_auth import WlcUser, auth_middleware
import requests

import unittest
from unittest.mock import patch

class DomainTermList(BaseModel):
    vocabulary: list[str]

router = APIRouter(prefix = "/vocabulary")

'''
domain terms in ambient:
    clinic : N nurse/dr/student names - every session
    patient file : drugs/patient name - per-visitor
'''

domain_term_url = os.environ.get("domain_term_url","https://api-wlc-staging.watsonmedia.ibm.com/training/v1")

def _getDtId(user: WlcUser):#FIXME unique_term_id should be the patient invalidating the WlcUser dep; requiring passing patient uuid
    shared_term_id = "ibm_cali_demo"
    #unique_term_id = user.username 
    return shared_term_id#f"{shared_term_id},{unique_term_id}"

def _getApikey():
    return os.environ["captioning_apikey"]

def _getExistingDomainTerms(dtId: str, apikey:str):
    rqUrl = f"{domain_term_url}/domain_terms/model/{dtId}"
    rqHeader = {
        "Authorization": f"apikey {apikey}"
        , "Content-Type": "application/json"
    }
    rqRes = requests.get(rqUrl, headers = rqHeader)
    #print(rqRes)
    return rqRes.json()

def _mkDts(term, modelId, rank):
    return {"term":term, "model_id":modelId, "rank":rank}

def _postNewDomainTerms(dtId:str, apikey:str, terms:list[str]):
    rqUrl = f"{domain_term_url}/domain_terms/"
    rqHeader = {
        "Authorization": f"apikey {apikey}"
        , "Content-Type": "application/json"
    }
    rqRes = requests.post(rqUrl, headers = rqHeader, json = {"domain_terms":[_mkDts(dt, dtId, "10") for dt in terms]})
    #print(rqRes)
    return rqRes.json()

@router.get("/list")
def listDomainTerms(user: Annotated[WlcUser, Depends(auth_middleware)]):
    domainterms = _getExistingDomainTerms(_getDtId(user), _getApikey())
    return domainterms

@router.post("/terms") #FIXME - if _getDtId returns comma sep values the created terms will have the comma in the model id!
def addDomainTerms(terms: DomainTermList, user: Annotated[WlcUser, Depends(auth_middleware)]):
    dtPost = _postNewDomainTerms(_getDtId(user), _getApikey(), terms.vocabulary) 
    return dtPost