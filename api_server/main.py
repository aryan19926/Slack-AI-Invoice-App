from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from dotenv import load_dotenv
from .models import APIResponse, ErrorResponse
from .database import DatabaseClient
from .auth import get_user_from_request
from .routers.invoices import router as invoices_router
from datetime import date
from .routers.auth import router as auth_router
from fastapi.staticfiles import StaticFiles

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Invoice AI API",
    description="Internal API for invoice management with AI integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from 'static' directory
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# Initialize database client
db = DatabaseClient()

app.include_router(invoices_router)

app.include_router(auth_router)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Invoice AI API is running", "status": "healthy"}

@app.get("/api/health")
async def health_check():
    """Detailed health check with database connectivity"""
    try:
        # Test database connection
        test_summary = db.get_invoices_summary()
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_invoices": test_summary.total_invoices,
            "timestamp": date.today().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {str(e)}"
        )

@app.get("/auth_callback.html")
def serve_auth_callback():
    return FileResponse("static/auth_callback.html")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=exc.detail,
            details=f"Status Code: {exc.status_code}"
        ).model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error="Internal server error",
            details=str(exc)
        ).model_dump()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )