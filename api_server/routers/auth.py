# api_server/routers/auth.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import requests
import os
import time
from supabase import create_client, Client

router = APIRouter()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", SUPABASE_ANON_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

@router.get("/auth/callback")
async def auth_callback(request: Request):
    # Check for error in query params
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    if error:
        # Optionally log or display the error
        return {"success": False, "error": error_description or error}

    code = request.query_params.get("code")
    slack_user_id = request.query_params.get("slack_user_id")  # Slack user_id passed in redirect_to

    if not code or not slack_user_id:
        raise HTTPException(status_code=400, detail="Missing code or slack_user_id")

    # The redirect_uri for the token exchange must match exactly what was used in the authorize step (without the query param)
    redirect_uri = "https://b8cb-2405-201-6009-a0af-4d52-e4eb-cbe1-c001.ngrok-free.app/auth/callback"
    # Exchange code for session with Supabase
    resp = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=oauth",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"auth_code": code, "redirect_uri": redirect_uri}
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    session = resp.json()
    # Extract info
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expires_in = session.get("expires_in")
    expires_at = int(time.time()) + int(expires_in) if expires_in else None
    user = session.get("user", {})
    supabase_user_id = user.get("id")

    # Store in Supabase table
    supabase.table("slack_sessions").upsert({
        "slack_user_id": slack_user_id,
        "supabase_user_id": supabase_user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at
    }).execute()

    # Optionally, notify the user in Slack (using Slack API)
    # Redirect to a "success" page or close the window
    return RedirectResponse("https://slack.com/app_redirect")  # or your own page


# api_server/routers/auth.py
@router.get("/auth/slack")
async def auth_slack(user_id: str):
    # Construct Supabase OAuth URL with slack_user_id as a query param in redirect_to
    redirect_uri = f"https://b8cb-2405-201-6009-a0af-4d52-e4eb-cbe1-c001.ngrok-free.app/auth/callback?slack_user_id={user_id}"
    supabase_oauth_url = (
        f"{SUPABASE_URL}/auth/v1/authorize"
        f"?provider=slack_oidc"
        f"&redirect_to={redirect_uri}"
    )
    return RedirectResponse(supabase_oauth_url)

@router.get("/api/session/{user_id}")
async def check_session(user_id: str):
    result = supabase.table("slack_sessions").select("*").eq("slack_user_id", user_id).execute()
    sessions = result.data
    if not sessions or len(sessions) == 0:
        return {"authenticated": False}
    session = sessions[0]
    expires_at = session.get("expires_at")
    if expires_at and int(expires_at) < int(time.time()):
        return {"authenticated": False}
    return {"authenticated": True}

@router.post("/api/save_session")
async def save_session(request: Request):
    import time
    try:
        data = await request.json()
        print("Received data for save_session:", data)
        slack_user_id = data.get("slack_user_id")
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_at = data.get("expires_at")
        expires_in = data.get("expires_in")

        if not slack_user_id or not access_token:
            return JSONResponse({"success": False, "error": "Missing slack_user_id or access_token"}, status_code=400)

        # Calculate expires_at if not provided
        if not expires_at and expires_in:
            expires_at = int(time.time()) + int(expires_in)
        elif expires_at:
            expires_at = int(expires_at)
        else:
            expires_at = None

        # Store in Supabase table
        result = supabase.table("slack_sessions").upsert({
            "slack_user_id": slack_user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }).execute()
        print("Upsert result:", result)

        # Check for errors in result
        if hasattr(result, 'error') and result.error:
            return JSONResponse({"success": False, "error": str(result.error)}, status_code=500)

        return {"success": True}
    except Exception as e:
        import traceback
        print("Exception in save_session:", traceback.format_exc())
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)