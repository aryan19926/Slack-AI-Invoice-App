import os
import requests
import json
from constants import GEMINI_API_URL, SYSTEM_PROMPT, FORMAT_PROMPT

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def ask_gemini(prompt, context=None):
    full_prompt = SYSTEM_PROMPT + "\n" + (context or "") + "\nUser: " + prompt
    headers = {"Content-Type": "application/json"}
    params = {"key": 'AIzaSyBQd9xqaUXsk0jpzdF8acwTEIts0CzFNq4'}
    data = {"contents": [{"parts": [{"text": full_prompt}]}]}
    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    if response.status_code == 200:
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "Sorry, I couldn't parse Gemini's response."
    else:
        return f"Gemini API error: {response.status_code} {response.text}"

def extract_json_from_code_block(text):
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
    try:
        cleaned = extract_json_from_code_block(formatted_response)
        data = json.loads(cleaned)
    except Exception:
        return [
            {"type": "divider"},
            {"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "text", "text": "Sorry, I couldn't format the response."}]}]},
            {"type": "divider"}
        ]
    blocks = []
    blocks.append({"type": "divider"})
    if data.get("plain_text"):
        blocks.append({
            "type": "rich_text",
            "elements": [{
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": data["plain_text"]}]
            }]
        })
    if data.get("list") and isinstance(data["list"], list) and len(data["list"]):
        blocks.append({
            "type": "rich_text",
            "elements": [
                {"type": "rich_text_section", "elements": [{"type": "text", "text": "Details:"}]},
                {"type": "rich_text_list", "style": "bullet", "indent": 0, "border": 0, "elements": [
                    {"type": "rich_text_section", "elements": [{"type": "text", "text": item}]} for item in data["list"]
                ]}
            ]
        })
    blocks.append({
        "type": "actions",
        "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "helpful", "emoji": True}, "value": "click_me_123", "action_id": "helpful"},
            {"type": "button", "text": {"type": "plain_text", "text": "not-helpful", "emoji": True}, "value": "click_me_123", "action_id": "not-helpful"}
        ]
    })
    blocks.append({"type": "divider"})
    return blocks 