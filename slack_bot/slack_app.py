import os
from slack_bolt import App
from supabase_helpers import is_user_authenticated, store_user_in_supabase, get_slack_user_email
from llm import ask_gemini, extract_json_from_code_block, format_api_response
from upload_modal import open_invoice_upload_modal
from constants import LOADING_BLOCKS, NOT_HELPFUL_MODAL
import requests
import json
import os
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()


API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# --- In-memory store for user channel/thread mapping ---
user_context_map = {}
# --- End in-memory store ---

# --- In-memory store for uploaded files and user emails ---
uploaded_files = []
# --- End in-memory store ---

def get_login_url(user_id):
    redirect_to = f"https://b8cb-2405-201-6009-a0af-4d52-e4eb-cbe1-c001.ngrok-free.app/static/auth_callback.html?slack_user_id={user_id}"
    SUPABASE_URL = "https://mogwrjpbnxayfvppqgzb.supabase.co"  # <-- replace with your actual Supabase project URL
    return (
        f"{SUPABASE_URL}/auth/v1/authorize"
        f"?provider=slack_oidc"
        f"&redirect_to={redirect_to}"
    )

@app.message("")
def message_gemini(message, say, client):
    user = message['user']
   # In your message handler:
    if not is_user_authenticated(user):
        say(
            "Please log in to use this bot.",
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Log in"},
                            "url": get_login_url(user)
                        }
                    ]
                }
            ]
        )
        return
    text = message.get('text', '')
    thread_ts = message.get('thread_ts') or message.get('ts')
    channel = message['channel']
    context = None
    loading = client.chat_postMessage(
        channel=channel,
        blocks=LOADING_BLOCKS,
        thread_ts=thread_ts
    )
    loading_ts = loading['ts']
    gemini_response = ask_gemini(text, context)
    print("Gemini response:", gemini_response)
    action = None
    try:
        cleaned = extract_json_from_code_block(gemini_response)
        action = json.loads(cleaned)
    except Exception:
        action = None
    if isinstance(action, dict) and 'action' in action and 'params' in action:
        api_result = None
        try:
            if action['action'] == 'get_invoice':
                invoice_id = action['params'].get('invoice_id')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}?user_id={user_id}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Invoice not found."
                    except Exception:
                        error_msg = "Invoice not found."
                    api_result = {"error": error_msg}
            elif action['action'] == 'update_invoice_status':
                invoice_id = action['params'].get('invoice_id')
                status = action['params'].get('status')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}/status?user_id={user_id}"
                try:
                    r = requests.put(api_url, json={"status": status})
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Failed to update invoice status."
                    except Exception:
                        error_msg = "Failed to update invoice status."
                    api_result = {"error": error_msg}
            elif action['action'] == 'get_summary':
                params = action['params']
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/summary"
                if query:
                    api_url += f"?{query}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Could not get summary."
                    except Exception:
                        error_msg = "Could not get summary."
                    api_result = {"error": error_msg}
            elif action['action'] == 'search_invoices':
                params = action['params']
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/search"
                if query:
                    api_url += f"?{query}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Could not search invoices."
                    except Exception:
                        error_msg = "Could not search invoices."
                    api_result = {"error": error_msg}
            else:
                api_result = {"error": "Unknown action."}
        except Exception as e:
            api_result = {"error": f"API call failed: {str(e)}"}
        if api_result and "error" in api_result:
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                text=f"<@{user}> Sorry, {api_result['error']}",
                blocks=None
            )
        else:
            formatted_response = format_api_response(api_result, text)
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                blocks=formatted_response
            )
    else:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"<@{user}> Sorry, I couldn't understand your request.",
            blocks=None
        )

