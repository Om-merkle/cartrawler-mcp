"""
OAuth 2.0 Authorization Code + PKCE for ChatGPT Apps UI
=========================================================
Implements the minimal OAuth 2.0 AS required by MCP / ChatGPT Apps:

  GET  /.well-known/oauth-authorization-server  → RFC 8414 metadata
  POST /oauth/register                           → dynamic client registration
  GET  /oauth/authorize                          → show login form
  POST /oauth/authorize                          → verify credentials, issue code, redirect
  POST /oauth/token                              → exchange code for JWT access token

All tokens are our existing JWT tokens — OAuth is just a wrapper around them.
"""
from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from cartrawler.auth.jwt_handler import create_access_token, create_refresh_token
from cartrawler.auth.password import verify_password
from cartrawler.config import settings
from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import User

# ─────────────────────────────────────────────────────────────────────────────
# In-memory stores (single-process — fine for Render free tier)
# ─────────────────────────────────────────────────────────────────────────────

# auth_codes[code] = {user_id, access_token, refresh_token,
#                     redirect_uri, code_challenge, client_id, expires_at}
_auth_codes: dict[str, dict[str, Any]] = {}

# registered_clients[client_id] = {client_id, redirect_uris, ...}
_clients: dict[str, dict[str, Any]] = {}


def _base_url() -> str:
    return str(settings.mcp_server_base_url).rstrip("/")


# ─────────────────────────────────────────────────────────────────────────────
# GET /.well-known/oauth-authorization-server
# ─────────────────────────────────────────────────────────────────────────────

