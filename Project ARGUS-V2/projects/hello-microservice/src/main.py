"""
Hello Microservice - ARGUS-V2 Sample Application

Demonstrates high-performance microservice built with ARGUS-V2 orchestration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="Hello Microservice",
    description="ARGUS-V2 sample demonstrating high-performance microservice",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EchoRequest(BaseModel):
    """Echo request model."""
    message: str

class EchoResponse(BaseModel):
    """Echo response model."""
    echo: str
    service: str
    framework: str

@app.get("/")
async def root():
    """Root endpoint showing service info."""
    return {
        "service": "hello-microservice",
        "version": "1.0.0",
        "framework": "ARGUS-V2",
        "status": "running",
        "features": [
            "⚡ <200ms cold start",
            "🚀 FastAPI framework",
            "🤖 Multi-agent orchestration",
            "🔧 Automated quality gates"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "hello-microservice",
        "framework": "ARGUS-V2"
    }

@app.get("/api/v1/hello")
async def hello():
    """Hello endpoint."""
    return {
        "message": "Hello from ARGUS-V2!",
        "description": "High-performance multi-agent AI orchestration framework",
        "features": {
            "performance": "≤200ms CLI startup, ≤30s builds",
            "architecture": "Async-first, plugin-based",
            "agents": "Claude, Gemini, GPT-4 integration",
            "quality": "90%+ test coverage, zero CVEs"
        }
    }

@app.post("/api/v1/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """Echo endpoint that returns the input message."""
    return EchoResponse(
        echo=request.message,
        service="hello-microservice",
        framework="ARGUS-V2"
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )