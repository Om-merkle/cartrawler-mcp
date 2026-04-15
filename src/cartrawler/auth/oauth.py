"""
OAuth 2.0 Authorization Code + PKCE for ChatGPT Apps UI
=========================================================
Implements the minimal OAuth 2.0 AS required by MCP / ChatGPT Apps:

  GET  /.well-known/oauth-authorization-server  → RFC 8414 metadata
  GET  /mcp/.well-known/oauth-protected-resource → RFC 9728 resource metadata
  POST /oauth/register                           → dynamic client registration
  GET  /oauth/authorize                          → login + register form
  POST /oauth/authorize?mode=login               → verify credentials, issue code
  POST /oauth/authorize?mode=register            → create account, issue code
  POST /oauth/token                              → exchange code for JWT access token

All tokens are our existing JWT tokens — OAuth is just a wrapper around them.
"""
from __future__ import annotations

import base64
import hashlib
import html
import secrets
import time
from urllib.parse import urlencode

from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from cartrawler.auth.jwt_handler import create_access_token, create_refresh_token
from cartrawler.auth.password import hash_password, verify_password
from cartrawler.config import settings
from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import User

# ─────────────────────────────────────────────────────────────────────────────
# In-memory stores (single-process — fine for Render free tier)
# ─────────────────────────────────────────────────────────────────────────────

_auth_codes: dict[str, dict] = {}
_clients:    dict[str, dict] = {}


def _base_url() -> str:
    return str(settings.mcp_server_base_url).rstrip("/")


def _next_user_id(existing_ids: list[str]) -> str:
    if not existing_ids:
        return "U1101"
    nums = [int(uid[1:]) for uid in existing_ids if uid.startswith("U") and uid[1:].isdigit()]
    return f"U{max(nums) + 1}" if nums else "U1101"


# ─────────────────────────────────────────────────────────────────────────────
# Discovery endpoints
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


async def oauth_protected_resource(_request: Request) -> JSONResponse:
    """RFC 9728 OAuth Protected Resource Metadata."""
    base = _base_url()
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
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
# Login + Register HTML
# ─────────────────────────────────────────────────────────────────────────────

_AUTH_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CarTrawler — Account</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f0f4ff;min-height:100vh;display:flex;
      align-items:center;justify-content:center;padding:16px}}
.card{{background:#fff;border-radius:16px;padding:36px 32px;
       width:100%;max-width:440px;box-shadow:0 4px 24px rgba(0,0,0,.12)}}
