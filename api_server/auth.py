import os
import hmac
import hashlib
import time
from fastapi import HTTPException, Header, Request
from typing import Optional

class SlackAuthenticator:
    def __init__(self):
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").encode()
        self.api_secret_key = os.getenv("API_SECRET_KEY", "default-secret-key")
        self.allowed_users = os.getenv("ALLOWED_SLACK_USERS", "").split(",")
    
    def verify_slack_request(self, 
                           request_body: bytes, 
                           timestamp: str, 
                           signature: str) -> bool:
        """Verify that the request came from Slack"""
        try:
            # Check timestamp (should be within 5 minutes)
            if abs(time.time() - int(timestamp)) > 60 * 5:
                return False
            
            # Create signature
            sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
            my_signature = 'v0=' + hmac.new(
                self.signing_secret,
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(my_signature, signature)
        except Exception as e:
            print(f"Error verifying Slack request: {e}")
            return False
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key for internal requests"""
        return api_key == self.api_secret_key
    
    def is_user_allowed(self, user_id: str) -> bool:
        """Check if user is in allowed list"""
        return user_id in self.allowed_users or len(self.allowed_users) == 0

# Authentication dependency functions
async def verify_internal_auth(x_api_key: Optional[str] = Header(None)):
    """Verify internal API authentication"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    auth = SlackAuthenticator()
    if not auth.verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True

async def verify_slack_auth(request: Request,
                          x_slack_signature: Optional[str] = Header(None),
                          x_slack_request_timestamp: Optional[str] = Header(None)):
    """Verify Slack request authentication"""
    if not x_slack_signature or not x_slack_request_timestamp:
        raise HTTPException(status_code=401, detail="Missing Slack headers")
    
    body = await request.body()
    auth = SlackAuthenticator()
    
    if not auth.verify_slack_request(body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    
    return True

def get_user_from_request(user_id: Optional[str] = None) -> Optional[str]:
    """Extract and validate user from request"""
    if user_id:
        auth = SlackAuthenticator()
        if auth.is_user_allowed(user_id):
            return user_id
    return None