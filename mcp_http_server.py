#!/usr/bin/env python3
"""
HTTP wrapper for the Deep Research MCP server.
Exposes MCP tools as HTTP endpoints for OpenWebUI integration.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import logging
from mcp_deep_research_server import DeepResearchMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-http-server")

app = FastAPI(
    title="Deep Research MCP HTTP Server",
    description="HTTP wrapper for Deep Research MCP tools",
    version="1.0.0"
)

# Initialize the research MCP instance
research_mcp = DeepResearchMCP()

class ResearchRequest(BaseModel):
    question: str
    timeout: int = 300
    new_session: bool = False

class ResearchResponse(BaseModel):
    report: str
    status: str = "success"

class StatusResponse(BaseModel):
    status: str
    message: str

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Deep Research MCP HTTP Server",
        "version": "1.0.0",
        "endpoints": {
            "/research": "POST - Conduct research",
            "/status": "GET - Check server status",
            "/openapi.json": "GET - OpenAPI specification"
        }
    }

@app.get("/status")
async def check_status():
    """Check if the deep research server is available."""
    try:
        is_running = research_mcp.check_server()
        if is_running:
            return StatusResponse(
                status="online",
                message="Deep Research server is running"
            )
        else:
            return StatusResponse(
                status="offline", 
                message="Deep Research server is not running"
            )
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/research")
async def conduct_research(request: ResearchRequest):
    """Conduct deep research on a given question."""
    try:
        logger.info(f"Starting research for: {request.question[:100]}...")
        
        report = research_mcp.conduct_research(
            question=request.question,
            timeout=request.timeout,
            new_session=request.new_session
        )
        
        return ResearchResponse(report=report)
        
    except Exception as e:
        logger.error(f"Research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# OpenWebUI-compatible endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """OpenAI-compatible endpoint for OpenWebUI integration."""
    try:
        # Extract the user's message
        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        user_message = messages[-1].get("content", "")
        
        # Conduct research
        report = research_mcp.conduct_research(question=user_message)
        
        # Return in OpenAI format
        return {
            "id": "research-response",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "deep-research",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": report
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len(report.split()),
                "total_tokens": len(user_message.split()) + len(report.split())
            }
        }
        
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Starting Deep Research MCP HTTP Server...")
    print("Server will be available at: http://localhost:8999")
    print("OpenAPI docs at: http://localhost:8999/docs")
    print("Make sure your LangGraph API is running on http://localhost:2024")
    
    uvicorn.run(app, host="0.0.0.0", port=8999)