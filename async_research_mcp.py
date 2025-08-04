from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import requests
import asyncio
import time
from typing import Dict, Optional
import uuid

load_dotenv()

mcp = FastMCP("Deep Research Async")

# Configuration
LANGGRAPH_API_URL = "http://localhost:2024"
HEADERS = {"Authorization": "Bearer dev-token"}

# Session storage - in production, use Redis or database
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

async def poll_for_completion(thread_id: str, run_id: str, max_wait: int = 720) -> Dict:
    """Async polling for research completion."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
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
                        return {"status": "success", "data": state_response.json()}
                
                elif status in ["error", "timeout", "interrupted"]:
                    return {"status": "error", "message": f"Research failed with status: {status}"}
            
            # Non-blocking sleep
            await asyncio.sleep(2)
            
        except Exception as e:
            return {"status": "error", "message": f"Polling error: {str(e)}"}
    
    return {"status": "timeout", "message": "Research timed out"}

@mcp.tool()
def start_research(question: str, allow_clarification: bool = True) -> str:
    """
    Start a research session. Returns immediately with a session ID.
    Use check_research_progress() to monitor and get_research_results() to retrieve results.
    
    Args:
        question: The research question or topic to investigate
        allow_clarification: Whether to allow the system to ask clarifying questions
    
    Returns:
        Session ID for tracking the research
    """
    # Check server
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
    
    # Generate session ID
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
        
        # Store session info
        active_sessions[session_id] = {
            "thread_id": thread_id,
            "run_id": run_id,
            "question": question,
            "status": "running",
            "started_at": time.time()
        }
        
        return f"✅ Research started! Session ID: **{session_id}**\n\nUse `check_research_progress('{session_id}')` to monitor progress."
        
    except Exception as e:
        return f"❌ Research error: {str(e)}"

@mcp.tool()
def check_research_progress(session_id: str) -> str:
    """
    Check the progress of a research session.
    
    Args:
        session_id: The session ID returned by start_research()
    
    Returns:
        Current status and progress information
    """
    if session_id not in active_sessions:
        return f"❌ Session {session_id} not found. Use start_research() to begin."
    
    session = active_sessions[session_id]
    thread_id = session["thread_id"]
    run_id = session["run_id"]
    
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/{run_id}", 
                              headers=HEADERS)
        if response.status_code == 200:
            run_data = response.json()
            status = run_data.get("status")
            
            if status == "success":
                session["status"] = "completed"
                return f"✅ Research completed for session {session_id}!\n\nUse `get_research_results('{session_id}')` to retrieve the report."
            
            elif status in ["error", "timeout", "interrupted"]:
                session["status"] = "error"
                return f"❌ Research failed for session {session_id} with status: {status}"
            
            elif status in ["pending", "running"]:
                elapsed = int(time.time() - session["started_at"])
                return f"🔍 Research in progress for session {session_id}\n\nElapsed time: {elapsed} seconds\nStatus: {status}"
        
        return f"❓ Could not get status for session {session_id}"
        
    except Exception as e:
        return f"❌ Error checking progress: {str(e)}"

@mcp.tool()
def get_research_results(session_id: str) -> str:
    """
    Get the results of a completed research session.
    
    Args:
        session_id: The session ID returned by start_research()
    
    Returns:
        The research results or status message
    """
    if session_id not in active_sessions:
        return f"❌ Session {session_id} not found."
    
    session = active_sessions[session_id]
    thread_id = session["thread_id"]
    question = session["question"]
    
    try:
        # Check if research is complete
        response = requests.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/{session['run_id']}", 
                              headers=HEADERS)
        if response.status_code == 200:
            run_data = response.json()
            if run_data.get("status") != "success":
                return f"❌ Research not yet complete for session {session_id}. Current status: {run_data.get('status')}"
        
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
                del active_sessions[session_id]
                return f"""RESEARCH_REPORT_START

{final_report}

RESEARCH_REPORT_END

