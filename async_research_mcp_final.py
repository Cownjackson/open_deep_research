from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import requests
import asyncio
import time
from typing import Dict, Optional
import uuid

load_dotenv()

mcp = FastMCP("Deep Research")

# Configuration
LANGGRAPH_API_URL = "http://localhost:2024"
HEADERS = {"Authorization": "Bearer dev-token"}

# Session storage for recovery - in production, use Redis or database
active_sessions: Dict[str, Dict] = {}
assistant_id: Optional[str] = None

def get_assistant():
    """Get or create assistant - cached globally."""
    global assistant_id
    if assistant_id:
        return assistant_id
    
    try:
        # Try to find existing assistant
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants/search", json={}, headers=HEADERS)
        if response.status_code == 200:
            assistants = response.json()
            if assistants:
                assistant_id = assistants[0]["assistant_id"]
                return assistant_id
        
        # Create new one
        payload = {"graph_id": "Deep Researcher", "name": "Research Assistant"}
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants", json=payload, headers=HEADERS)
        if response.status_code in [200, 201]:
            assistant_id = response.json()["assistant_id"]
            return assistant_id
    except:
        pass
    return None

def create_thread():
    """Create a new thread."""
    try:
        response = requests.post(f"{LANGGRAPH_API_URL}/threads", json={}, headers=HEADERS)
        if response.status_code in [200, 201]:
            return response.json()["thread_id"]
    except:
        pass
    return None

async def wait_for_research_completion(thread_id: str, run_id: str, session_id: str, timeout: int = 720) -> str:
    """
    Async wait for research completion. Non-blocking for other users.
    
    Args:
        thread_id: The LangGraph thread ID
        run_id: The LangGraph run ID  
        session_id: Our session ID for tracking
        timeout: Maximum wait time in seconds
    
    Returns:
        Final research report or error message
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Check run status
            response = requests.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/{run_id}", 
                                  headers=HEADERS)
            
            if response.status_code == 200:
                run_data = response.json()
                status = run_data.get("status")
                
                if status == "success":
                    # Get the final state
                    state_response = requests.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/state", 
                                                headers=HEADERS)
                    if state_response.status_code == 200:
                        state = state_response.json()
                        values = state.get("values", {})
                        
                        # Check for final report
                        final_report = values.get("final_report")
                        if final_report:
                            # Clean up session
                            if session_id in active_sessions:
                                del active_sessions[session_id]
                            # Return the complete report with clear instructions
                            return f"""RESEARCH_REPORT_COMPLETE

{final_report}