.logo{{text-align:center;margin-bottom:24px}}
.logo h1{{font-size:22px;color:#1a1a2e;font-weight:700}}
.logo p{{color:#666;font-size:13px;margin-top:4px}}
.tabs{{display:flex;border-bottom:2px solid #eee;margin-bottom:24px}}
.tab{{flex:1;padding:10px;text-align:center;font-size:14px;font-weight:600;
      color:#999;cursor:pointer;border-bottom:2px solid transparent;
      margin-bottom:-2px;transition:all .2s}}
.tab.active{{color:#4f7df0;border-bottom-color:#4f7df0}}
.panel{{display:none}}.panel.active{{display:block}}
label{{display:block;font-size:13px;font-weight:600;color:#444;margin-bottom:5px}}
input[type=text],input[type=email],input[type=password],input[type=tel]{{
  width:100%;padding:11px 13px;border:1.5px solid #ddd;border-radius:8px;
  font-size:14px;outline:none;transition:border-color .2s}}
input:focus{{border-color:#4f7df0}}
.field{{margin-bottom:15px}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.msg{{border-radius:8px;padding:10px 13px;font-size:13px;margin-bottom:14px}}
.error{{background:#fff0f0;color:#c00;border:1px solid #fcc}}
.success{{background:#f0fff4;color:#080;border:1px solid #cfc}}
button{{width:100%;padding:12px;background:#4f7df0;color:#fff;border:none;
        border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;
        transition:background .2s;margin-top:4px}}
button:hover{{background:#3d6ae0}}
.note{{text-align:center;color:#aaa;font-size:11px;margin-top:16px;line-height:1.5}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>🚗 CarTrawler</h1>
    <p>Connect your account to ChatGPT</p>
  </div>

  <div class="tabs">
    <div class="tab {login_active}" onclick="show('login')">Sign In</div>
    <div class="tab {register_active}" onclick="show('register')">Create Account</div>
  </div>

  <!-- LOGIN PANEL -->
  <div id="login" class="panel {login_active}">
    {login_msg}
    <form method="POST" action="/oauth/authorize?mode=login">
      <input type="hidden" name="client_id"             value="{client_id}">
      <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
      <input type="hidden" name="state"                 value="{state}">
      <input type="hidden" name="code_challenge"        value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <div class="field">
        <label>Email</label>
        <input type="email" name="email" placeholder="you@example.com"
               required autocomplete="email">
      </div>
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" placeholder="••••••••"
               required autocomplete="current-password">
      </div>
      <button type="submit">Sign in &rarr;</button>
    </form>
  </div>

  <!-- REGISTER PANEL -->
  <div id="register" class="panel {register_active}">
    {register_msg}
    <form method="POST" action="/oauth/authorize?mode=register">
      <input type="hidden" name="client_id"             value="{client_id}">
      <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
      <input type="hidden" name="state"                 value="{state}">
      <input type="hidden" name="code_challenge"        value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <div class="field">
        <label>Full Name *</label>
        <input type="text" name="name" placeholder="Rahul Sharma" required>
      </div>
      <div class="row">
        <div class="field">
          <label>Email *</label>
          <input type="email" name="email" placeholder="you@example.com" required autocomplete="email">
        </div>
        <div class="field">
          <label>Phone</label>
          <input type="tel" name="phone" placeholder="+91 98765 43210">
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label>Password *</label>
          <input type="password" name="password" placeholder="Min 6 chars" required>
        </div>
        <div class="field">
          <label>Home City</label>
          <input type="text" name="home_city" placeholder="Mumbai">
        </div>
      </div>
      <button type="submit">Create account &rarr;</button>
    </form>
  </div>

  <p class="note">CarTrawler will book cars &amp; manage your account via ChatGPT.</p>
</div>
<script>
function show(tab) {{
  document.querySelectorAll('.tab,.panel').forEach(function(el) {{
    el.classList.remove('active');
  }});
  document.querySelectorAll('#'+tab+',.tab:nth-child('+(tab==='login'?1:2)+')').forEach(function(el) {{
    el.classList.add('active');
  }});
}}
</script>
</body>
</html>
"""


def _render(
    active: str = "login",
    login_msg: str = "",
    register_msg: str = "",
    **hidden: str,
) -> HTMLResponse:
    ctx = {k: html.escape(v) for k, v in hidden.items()}
    ctx["login_active"]    = "active" if active == "login"    else ""
    ctx["register_active"] = "active" if active == "register" else ""
    ctx["login_msg"]       = login_msg
    ctx["register_msg"]    = register_msg
    return HTMLResponse(_AUTH_HTML.format(**ctx))


def _msg(text: str, kind: str = "error") -> str:
    return f'<div class="msg {kind}">{html.escape(text)}</div>'


# ─────────────────────────────────────────────────────────────────────────────
# Shared: issue auth code after successful auth
# ─────────────────────────────────────────────────────────────────────────────

def _issue_code(user: User, redirect_uri: str, state: str,
                code_challenge: str, code_challenge_method: str, client_id: str) -> str:
    access_token  = create_access_token(user.user_id)
    refresh_token = create_refresh_token(user.user_id)
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "user_id":              user.user_id,
        "access_token":         access_token,
        "refresh_token":        refresh_token,
        "redirect_uri":         redirect_uri,
        "code_challenge":       code_challenge,
        "code_challenge_method": code_challenge_method,
        "client_id":            client_id,
        "expires_at":           time.time() + 600,
    }
    return code


# ─────────────────────────────────────────────────────────────────────────────
# GET /oauth/authorize  — show login/register form
# POST /oauth/authorize?mode=login    — sign in existing user
# POST /oauth/authorize?mode=register — create new user
# ─────────────────────────────────────────────────────────────────────────────

async def oauth_authorize(request: Request) -> HTMLResponse | RedirectResponse:
    mode = request.query_params.get("mode", "login")

    if request.method == "GET":
        p = request.query_params
        return _render(
            active="login",
            client_id=p.get("client_id", ""),
            redirect_uri=p.get("redirect_uri", ""),
            state=p.get("state", ""),
            code_challenge=p.get("code_challenge", ""),
            code_challenge_method=p.get("code_challenge_method", "S256"),
        )

    form = await request.form()

    def hidden() -> dict:
        return {
            "client_id":             str(form.get("client_id", "")),
            "redirect_uri":          str(form.get("redirect_uri", "")),
            "state":                 str(form.get("state", "")),
            "code_challenge":        str(form.get("code_challenge", "")),
            "code_challenge_method": str(form.get("code_challenge_method", "S256")),
        }

    h = hidden()

    def _redirect(user: User) -> RedirectResponse:
        code = _issue_code(user, **h)
        params = {"code": code}
        if h["state"]:
            params["state"] = h["state"]
        return RedirectResponse(f"{h['redirect_uri']}?{urlencode(params)}", status_code=302)

    # ── LOGIN ─────────────────────────────────────────────────────────────────
    if mode == "login":
        email    = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))

        if not email or not password:
            return _render("login", login_msg=_msg("Email and password are required."), **h)

        try:
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(User).where(User.email == email))
                user: User | None = r.scalar_one_or_none()
        except Exception as exc:
            return _render("login", login_msg=_msg(f"Database error: {exc}. Please try again."), **h)

        if not user or not verify_password(password, str(user.hashed_password)):
            return _render("login", login_msg=_msg("Invalid email or password."), **h)

        if not bool(user.is_active):
            return _render("login", login_msg=_msg("Account inactive. Contact support."), **h)

        return _redirect(user)

    # ── REGISTER ──────────────────────────────────────────────────────────────
    if mode == "register":
        name      = str(form.get("name", "")).strip()
        email     = str(form.get("email", "")).strip()
        password  = str(form.get("password", ""))
        phone     = str(form.get("phone", "")).strip() or None
        home_city = str(form.get("home_city", "")).strip() or None

        if not name or not email or not password:
            return _render("register",
                           register_msg=_msg("Name, email and password are required."), **h)
        if len(password) < 6:
            return _render("register",
                           register_msg=_msg("Password must be at least 6 characters."), **h)

        try:
            async with AsyncSessionLocal() as db:
                # Check duplicate email
                r = await db.execute(select(User).where(User.email == email))
                if r.scalar_one_or_none():
                    return _render("register",
                                   register_msg=_msg("An account with this email already exists. Please sign in."), **h)

                # Generate user ID
                all_ids_r = await db.execute(select(User.user_id))
                all_ids = [row[0] for row in all_ids_r.fetchall()]
                user_id = _next_user_id(all_ids)

                new_user = User(
                    user_id=user_id,
                    name=name,
                    email=email,
                    hashed_password=hash_password(password),
                    phone=phone,
                    home_city=home_city,
                    loyalty_tier="Bronze",
                    loyalty_points=0,
                    is_active=True,
                    is_verified=False,
                )
                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
        except Exception as exc:
            return _render("register",
                           register_msg=_msg(f"Database error: {exc}. Run /admin/seed first to initialise the database."), **h)

        return _redirect(new_user)

    return _render("login", login_msg=_msg("Unknown mode."), **h)


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

    grant_type    = str(body.get("grant_type", ""))
    code          = str(body.get("code", ""))
    redirect_uri  = str(body.get("redirect_uri", ""))
    code_verifier = str(body.get("code_verifier", ""))

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    stored = _auth_codes.pop(code, None)
    if not stored:
        return JSONResponse({"error": "invalid_grant",
                             "error_description": "Code not found or already used"}, status_code=400)

    if stored["expires_at"] < time.time():
        return JSONResponse({"error": "invalid_grant",
                             "error_description": "Code expired"}, status_code=400)

    if stored["redirect_uri"] != redirect_uri:
        return JSONResponse({"error": "invalid_grant",
                             "error_description": "redirect_uri mismatch"}, status_code=400)

    # Verify PKCE
    if stored.get("code_challenge"):
        if not code_verifier:
            return JSONResponse({"error": "invalid_grant",
                                 "error_description": "code_verifier required"}, status_code=400)
        digest   = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if computed != stored["code_challenge"]:
            return JSONResponse({"error": "invalid_grant",
                                 "error_description": "PKCE verification failed"}, status_code=400)

    return JSONResponse({
        "access_token":  stored["access_token"],
        "refresh_token": stored["refresh_token"],
        "token_type":    "bearer",
        "expires_in":    settings.jwt_access_token_expire_minutes * 60,
    })