[This is the complete research report. Present it to the user exactly as shown above between the RESEARCH_REPORT_START and RESEARCH_REPORT_END markers, without adding commentary, summary, or modifications.]"""
            
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
                    return f"🤔 **Clarification Needed for Session {session_id}**\n\n{content}\n\nUse `continue_research('{session_id}', 'your answer')` to provide clarification."
            
            return f"❌ No results found for session {session_id}"
        
        return f"❌ Could not retrieve results for session {session_id}"
        
    except Exception as e:
        return f"❌ Error getting results: {str(e)}"

@mcp.tool()
def continue_research(session_id: str, clarification_answer: str) -> str:
    """
    Continue research after providing clarification.
    
    Args:
        session_id: The session ID that needs clarification
        clarification_answer: Your answer to the clarification question
    
    Returns:
        Status message about continuing research
    """
    if session_id not in active_sessions:
        return f"❌ Session {session_id} not found."
    
    session = active_sessions[session_id]
    thread_id = session["thread_id"]
    
    try:
        assistant = get_assistant()
        if not assistant:
            return "❌ Could not get research assistant"
        
        # Continue the conversation
        payload = {
            "assistant_id": assistant,
            "input": {"messages": [{"role": "user", "content": clarification_answer}]}
        }
        response = requests.post(f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs", 
                               json=payload, headers=HEADERS)
        
        if response.status_code != 200:
            return f"❌ Failed to continue research: {response.text}"
        
        run_id = response.json()["run_id"]
        
        # Update session
        session["run_id"] = run_id
        session["status"] = "running"
        session["started_at"] = time.time()
        
        return f"✅ Research continued for session {session_id}!\n\nUse `check_research_progress('{session_id}')` to monitor progress."
        
    except Exception as e:
        return f"❌ Error continuing research: {str(e)}"

@mcp.tool()
def list_active_sessions() -> str:
    """
    List all active research sessions.
    
    Returns:
        List of active sessions with their status
    """
    if not active_sessions:
        return "No active research sessions."
    
    result = "📋 **Active Research Sessions:**\n\n"
    for session_id, session in active_sessions.items():
        elapsed = int(time.time() - session["started_at"])
        result += f"• **{session_id}** - {session['status']} ({elapsed}s ago)\n"
        result += f"  Question: {session['question'][:60]}...\n\n"
    
    return result

@mcp.tool()
def research_question(question: str, allow_clarification: bool = True) -> str:
    """
    Research a question using the Deep Researcher. This is the main research tool.
    This version is backward compatible but uses async sessions internally.
    
    Args:
        question: The research question or topic to investigate
        allow_clarification: Whether to allow the system to ask clarifying questions
    
    Returns:
        The research results, clarifying question, or status
    """
    # Start research
    start_result = start_research(question, allow_clarification)
    if "❌" in start_result:
        return start_result
    
    # Extract session ID
    try:
        session_id = start_result.split("Session ID: **")[1].split("**")[0]
    except:
        return "❌ Could not extract session ID from start result"
    
    # Poll for completion (with shorter timeout for sync behavior)
    start_time = time.time()
    timeout = 720  # 2 minutes
    
    while time.time() - start_time < timeout:
        progress = check_research_progress(session_id)
        
        if "✅ Research completed" in progress:
            return get_research_results(session_id)
        elif "❌" in progress:
            return progress
        
        time.sleep(2)
    
    return f"⏰ Research is taking longer than expected. Session {session_id} may still be running. Use check_research_progress('{session_id}') to monitor."

@mcp.tool()
def research_question_sync(question: str, allow_clarification: bool = True, timeout: int = 720) -> str:
    """
    Research a question synchronously (blocks until complete). 
    Use this for simple cases where you want to wait for results.
    
    Args:
        question: The research question or topic to investigate
        allow_clarification: Whether to allow clarification questions
        timeout: Maximum time to wait in seconds
    
    Returns:
        The research results or clarification request
    """
    return research_question(question, allow_clarification)

@mcp.tool()
def continue_research_with_clarification(clarification_answer: str) -> str:
    """
    Continue research after providing clarification to a previous question.
    This is backward compatible - it finds the most recent session needing clarification.
    
    Args:
        clarification_answer: Your answer to the clarification question
    
    Returns:
        The research results or status
    """
    # Find the most recent session that might need clarification
    if not active_sessions:
        return "❌ No active research sessions found. Please start a new research session."
    
    # Get the most recent session (simple heuristic)
    latest_session_id = max(active_sessions.keys(), key=lambda x: active_sessions[x]["started_at"])
    
    # Continue research with that session
    continue_result = continue_research(latest_session_id, clarification_answer)
    if "❌" in continue_result:
        return continue_result
    
    # Wait for completion (like the sync version)
    start_time = time.time()
    timeout = 720
    
    while time.time() - start_time < timeout:
        progress = check_research_progress(latest_session_id)
        
        if "✅ Research completed" in progress:
            return get_research_results(latest_session_id)
        elif "❌" in progress:
            return progress
        
        time.sleep(2)
    
    return f"⏰ Research is taking longer than expected. Session {latest_session_id} may still be running."

@mcp.tool()
def get_current_thread_info() -> str:
    """
    Get information about current research threads.
    Shows all active sessions for backward compatibility.
    
    Returns:
        Thread information or status
    """
    return list_active_sessions()

@mcp.tool()
def check_research_status() -> str:
    """Check if the Deep Research server is running."""
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
        if response.status_code == 200:
            return "✅ Deep Research server is running and ready"
        else:
            return f"❌ Server responded with status {response.status_code}"
    except Exception as e:
        return f"❌ Deep Research server not available: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")