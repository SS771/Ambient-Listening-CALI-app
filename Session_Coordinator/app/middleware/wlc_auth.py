from typing import Annotated
import os, json
from datetime import datetime, timedelta, timezone
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openemr import connector

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth")#https://fastapi.tiangolo.com/tutorial/security/first-steps/#use-it
JWT_SECRET_KEY = os.environ.get("jwt_secret_key", "")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
#send signed jwt to frontend -> frontend opens websocket w/ jwt -> backend can get client id & session info from jwt
def _createJWT(data: dict):
    toEncode = data.copy()
    expireTime = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    toEncode.update({"exp":expireTime})
    return jwt.encode(toEncode, JWT_SECRET_KEY, algorithm = JWT_ALGORITHM)

def _decodeJWT(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        print("exception decoding jwt token=", token, ":: exception info=", e)
    return None

def _getClientApikey():
    return os.environ["captioning_apikey"]

def _isUserAllowed(userName):
    if userName in os.environ["allowed_users"].split(","):
        return True
    return False

class WlcUser(BaseModel):
    username: str
    emr_token: str

def auth_middleware(X_Watson_Authorization_Token : Annotated[str, Depends(oauth2_scheme)]):
    try:
        jwtData = _decodeJWT(X_Watson_Authorization_Token)
        user = jwtData["x-wlc-user"]
        emr_token = jwtData["x-emr-token"]
        wlcUser = WlcUser(username=user, emr_token=emr_token)
        print("auth_middleware : OK")
        return wlcUser
    except Exception as e:
        print("Exception in auth_middleware::", e)
    print("auth_middleware : REJECT")
    raise HTTPException(status_code=401, detail="Unable to authenticate")

@router.post("/auth")
def authorizeToAppWithPassword(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ):
    userName = form_data.username
    userPass = form_data.password
    try:
        token = connector.getOpenEMRToken_PasswordGrant(openEMR_username=userName, openEMR_password=userPass)
        return {
            "access_token":_createJWT(
                {
                    "x-wlc-user":userName
                    , "x-emr-token": token
                }
            )
            , "token_type":"bearer"
        }
    except Exception as e:
        print("authorizeToAppWithPassword : ERROR :", e)
    raise HTTPException(status_code=401, detail="Unable to authenticate")


class Test_JwtCreateDecode(unittest.TestCase):
    def test_createJWT(self):
        new_token = _createJWT({"x-wlc-apikey":"test-api-key", "x-wlc-user":"test@ibm.com"})
        print(new_token)
        self.assertTrue(len(new_token) > 100)
        self.assertIn("ey", new_token)

    def test_decodeJWT(self):
        new_token = _createJWT({"x-wlc-apikey":"test-api-key", "x-wlc-user":"test@ibm.com"})
        self.assertTrue(len(new_token) > 100)
        jwt_data = _decodeJWT(new_token)
        self.assertEqual(jwt_data["x-wlc-apikey"], "test-api-key")
        self.assertEqual(jwt_data["x-wlc-user"], "test@ibm.com")