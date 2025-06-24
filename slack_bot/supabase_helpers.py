import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_user_authenticated(slack_user_id):
    response = supabase.table("users").select("*").eq("slack_user_id", slack_user_id).execute()
    return len(response.data) > 0

def store_user_in_supabase(slack_user_id, email):
    if not is_user_authenticated(slack_user_id):
        supabase.table("users").insert({"slack_user_id": slack_user_id, "email": email}).execute()

def get_slack_user_email(client, user_id):
    user_info = client.users_info(user=user_id)
    return user_info['user']['profile']['email'] 