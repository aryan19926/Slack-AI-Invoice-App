import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")

def is_user_authenticated(slack_user_id):
    # Call the FastAPI endpoint to check session
    try:
        resp = requests.get(f"{API_SERVER_URL}/api/session/{slack_user_id}")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("authenticated", False)
        return False
    except Exception:
        return False

def store_user_in_supabase(slack_user_id, email):
    if not is_user_authenticated(slack_user_id):
        supabase.table("users").insert({"slack_user_id": slack_user_id, "email": email}).execute()

def get_slack_user_email(client, user_id):
    user_info = client.users_info(user=user_id)
    return user_info['user']['profile']['email'] 