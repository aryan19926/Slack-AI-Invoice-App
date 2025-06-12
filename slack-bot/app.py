import os
from dotenv import load_dotenv
import requests
import json
import time
import hmac
import hashlib
load_dotenv()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# System prompt describing the API endpoints and expected output format
SYSTEM_PROMPT = (
    "You are an AI assistant for invoice management. "
    "You can call the following API endpoints to help users with their requests. "
    "For invoice-related requests, respond with a JSON object as described below.\n"
    "API Endpoints:\n"
    "1. get_invoice: Get details for a specific invoice.\n"
    "   Params: invoice_id (str), user_id (str, optional)\n"
    "2. update_invoice_status: Update the status of an invoice.\n"
    "   Params: invoice_id (str), status (str: Draft/Sent/Paid/Overdue/Cancelled), user_id (str, optional)\n"
    "3. get_summary: Get a summary of invoices (for aggregate numbers only, not lists).\n"
    "   Params: status (str, optional), due_date_before (str, optional), customer_name (str, optional), created_by_user_id (str, optional), invoice_type (str, optional)\n"
    "4. search_invoices: Search for and list invoices matching criteria (for when the user asks for a list of invoices, e.g., 'all invoices with status Draft').\n"
    "   Params: status (str, optional), due_date_before (str, optional), customer_name (str, optional), created_by_user_id (str, optional), invoice_type (str, optional)\n"
    "Respond in this format:\n"
    '{"action": "search_invoices", "params": { ... }}\n'
    "\n"
    "Examples:\n"
    "User: Give all invoices with status Draft\n"
    '{"action": "search_invoices", "params": {"status": "Draft"}}\n'
    "User: What is the total outstanding for paid invoices?\n"
    '{"action": "get_summary", "params": {"status": "Paid"}}\n'
)

FORMAT_PROMPT = (
    "You are a helpful assistant that formats invoice data into clear, natural language responses. "
    "Your task is to transform raw invoice data into easy-to-understand summaries. "
    "Follow these guidelines:\n"
    "1. Be concise but informative\n"
    "2. Highlight key numbers and important details\n"
    "3. Use bullet points for lists\n"
    "4. Format currency values appropriately\n"
    "5. Group related information together\n"
    "6. Use natural, conversational language\n"
    "7. If there are any errors or empty results, explain them clearly\n"
    "\n"
    "Example format:\n"
    "Here's a summary of your invoices:\n"
    "• Total amount: $10,000\n"
    "• Number of invoices: 5\n"
    "• Status breakdown:\n"
    "  - Paid: 3 invoices ($6,000)\n"
    "  - Pending: 2 invoices ($4,000)\n"
)

API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

def generate_slack_signature(body: str, signing_secret: str):
    timestamp = str(int(time.time()))
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return my_signature, timestamp

def ask_gemini(prompt, context=None):
    # Compose the full prompt with system instructions
    full_prompt = SYSTEM_PROMPT + "\n" + (context or "") + "\nUser: " + prompt
    headers = {
        "Content-Type": "application/json",
    }
    params = {
        "key": GEMINI_API_KEY
    }
    data = {
        "contents": [
            {"parts": [{"text": full_prompt}]}
        ]
    }
    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    if response.status_code == 200:
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "Sorry, I couldn't parse Gemini's response."
    else:
        return f"Gemini API error: {response.status_code} {response.text}"

def extract_json_from_code_block(text):
    # Remove code block markers if present
    if text.strip().startswith('```'):
        lines = text.strip().split('\n')
        # Remove the first (``` or ```json) and last (```)
        return '\n'.join(lines[1:-1])
    return text

def format_api_response(api_result, original_query):
    format_prompt = (
        f"{FORMAT_PROMPT}\n\n"
        f"User's original query: {original_query}\n\n"
        f"API Response: {json.dumps(api_result)}\n\n"
        "Please provide a natural language response:"
    )
    
    formatted_response = ask_gemini(format_prompt)
    return formatted_response

