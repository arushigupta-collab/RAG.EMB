"""Simple login gate for the sandbox.

Verifies a single configured email/password on the server so the credential is
never shipped in the client bundle. This gates the UI; for hardened access behind
the public URL, also enable the Caddy basic-auth layer (see the deployment plan).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(req: LoginRequest) -> dict:
    # If no credential is configured, deny everything (prevents an empty-string bypass).
    if not settings.auth_email or not settings.auth_password:
        raise HTTPException(status_code=503, detail="Login is not configured.")
    if (
        req.email.strip().lower() == settings.auth_email.strip().lower()
        and req.password == settings.auth_password
    ):
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid email or password.")
