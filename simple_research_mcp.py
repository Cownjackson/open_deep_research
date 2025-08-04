from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import requests
import time

load_dotenv()

mcp = FastMCP("Deep Research")

# Simple configuration
LANGGRAPH_API_URL = "http://localhost:2024"
HEADERS = {"Authorization": "Bearer dev-token"}

# Global state - keep it simple
current_thread_id = None
assistant_id = None

def get_assistant():
    """Get or create assistant - simple approach."""
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
    """Create a new thread - simple approach."""
    try:
        response = requests.post(f"{LANGGRAPH_API_URL}/threads", json={}, headers=HEADERS)
        if response.status_code in [200, 201]:
            return response.json()["thread_id"]
    except:
        pass
    return None

@mcp.tool()
def research_question(question: str) -> str:
    """
    Research a question using the Deep Researcher. This is the main research tool.
    
    Args:
        question: The research question or topic to investigate
    
    Returns:
        The research results or status
    """
    global current_thread_id
    
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
    current_thread_id = create_thread()
    if not current_thread_id:
        return "❌ Could not create research thread"
    
    try:
        # Start research
        payload = {
            "assistant_id": assistant,
            "input": {"messages": [{"role": "user", "content": question}]}
        }
        response = requests.post(f"{LANGGRAPH_API_URL}/threads/{current_thread_id}/runs", 
                               json=payload, headers=HEADERS)
        
        if response.status_code != 200:
            return f"❌ Failed to start research: {response.text}"
        
        run_id = response.json()["run_id"]
        
        # Wait for completion (simple polling)
        for _ in range(60):  # 2 minutes max
            time.sleep(2)
            status_response = requests.get(f"{LANGGRAPH_API_URL}/threads/{current_thread_id}/runs/{run_id}", 
                                         headers=HEADERS)
            if status_response.status_code == 200:
                status = status_response.json().get("status")
                if status == "success":
                    # Get results
                    state_response = requests.get(f"{LANGGRAPH_API_URL}/threads/{current_thread_id}/state", 
                                                headers=HEADERS)
                    if state_response.status_code == 200:
                        state = state_response.json()
                        final_report = state.get("values", {}).get("final_report")
                        if final_report:
                            return f"# Research Results\n\n**Question:** {question}\n\n{final_report}"
                elif status in ["error", "timeout", "interrupted"]:
                    return f"❌ Research failed with status: {status}"
        
        return "⏰ Research is taking longer than expected. Check back later."
        
    except Exception as e:
        return f"❌ Research error: {str(e)}"

@mcp.tool()
def check_research_status() -> str:
    """
    Check if the Deep Research server is running and ready.
    
    Returns:
        Server status message
    """
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
        if response.status_code == 200:
            return "✅ Deep Research server is running and ready"
        else:
            return f"❌ Server responded with status {response.status_code}"
    except Exception as e:
        return f"❌ Deep Research server not available: {str(e)}"

@mcp.tool()
def get_current_thread_info() -> str:
    """
    Get information about the current research thread.
    
    Returns:
        Thread information or status
    """
    if not current_thread_id:
        return "No active research thread"
    
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/threads/{current_thread_id}/state", headers=HEADERS)
        if response.status_code == 200:
            state = response.json()
            return f"Thread ID: {current_thread_id}\nStatus: {state.get('status', 'unknown')}"
        else:
            return f"Could not get thread info: {response.status_code}"
    except Exception as e:
        return f"Error getting thread info: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")