GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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

NOT_HELPFUL_MODAL = {
    "type": "modal",
    "callback_id": "not_helpful_modal",
    "title": {
        "type": "plain_text",
        "text": "My App",
        "emoji": True
    },
    "submit": {
        "type": "plain_text",
        "text": "Submit",
        "emoji": True
    },
    "close": {
        "type": "plain_text",
        "text": "Cancel",
        "emoji": True
    },
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "This is a section block with checkboxes."
            },
            "accessory": {
                "type": "checkboxes",
                "options": [
                    {
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Not Accurate*"
                        },
                        "value": "value-0"
                    },
                    {
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Not Accurate*"
                        },
                        "value": "value-1"
                    },
                    {
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Not Accurate*"
                        },
                        "value": "value-2"
                    }
                ],
                "action_id": "checkboxes-action"
            }
        }
    ]
}

LOADING_BLOCKS = [
    {"type": "divider"},
    {
        "type": "rich_text",
        "elements": [{
            "type": "rich_text_section",
            "elements": [{"type": "text", "text": "Quid is working on your request..."}]
        }]
    },
    {"type": "divider"}
] 