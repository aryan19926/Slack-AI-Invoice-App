"""
FastAPI Server Startup Script
Run this to start the Invoice AI API server
"""

import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Start the FastAPI server"""
    port = int(os.getenv("API_PORT", 8000))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    print(f"🚀 Starting Invoice AI API Server...")
    print(f"📍 Server will run on: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔍 Health Check: http://{host}:{port}/api/health")
    
    uvicorn.run(
        "api_server.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()