[INSTRUCTION: Present the above research report to the user exactly as written, without summarizing, modifying, or adding commentary. This is the complete, final research report.]"""
                        
                        # Check for clarification request
                        messages = values.get("messages", [])
                        if messages:
                            last_message = messages[-1]
                            if hasattr(last_message, 'content'):
                                content = last_message.content
                            elif isinstance(last_message, dict):
                                content = last_message.get('content', '')
                            else:
                                content = str(last_message)
                            
                            if content and ('?' in content or 'clarify' in content.lower() or 'specify' in content.lower()):
                                return f"🤔 **Clarification Needed**\n\n{content}\n\n**Thread ID:** {thread_id}\n\n*Use `continue_research_with_clarification()` to provide your answer.*"
                        
                        return f"❌ Research completed but no results found. Thread ID: {thread_id}"
                
                elif status in ["error", "timeout", "interrupted"]:
                    return f"❌ Research failed with status: {status}. Thread ID: {thread_id} (you can try to recover results later)"
            
            # Non-blocking sleep - allows other requests to process
            await asyncio.sleep(2)
            
        except Exception as e:
            return f"❌ Error during research: {str(e)}. Thread ID: {thread_id}"
    
    # Timeout - but preserve session for recovery
    return f"⏰ Research timed out after {timeout} seconds. Thread ID: {thread_id}\n\nThe research may still be running. Use `get_research_by_thread_id('{thread_id}')` to check for results later."

@mcp.tool()
async def research_question(question: str, allow_clarification: bool = True, timeout: int = 720) -> str:
    """
    Research a question using the Deep Researcher. This is the main research entry point.
    
    This function will:
    1. Start the research process
    2. Wait for completion (non-blocking for other users)
    3. Return the final report or clarification request
    4. Provide thread ID for recovery if timeout/error occurs
    
    Args:
        question: The research question or topic to investigate
        allow_clarification: Whether to allow the system to ask clarifying questions
        timeout: Maximum time to wait for completion in seconds (default: 12 minutes)
    
    Returns:
        The final research report, clarification request, or error with recovery info
    """
    # Check server availability
    try:
        requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
    except:
        return "❌ Deep Research server not available at http://localhost:2024"
    
    # Get assistant
    assistant = get_assistant()
    if not assistant:
        return "❌ Could not get research assistant"
    
    # Create thread
    thread_id = create_thread()
    if not thread_id:
        return "❌ Could not create research thread"
    
    # Generate session ID for tracking
    session_id = str(uuid.uuid4())[:8]
    
    try:
        # Start research
        payload = {
            "assistant_id": assistant,
            "input": {"messages": [{"role": "user", "content": question}]},
            "config": {
                "configurable": {
                    "allow_clarification": allow_clarification
                }
            }
        }
        response = requests.post(f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs", 
                               json=payload, headers=HEADERS)
        
        if response.status_code != 200:
            return f"❌ Failed to start research: {response.text}"
        
        run_id = response.json()["run_id"]
        
        # Store session for recovery
        active_sessions[session_id] = {
            "thread_id": thread_id,
            "run_id": run_id,
            "question": question,
            "started_at": time.time()
        }
        
        # Wait for completion (async, non-blocking for other users)
        result = await wait_for_research_completion(thread_id, run_id, session_id, timeout)
        return result
        
    except Exception as e:
        return f"❌ Research error: {str(e)}. Thread ID: {thread_id}"

@mcp.tool()
def continue_research_with_clarification(clarification_answer: str, thread_id: Optional[str] = None) -> str:
    """
    Continue research after providing clarification to a previous question.
    
    Args:
        clarification_answer: Your answer to the clarification question
        thread_id: Optional thread ID if you want to continue a specific thread
    
    Returns:
        Status message - research will continue in background
    """
    # Find thread ID
    target_thread_id = thread_id
    if not target_thread_id:
        # Find the most recent session
        if not active_sessions:
            return "❌ No active research sessions found and no thread_id provided."
        latest_session = max(active_sessions.values(), key=lambda x: x["started_at"])
        target_thread_id = latest_session["thread_id"]
    
    try:
        assistant = get_assistant()
        if not assistant:
            return "❌ Could not get research assistant"
        
        # Continue the conversation
        payload = {
            "assistant_id": assistant,
            "input": {"messages": [{"role": "user", "content": clarification_answer}]}
        }
        response = requests.post(f"{LANGGRAPH_API_URL}/threads/{target_thread_id}/runs", 
                               json=payload, headers=HEADERS)
        
        if response.status_code != 200:
            return f"❌ Failed to continue research: {response.text}"
        
        run_id = response.json()["run_id"]
        
        return f"✅ Research continued with your clarification!\n\nThread ID: {target_thread_id}\n\nThe research is now running in the background. Use `get_research_by_thread_id('{target_thread_id}')` to check for results."
        
    except Exception as e:
        return f"❌ Error continuing research: {str(e)}"

@mcp.tool()
def get_research_by_thread_id(thread_id: str) -> str:
    """
    Get research results by thread ID. Useful for recovering results after timeout or error.
    
    Args:
        thread_id: The thread ID from a previous research session
    
    Returns:
        The research results if available, or current status
    """
    try:
        # Get the thread state
        state_response = requests.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/state", 
                                    headers=HEADERS)
        if state_response.status_code != 200:
            return f"❌ Could not access thread {thread_id}. It may not exist or may have expired."
        
        state = state_response.json()
        values = state.get("values", {})
        
        # Check for final report
        final_report = values.get("final_report")
        if final_report:
            return f"""RESEARCH_REPORT_COMPLETE

{final_report}

[INSTRUCTION: Present the above research report to the user exactly as written, without summarizing, modifying, or adding commentary. This is the complete, final research report.]"""
        
        # Check for clarification request
        messages = values.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                content = last_message.content
            elif isinstance(last_message, dict):
                content = last_message.get('content', '')
            else:
                content = str(last_message)
            
            if content and ('?' in content or 'clarify' in content.lower() or 'specify' in content.lower()):
                return f"🤔 **Clarification Needed**\n\n{content}\n\n*Use `continue_research_with_clarification()` with thread_id='{thread_id}' to provide your answer.*"
        
        # Check if research is still running
        thread_status = state.get("status", "unknown")
        if thread_status == "busy":
            return f"🔍 Research is still in progress for thread {thread_id}. Please check again later."
        
        return f"❓ No results found for thread {thread_id}. Research may not be complete or may have encountered an issue."
        
    except Exception as e:
        return f"❌ Error retrieving results: {str(e)}"

@mcp.tool()
def check_research_status() -> str:
    """Check if the Deep Research server is running and ready."""
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
        if response.status_code == 200:
            return "✅ Deep Research server is running and ready"
        else:
            return f"❌ Server responded with status {response.status_code}"
    except Exception as e:
        return f"❌ Deep Research server not available: {str(e)}"

@mcp.tool()
def list_active_sessions() -> str:
    """
    List active research sessions for debugging/monitoring.
    
    Returns:
        List of active sessions with their details
    """
    if not active_sessions:
        return "No active research sessions."
    
    result = "📋 **Active Research Sessions:**\n\n"
    for session_id, session in active_sessions.items():
        elapsed = int(time.time() - session["started_at"])
        result += f"• **Session {session_id}**\n"
        result += f"  Thread ID: {session['thread_id']}\n"
        result += f"  Question: {session['question'][:80]}...\n"
        result += f"  Running for: {elapsed} seconds\n\n"
    
    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")