async def oauth_metadata(_request: Request) -> JSONResponse:
    """RFC 8414 Authorization Server Metadata."""
    base = _base_url()
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "scopes_supported": ["openid"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /oauth/register  (dynamic client registration — RFC 7591)
# ─────────────────────────────────────────────────────────────────────────────

async def oauth_register(request: Request) -> JSONResponse:
    """Accept any client registration (open registration for ChatGPT)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    client_id = secrets.token_urlsafe(16)
    client_info = {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "redirect_uris": body.get("redirect_uris", []),
        "client_name": body.get("client_name", "ChatGPT"),
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    }
    _clients[client_id] = client_info
    return JSONResponse(client_info, status_code=201)


# ─────────────────────────────────────────────────────────────────────────────
# GET /oauth/authorize  — show login form
# POST /oauth/authorize — verify credentials + issue code
# ─────────────────────────────────────────────────────────────────────────────

_LOGIN_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CarTrawler — Sign In</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f0f4ff;min-height:100vh;display:flex;
        align-items:center;justify-content:center}}
  .card{{background:#fff;border-radius:16px;padding:40px 36px;
         width:100%;max-width:420px;box-shadow:0 4px 24px rgba(0,0,0,.12)}}
  .logo{{text-align:center;margin-bottom:28px}}
  .logo h1{{font-size:24px;color:#1a1a2e;font-weight:700}}
  .logo p{{color:#666;font-size:14px;margin-top:4px}}
  label{{display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:6px}}
  input[type=email],input[type=password]{{
    width:100%;padding:12px 14px;border:1.5px solid #ddd;border-radius:8px;
    font-size:15px;outline:none;transition:border-color .2s}}
  input:focus{{border-color:#4f7df0}}
  .field{{margin-bottom:18px}}
  .error{{background:#fff0f0;color:#d00;border:1px solid #fcc;
          border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:16px}}
  button{{width:100%;padding:13px;background:#4f7df0;color:#fff;
          border:none;border-radius:8px;font-size:16px;font-weight:600;
          cursor:pointer;transition:background .2s}}
  button:hover{{background:#3d6ae0}}
  .note{{text-align:center;color:#888;font-size:12px;margin-top:20px}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>🚗 CarTrawler</h1>
    <p>Sign in to your CarTrawler account</p>
  </div>
  {error_block}
  <form method="POST" action="/oauth/authorize">
    <input type="hidden" name="client_id"             value="{client_id}">
    <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
    <input type="hidden" name="state"                 value="{state}">
    <input type="hidden" name="code_challenge"        value="{code_challenge}">
    <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
    <div class="field">
      <label for="email">Email</label>
      <input type="email" id="email" name="email"
             placeholder="you@example.com" required autocomplete="email">
    </div>
    <div class="field">
      <label for="password">Password</label>
      <input type="password" id="password" name="password"
             placeholder="••••••••" required autocomplete="current-password">
    </div>
    <button type="submit">Sign in &rarr;</button>
  </form>
  <p class="note">CarTrawler will access your account on ChatGPT's behalf.</p>
</div>
</body>
</html>
"""


async def oauth_authorize(request: Request) -> HTMLResponse | RedirectResponse:
    if request.method == "GET":
        p = request.query_params
        error_block = ""
        return HTMLResponse(_LOGIN_HTML.format(
            client_id=html.escape(p.get("client_id", "")),
            redirect_uri=html.escape(p.get("redirect_uri", "")),
            state=html.escape(p.get("state", "")),
            code_challenge=html.escape(p.get("code_challenge", "")),
            code_challenge_method=html.escape(p.get("code_challenge_method", "S256")),
            error_block=error_block,
        ))

    # POST — process login
    form = await request.form()
    email            = str(form.get("email", "")).strip()
    password         = str(form.get("password", ""))
    client_id        = str(form.get("client_id", ""))
    redirect_uri     = str(form.get("redirect_uri", ""))
    state            = str(form.get("state", ""))
    code_challenge   = str(form.get("code_challenge", ""))
    code_challenge_method = str(form.get("code_challenge_method", "S256"))

    def _error(msg: str) -> HTMLResponse:
        block = f'<div class="error">{html.escape(msg)}</div>'
        return HTMLResponse(_LOGIN_HTML.format(
            client_id=html.escape(client_id),
            redirect_uri=html.escape(redirect_uri),
            state=html.escape(state),
            code_challenge=html.escape(code_challenge),
            code_challenge_method=html.escape(code_challenge_method),
            error_block=block,
        ))

    if not email or not password:
        return _error("Email and password are required.")

    # Verify credentials
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.email == email))
        user: User | None = r.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        return _error("Invalid email or password.")

    if not user.is_active:
        return _error("Account is inactive. Please contact support.")

    # Issue JWT tokens
    access_token  = create_access_token(user.user_id)
    refresh_token = create_refresh_token(user.user_id)

    # Store auth code
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "user_id":      user.user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "client_id":    client_id,
        "expires_at":   time.time() + 600,  # 10 min
    }

    # Redirect back to ChatGPT
    params = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(
        f"{redirect_uri}?{urlencode(params)}",
        status_code=302,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /oauth/token
# ─────────────────────────────────────────────────────────────────────────────

async def oauth_token(request: Request) -> JSONResponse:
    """Exchange authorization code for JWT access token."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_request"}, status_code=400)
    else:
        form = await request.form()
        body = dict(form)

    grant_type    = body.get("grant_type", "")
    code          = body.get("code", "")
    redirect_uri  = body.get("redirect_uri", "")
    code_verifier = body.get("code_verifier", "")

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    stored = _auth_codes.pop(str(code), None)
    if not stored:
        return JSONResponse({"error": "invalid_grant", "error_description": "Code not found or already used"}, status_code=400)

    if stored["expires_at"] < time.time():
        return JSONResponse({"error": "invalid_grant", "error_description": "Code expired"}, status_code=400)

    if stored["redirect_uri"] != str(redirect_uri):
        return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch"}, status_code=400)

    # Verify PKCE
    if stored.get("code_challenge"):
        if not code_verifier:
            return JSONResponse({"error": "invalid_grant", "error_description": "code_verifier required"}, status_code=400)
        digest = hashlib.sha256(str(code_verifier).encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if computed != stored["code_challenge"]:
            return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)

    return JSONResponse({
        "access_token":  stored["access_token"],
        "refresh_token": stored["refresh_token"],
        "token_type":    "bearer",
        "expires_in":    settings.jwt_access_token_expire_minutes * 60,
    })
