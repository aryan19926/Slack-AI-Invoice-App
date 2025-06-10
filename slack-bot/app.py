import os
from dotenv import load_dotenv
import requests
import json
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
    "If the user's request is about invoices, ALWAYS respond ONLY with a JSON object as described below. "
    "Do NOT reply with plain text unless the request is not related to invoices.\n"
    "API Endpoints:\n"
    "1. get_invoice: Get details for a specific invoice.\n"
    "   Params: invoice_id (str), user_id (str, optional)\n"
    "2. update_invoice_status: Update the status of an invoice.\n"
    "   Params: invoice_id (str), status (str: Draft/Sent/Paid/Overdue/Cancelled), user_id (str, optional)\n"
    "3. get_summary: Get a summary of invoices.\n"
    "   Params: status (str, optional), due_date_before (str, optional), customer_name (str, optional), created_by_user_id (str, optional), invoice_type (str, optional)\n"
    "Respond in this format for actions:\n"
    '{"action": "get_invoice", "params": { ... }}\n'
    "If the request is not about invoices, you may reply with a plain message."
)

API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")

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

@app.message("")  # Respond to any message
def message_gemini(message, say):
    user = message['user']
    text = message.get('text', '')
    thread_ts = message.get('thread_ts') or message.get('ts')

    # Optionally, you could fetch recent conversation context here for RAG
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
                r = requests.get(api_url)
                api_result = r.json()
            elif action['action'] == 'update_invoice_status':
                invoice_id = action['params'].get('invoice_id')
                status = action['params'].get('status')
                user_id = action['params'].get('user_id', user)
                api_url = f"{API_SERVER_URL}/api/invoices/{invoice_id}/status?user_id={user_id}"
                print(f"[API CALL] PUT {api_url} BODY: {{'status': {status}}}")
                r = requests.put(api_url, json={"status": status})
                api_result = r.json()
            elif action['action'] == 'get_summary':
                params = action['params']
                # Build query string
                query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
                api_url = f"{API_SERVER_URL}/api/invoices/summary"
                if query:
                    api_url += f"?{query}"
                print(f"[API CALL] GET {api_url}")
                r = requests.get(api_url)
                api_result = r.json()
            else:
                api_result = {"error": "Unknown action."}
        except Exception as e:
            print("[API ERROR]", e)
            api_result = {"error": f"API call failed: {str(e)}"}

        print("[API RESULT]", api_result)
        # Format the API result for Slack
        if api_result:
            formatted = f"<@{user}>\n```\n{json.dumps(api_result, indent=2)}\n```"
            say(formatted, thread_ts=thread_ts)
        else:
            say(f"<@{user}> Sorry, I couldn't process your request.", thread_ts=thread_ts)
    else:
        print("[Not an actionable response, sending fallback]")
        say(f"<@{user}> Sorry, I couldn't understand your request.", thread_ts=thread_ts)

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()