@app.message("")  # Respond to any message
def message_gemini(message, say):
    user = message['user']
    text = message.get('text', '')
    thread_ts = message.get('thread_ts') or message.get('ts')
    # print user id
    print("[User ID]", user)
    # you could fetch recent conversation context here for RAG
    context = None  # For now, no extra context

    gemini_response = ask_gemini(text, context)

    # Debug: print the raw Gemini response
    print("[Gemini raw response]", gemini_response)

    # Try to parse Gemini's response as JSON for an action
    action = None
    try:
        cleaned = extract_json_from_code_block(gemini_response)
        action = json.loads(cleaned)
        print("[Gemini parsed action]", action)
        print("[Type of action]", type(action))
    except Exception as e:
        print("[Gemini JSON parse error]", e)
        action = None

    print("[Before action type check] action:", action, "type:", type(action))
    if isinstance(action, dict) and 'action' in action and 'params' in action:
        print("[Entering API call block]")
        api_result = None
        try:
            if action['action'] == 'get_invoice':
                invoice_id = action['params'].get('invoice_id')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}?user_id={user_id}"
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
                print(f"[API CALL] PUT {api_url} BODY: {{'status': {status}}}")
                try:
                    json_body = {"status": status}
                    raw_body = json.dumps(json_body)
                    signature, timestamp = generate_slack_signature(raw_body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp,
                        "Content-Type": "application/json"
                    }
                    r = requests.put(api_url, json=json_body, headers=headers)
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
                # Build query string
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/summary"
                if query:
                    api_url += f"?{query}"
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
            print("[API ERROR]", e)
            api_result = {"error": f"API call failed: {str(e)}"}

        print("[API RESULT]", api_result)
        # Format the API result for Slack
        if api_result:
            # Get natural language response
            formatted_response = format_api_response(api_result, text)
            say(f"<@{user}> {formatted_response}", thread_ts=thread_ts)
        else:
            say(f"<@{user}> Sorry, I couldn't process your request.", thread_ts=thread_ts)
    else:
        print("[Not an actionable response, sending fallback]")
        say(f"<@{user}> Sorry, I couldn't understand your request.", thread_ts=thread_ts)

# Handle the app_mention event
@app.event("app_mention")
def handle_app_mention(event, say):
    user = event['user']
    text = event['text'].strip()
    thread_ts = event.get('thread_ts') or event.get('ts')
    
    # Remove the bot mention from the text
    text = text.replace(f"<@{os.environ.get('SLACK_BOT_ID')}>", "").strip()
    
    print("[User ID]", user)
    print("[Mention text]", text)
    
    # Get the action from Gemini
    gemini_response = ask_gemini(text)
    print("[Gemini raw response]", gemini_response)
    
    # Try to parse Gemini's response as JSON for an action
    action = None
    try:
        cleaned = extract_json_from_code_block(gemini_response)
        action = json.loads(cleaned)
        print("[Gemini parsed action]", action)
    except Exception as e:
        print("[Gemini JSON parse error]", e)
        action = None
    
    if isinstance(action, dict) and 'action' in action and 'params' in action:
        api_result = None
        try:
            if action['action'] == 'get_invoice':
                invoice_id = action['params'].get('invoice_id')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}?user_id={user_id}"
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
                print(f"[API CALL] PUT {api_url} BODY: {{'status': {status}}}")
                try:
                    json_body = {"status": status}
                    raw_body = json.dumps(json_body)
                    signature, timestamp = generate_slack_signature(raw_body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp,
                        "Content-Type": "application/json"
                    }
                    r = requests.put(api_url, json=json_body, headers=headers)
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
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
                print(f"[API CALL] GET {api_url}")
                try:
                    body = ""  # GET request, no body
                    signature, timestamp = generate_slack_signature(body, SLACK_SIGNING_SECRET)
                    headers = {
                        "x-slack-signature": signature,
                        "x-slack-request-timestamp": timestamp
                    }
                    r = requests.get(api_url, headers=headers)
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
            print("[API ERROR]", e)
            api_result = {"error": f"API call failed: {str(e)}"}
        
        print("[API RESULT]", api_result)
        if api_result:
            # Get natural language response
            formatted_response = format_api_response(api_result, text)
            say(f"<@{user}> {formatted_response}", thread_ts=thread_ts)
        else:
            say(f"<@{user}> Sorry, I couldn't process your request.", thread_ts=thread_ts)
    else:
        print("[Not an actionable response, sending fallback]")
        say(f"<@{user}> Sorry, I couldn't understand your request.", thread_ts=thread_ts)

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()