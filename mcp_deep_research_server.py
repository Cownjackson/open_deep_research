#!/usr/bin/env python3
"""
MCP Server for Open Deep Research
Exposes the deep research functionality as MCP tools for AI agents.
"""

import asyncio
import json
import logging
from typing import Any, Sequence
import requests
import time

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.types as types

# Configuration
LANGGRAPH_API_URL = "http://localhost:2024"
DEFAULT_TIMEOUT = 300  # 5 minutes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deep-research-mcp")

class DeepResearchMCP:
    def __init__(self):
        self.server = Server("deep-research")
        self.current_thread_id = None
        self.assistant_id = None
        
    def check_server(self) -> bool:
        """Check if the LangGraph server is running."""
        try:
            response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Server check failed: {e}")
            return False
    
    def create_thread(self) -> str | None:
        """Create a new research thread."""
        try:
            headers = {"Authorization": "Bearer dev-token"}
            response = requests.post(f"{LANGGRAPH_API_URL}/threads", json={}, headers=headers)
            if response.status_code in [200, 201]:
                result = response.json()
                thread_id = result.get("thread_id") or result.get("id")
                logger.info(f"Created thread: {thread_id}")
                return thread_id
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
        return None
    
    def get_or_create_assistant(self) -> str | None:
        """Get or create the Deep Researcher assistant."""
        if self.assistant_id:
            return self.assistant_id
            
        try:
            headers = {"Authorization": "Bearer dev-token"}
            
            # Try to search for existing assistants
            response = requests.post(f"{LANGGRAPH_API_URL}/assistants/search", json={}, headers=headers)
            if response.status_code == 200:
                assistants = response.json()
                if assistants:
                    self.assistant_id = assistants[0].get("assistant_id") or assistants[0].get("id")
                    logger.info(f"Found existing assistant: {self.assistant_id}")
                    return self.assistant_id
            
            # Create new assistant
            payload = {
                "graph_id": "Deep Researcher",
                "name": "Deep Researcher",
                "description": "AI research agent"
            }
            response = requests.post(f"{LANGGRAPH_API_URL}/assistants", json=payload, headers=headers)
            if response.status_code in [200, 201]:
                result = response.json()
                self.assistant_id = result.get("assistant_id") or result.get("id")
                logger.info(f"Created new assistant: {self.assistant_id}")
                return self.assistant_id
                
        except Exception as e:
            logger.error(f"Failed to get/create assistant: {e}")
        
        return None
    
    def wait_for_completion(self, thread_id: str, run_id: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
        """Wait for the research run to complete and return the final report."""
        headers = {"Authorization": "Bearer dev-token"}
        wait_time = 0
        
        while wait_time < timeout:
            try:
                # Check run status
                status_url = f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/{run_id}"
                response = requests.get(status_url, headers=headers)
                
                if response.status_code == 200:
                    run_info = response.json()
                    status = run_info.get("status")
                    
                    if status == "success":
                        # Get the final state
                        state_url = f"{LANGGRAPH_API_URL}/threads/{thread_id}/state"
                        state_response = requests.get(state_url, headers=headers)
                        
                        if state_response.status_code == 200:
                            state_data = state_response.json()
                            final_report = state_data.get("values", {}).get("final_report")
                            if final_report:
                                logger.info("Research completed successfully")
                                return final_report
                        
                    elif status == "error":
                        logger.error("Research run failed")
                        return None
                        
                time.sleep(2)
                wait_time += 2
                
            except Exception as e:
                logger.error(f"Error checking status: {e}")
                return None
        
        logger.error("Research timed out")
        return None
    
    def conduct_research(self, question: str, timeout: int = DEFAULT_TIMEOUT, new_session: bool = False) -> str:
        """Conduct research on the given question."""
        # Check server availability
        if not self.check_server():
            raise Exception("LangGraph server is not running. Please start it first.")
        
        # Create or reuse thread
        if new_session or not self.current_thread_id:
            self.current_thread_id = self.create_thread()
            
        if not self.current_thread_id:
            raise Exception("Failed to create research thread")
        
        # Get assistant
        assistant_id = self.get_or_create_assistant()
        if not assistant_id:
            raise Exception("Failed to get assistant")
        
        try:
            headers = {"Authorization": "Bearer dev-token"}
            
            # Submit research
            url = f"{LANGGRAPH_API_URL}/threads/{self.current_thread_id}/runs"
            payload = {
                "assistant_id": assistant_id,
                "input": {"messages": [{"role": "user", "content": question}]}
            }
            
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Failed to start research: {response.status_code} - {response.text}")
                
            run_data = response.json()
            run_id = run_data.get("run_id")
            
            if not run_id:
                raise Exception("No run ID returned")
            
            # Wait for completion
            final_report = self.wait_for_completion(self.current_thread_id, run_id, timeout)
            
            if not final_report:
                raise Exception("No final report was generated")
                
            return final_report
            
        except Exception as e:
            logger.error(f"Research failed: {e}")
            raise

# Initialize the MCP server
research_mcp = DeepResearchMCP()

@research_mcp.server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available research tools."""
    return [
        Tool(
            name="conduct_research",
            description="Conduct deep research on a given topic or question. Returns a comprehensive research report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The research question or topic to investigate"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum time to wait for research completion in seconds (default: 600)",
                        "default": 600
                    },
                    "new_session": {
                        "type": "boolean",
                        "description": "Whether to start a new research session (default: false)",
                        "default": False
                    }
                },
                "required": ["question"]
            }
        )
    ]

@research_mcp.server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}
    
    try:
        if name == "conduct_research":
            question = arguments.get("question")
            if not question:
                return [types.TextContent(
                    type="text",
                    text="Error: 'question' parameter is required"
                )]
            
            timeout = arguments.get("timeout", DEFAULT_TIMEOUT)
            new_session = arguments.get("new_session", False)
            
            logger.info(f"Starting research for: {question[:100]}...")
            
            # Conduct the research
            report = research_mcp.conduct_research(question, timeout, new_session)
            
            return [types.TextContent(
                type="text",
                text=f"# Research Report\n\n**Question:** {question}\n\n{report}"
            )]
            
        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
            
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

async def main():
    # Run the server using stdin/stdout loops
    async with stdio_server() as (read_stream, write_stream):
        await research_mcp.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="deep-research",
                server_version="1.0.0",
                capabilities=research_mcp.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())