@app.event("app_mention")
def handle_app_mention(event, say, client):
    user = event['user']
    if not is_user_authenticated(user):
        say(
            "Please log in to use this bot.",
            blocks=[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Log in"},
                            "action_id": "login"
                        }
                    ]
                }
            ]
        )
        return
    text = event['text'].strip()
    thread_ts = event.get('thread_ts') or event.get('ts')
    channel = event['channel']
    text = text.replace(f"<@{os.environ.get('SLACK_BOT_ID')}>", "").strip()
    loading = client.chat_postMessage(
        channel=channel,
        blocks=LOADING_BLOCKS,
        thread_ts=thread_ts
    )
    loading_ts = loading['ts']
    gemini_response = ask_gemini(text)
    print("Gemini response:", gemini_response)
    action = None
    try:
        cleaned = extract_json_from_code_block(gemini_response)
        action = json.loads(cleaned)
    except Exception:
        action = None
    if isinstance(action, dict) and 'action' in action and 'params' in action:
        api_result = None
        try:
            if action['action'] == 'get_invoice':
                invoice_id = action['params'].get('invoice_id')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}?user_id={user_id}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Invoice not found."
                    except Exception:
                        error_msg = "Invoice not found."
                    api_result = {"error": error_msg}
            elif action['action'] == 'update_invoice_status':
                invoice_id = action['params'].get('invoice_id')
                status = action['params'].get('status')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}/status?user_id={user_id}"
                try:
                    r = requests.put(api_url, json={"status": status})
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Failed to update invoice status."
                    except Exception:
                        error_msg = "Failed to update invoice status."
                    api_result = {"error": error_msg}
            elif action['action'] == 'get_summary':
                params = action['params']
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/summary"
                if query:
                    api_url += f"?{query}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Could not get summary."
                    except Exception:
                        error_msg = "Could not get summary."
                    api_result = {"error": error_msg}
            elif action['action'] == 'search_invoices':
                params = action['params']
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/search"
                if query:
                    api_url += f"?{query}"
                try:
                    r = requests.get(api_url)
                    r.raise_for_status()
                    api_result = r.json()
                except requests.HTTPError:
                    try:
                        error_msg = r.json().get("error") or r.json().get("detail") or "Could not search invoices."
                    except Exception:
                        error_msg = "Could not search invoices."
                    api_result = {"error": error_msg}
            else:
                api_result = {"error": "Unknown action."}
        except Exception as e:
            api_result = {"error": f"API call failed: {str(e)}"}
        if api_result and "error" in api_result:
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                text=f"<@{user}> Sorry, {api_result['error']}",
                blocks=None
            )
        else:
            formatted_response = format_api_response(api_result, text)
            client.chat_update(
                channel=channel,
                ts=loading_ts,
                blocks=formatted_response
            )
    else:
        client.chat_update(
            channel=channel,
            ts=loading_ts,
            text=f"<@{user}> Sorry, I couldn't understand your request.",
            blocks=None
        )

@app.action("helpful")
def action_helpful(body, ack, say):
    ack()
    user_id = body['user']['id']
    thread_ts = None
    if 'message' in body and 'thread_ts' in body['message']:
        thread_ts = body['message']['thread_ts']
    elif 'message' in body and 'ts' in body['message']:
        thread_ts = body['message']['ts']
    say(f"<@{user_id}> Thank you for your feedback!", thread_ts=thread_ts)

@app.action("not-helpful")
def action_not_helpful(body, ack, client, say):
    ack()
    trigger_id = body.get("trigger_id")
    if trigger_id:
        client.views_open(
            trigger_id=trigger_id,
            view=NOT_HELPFUL_MODAL
        )

@app.action("login")
def handle_login(ack, body, client, say):
    ack()
    user_id = body['user']['id']
    email = get_slack_user_email(client, user_id)
    store_user_in_supabase(user_id, email)
    thread_ts = None
    if 'message' in body and 'thread_ts' in body['message']:
        thread_ts = body['message']['thread_ts']
    elif 'message' in body and 'ts' in body['message']:
        thread_ts = body['message']['ts']
    channel = body['channel']['id'] if 'channel' in body else None
    if channel:
        client.chat_postMessage(
            channel=channel,
            text=f"Logged in as {email}. You can now use the bot!",
            thread_ts=thread_ts
        )
    else:
        say(f"Logged in as {email}. You can now use the bot!")

@app.command("/quid")
def handle_quid_command(ack, body, client, say):
    ack()
    user_id = body["user_id"]
    if not is_user_authenticated(user_id):
        say(
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Please log in to use this bot."
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Log in"},
                            "action_id": "login"
                        }
                    ]
                }
            ]
        )
        return
    trigger_id = body["trigger_id"]
    channel_id = body["channel_id"]
    thread_ts = body.get("thread_ts")
    user_context_map[user_id] = {"channel": channel_id}
    if thread_ts:
        user_context_map[user_id]["thread_ts"] = thread_ts
    open_invoice_upload_modal(trigger_id, client)

@app.view("upload_invoice_modal")
def handle_invoice_upload_submission(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    context = user_context_map.get(user_id)

    if context and "channel" in context:
        channel = context["channel"]
        client.chat_postMessage(
            channel=channel,
            text="Thank you! Your file is being processed. You will receive a confirmation shortly."
        )

@app.event("file_shared")
def handle_file_shared(event, client):
    file_id = event["file_id"]
    user_id = event["user_id"]
    # Get user email
    email = get_slack_user_email(client, user_id)
    # Fetch file info from Slack
    file_info = client.files_info(file=file_id)["file"]
    # Save to the global array
    uploaded_files.append({
        "user_id": user_id,
        "email": email,
        "file_info": file_info
    })
    print(uploaded_files)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() 