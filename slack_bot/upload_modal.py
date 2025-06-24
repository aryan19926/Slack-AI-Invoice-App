from constants import NOT_HELPFUL_MODAL

def open_invoice_upload_modal(trigger_id, client):
    modal_view = {
        "type": "modal",
        "callback_id": "upload_invoice_modal",
        "title": {"type": "plain_text", "text": "Upload Invoice"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "file_upload_block",
                "label": {"type": "plain_text", "text": "Upload Invoice (Image or PDF)"},
                "element": {
                    "type": "file_input",
                    "action_id": "file_input_action_id_1",
                    "filetypes": ["jpg", "jpeg", "png", "pdf"],
                    "max_files": 5
                }
            }
        ]
    }
    client.views_open(trigger_id=trigger_id, view=modal_view) 