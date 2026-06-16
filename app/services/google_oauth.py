from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleUserInfo(BaseModel):
    sub: str
    email: str
    email_verified: bool = False
    name: str | None = None


def build_authorization_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_userinfo(code: str, redirect_uri: str) -> GoogleUserInfo:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        return GoogleUserInfo.model_validate(userinfo_resp.json())
