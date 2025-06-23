from typing import Optional

def get_user_from_request(user_id: Optional[str] = None) -> Optional[str]:
    """Extract and validate user from request"""
    # The allowed users logic is still needed for filtering
    import os
    allowed_users = os.getenv("ALLOWED_SLACK_USERS", "").split(",")
    if user_id:
        if user_id in allowed_users or len(allowed_users) == 0:
            return user_id
    return None