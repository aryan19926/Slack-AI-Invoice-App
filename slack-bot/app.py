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
    "For invoice-related requests, respond with a JSON object as described below.\n"
    "If the query is about an invoice, even if the wording is informal or partial (e.g., 'status of invoice INV-2024-001', 'show invoice INV-2024-001', 'is INV-2024-001 paid?'), respond with the appropriate JSON action as described below.\n"
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
    "User: status of invoice inv-2024-001\n"
    '{"action": "get_invoice", "params": {"invoice_id": "inv-2024-001"}}\n'
    "User: is inv-2024-001 paid?\n"
    '{"action": "get_invoice", "params": {"invoice_id": "inv-2024-001"}}\n'
)

FORMAT_PROMPT = (
    "You are a helpful assistant that formats invoice data for Slack using blocks. "
    "Your task is to transform raw invoice data into a JSON object with these fields: "
    "'plain_text' (string, a concise summary addressing the user's query), "
    "'list' (array of strings, for bullet points if needed, else empty array), "
    "'error' (boolean, true if there is an error or empty result, else false). "
    "Do not include any other fields. "
    "Do not use markdown. "
    "Example output: {\"plain_text\": \"Here's a summary...\", \"list\": [\"item 1\", \"item 2\"], \"error\": false} "
    "If there is an error or empty result, set 'error' to true and explain in 'plain_text'. "
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
        return '\n'.join(lines[1:-1])
    return text

def format_api_response(api_result, original_query):
    format_prompt = (
        f"{FORMAT_PROMPT}\n\n"
        f"User's original query: {original_query}\n\n"
        f"API Response: {json.dumps(api_result)}\n\n"
        "Please provide only the JSON object as described."
    )
    formatted_response = ask_gemini(format_prompt)
    # Try to parse the JSON output
    try:
        cleaned = extract_json_from_code_block(formatted_response)
        data = json.loads(cleaned)
    except Exception:
        # fallback: show as plain text
        return [{
            "type": "divider"
        }, {
            "type": "rich_text",
            "elements": [{
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": "Sorry, I couldn't format the response."}]
            }]
        }, {
            "type": "divider"
        }]
    blocks = []
    # Divider
    blocks.append({"type": "divider"})
    # Plain text (rich_text)
    if data.get("plain_text"):
        blocks.append({
            "type": "rich_text",
            "elements": [{
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": data["plain_text"]}]
            }]
        })
    # List (rich_text_list)
    if data.get("list") and isinstance(data["list"], list) and len(data["list"]):
        # Add a heading for the list
        blocks.append({
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Details:"}]
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "indent": 0,
                    "border": 0,
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": item}]
                        } for item in data["list"]
                    ]
                }
            ]
        })
    # Actions (buttons)
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "helpful", "emoji": True},
                "value": "click_me_123",
                "action_id": "helpful"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "not-helpful", "emoji": True},
                "value": "click_me_123",
                "action_id": "not-helpful"
            }
        ]
    })
    # Divider
    blocks.append({"type": "divider"})
    return blocks

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
                print(f"[API CALL] PUT {api_url} BODY: {{'status': {status}}}")
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
                print(f"[API CALL] GET {api_url}")
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
                print(f"[API CALL] GET {api_url}")
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
            print("[API ERROR]", e)
            api_result = {"error": f"API call failed: {str(e)}"}

        print("[API RESULT]", api_result)
        # Format the API result for Slack
        if api_result and "error" in api_result:
            say(f"<@{user}> Sorry, {api_result['error']}", thread_ts=thread_ts)
        else:
            formatted_response = format_api_response(api_result, text)
            say(blocks=formatted_response, thread_ts=thread_ts)
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
                print(f"[API CALL] PUT {api_url} BODY: {{'status': {status}}}")
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
                print(f"[API CALL] GET {api_url}")
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
                print(f"[API CALL] GET {api_url}")
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
            print("[API ERROR]", e)
            api_result = {"error": f"API call failed: {str(e)}"}
        
        print("[API RESULT]", api_result)
        if api_result and "error" in api_result:
            say(f"<@{user}> Sorry, {api_result['error']}", thread_ts=thread_ts)
        else:
            formatted_response = format_api_response(api_result, text)
            say(blocks=formatted_response, thread_ts=thread_ts)
    else:
        print("[Not an actionable response, sending fallback]")
        say(f"<@{user}> Sorry, I couldn't understand your request.", thread_ts=thread_ts)


@app.action("helpful")
def action_helpful(body, ack, say):
    ack()
    user_id = body['user']['id']
    # Try to get the thread_ts from the action payload
    thread_ts = None
    if 'message' in body and 'thread_ts' in body['message']:
        thread_ts = body['message']['thread_ts']
    elif 'message' in body and 'ts' in body['message']:
        thread_ts = body['message']['ts']
    say(f"<@{user_id}> Thank you for your feedback!", thread_ts=thread_ts)

@app.action("not-helpful")
def action_not_helpful(body, ack, say):
    ack()
    user_id = body['user']['id']
    # Try to get the thread_ts from the action payload
    thread_ts = None
    if 'message' in body and 'thread_ts' in body['message']:
        thread_ts = body['message']['thread_ts']
    elif 'message' in body and 'ts' in body['message']:
        thread_ts = body['message']['ts']
    say(f"<@{user_id}> I'm sorry to hear that. I'll try to improve.", thread_ts=thread_ts)


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() 