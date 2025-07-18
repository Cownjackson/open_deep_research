#!/usr/bin/env python3
"""
Streamlit interface for Open Deep Research
A simple web UI to interact with the Deep Research agent locally.
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime
import uuid

# Configuration
LANGGRAPH_API_URL = "http://localhost:2024"

def check_server_health():
    """Check if the LangGraph server is running."""
    try:
        # Try the docs endpoint since we know it works
        response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
        return response.status_code == 200
    except:
        try:
            # Fallback to root endpoint
            response = requests.get(LANGGRAPH_API_URL, timeout=5)
            return response.status_code in [200, 404]  # 404 is also OK, means server is running
        except:
            return False

def create_thread():
    """Create a new conversation thread."""
    try:
        # Add authorization header for development
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dev-token"
        }
        
        response = requests.post(f"{LANGGRAPH_API_URL}/threads", json={}, headers=headers)
        if response.status_code in [200, 201]:
            result = response.json()
            # Handle different possible response formats
            if "thread_id" in result:
                return result["thread_id"]
            elif "id" in result:
                return result["id"]
            else:
                st.error(f"Unexpected response format: {result}")
                return None
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Failed to create thread: {e}")
        return None

def get_assistant_id():
    """Get the Deep Researcher assistant ID."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dev-token"
        }
        
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants/search", json={}, headers=headers)
        if response.status_code == 200:
            assistants = response.json()
            
            # Debug: Show what assistants we found
            st.write(f"Found {len(assistants)} assistants:")
            for i, assistant in enumerate(assistants):
                st.write(f"Assistant {i}: {assistant}")
            
            # Look for the Deep Researcher assistant
            for assistant in assistants:
                if assistant.get("name") == "Deep Researcher":
                    return assistant.get("assistant_id")
            
            # If not found by name, return the first one
            if assistants:
                first_assistant = assistants[0]
                assistant_id = first_assistant.get("assistant_id") or first_assistant.get("id")
                st.info(f"Using first available assistant: {first_assistant.get('name', 'Unknown')} (ID: {assistant_id})")
                return assistant_id
                
        else:
            st.error(f"Assistant search failed: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        st.error(f"Failed to get assistant ID: {e}")
        return None

def submit_research_query(thread_id, question):
    """Submit a research query and stream the response."""
    try:
        # Try different approaches to submit the research query
        
        # Approach 1: Try with graph name directly
        url = f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/stream"
        payload = {
            "graph_id": "Deep Researcher",  # Use graph_id instead of assistant_id
            "input": {
                "messages": [{"role": "user", "content": question}]
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dev-token"
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True)
        
        if response.status_code == 200:
            return response
        
        # Approach 2: Try without graph_id/assistant_id (some APIs auto-detect)
        payload = {
            "input": {
                "messages": [{"role": "user", "content": question}]
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True)
        
        if response.status_code == 200:
            return response
        
        # Approach 3: Try creating an assistant first
        assistant_id = create_assistant_if_needed()
        if assistant_id:
            payload = {
                "assistant_id": assistant_id,
                "input": {
                    "messages": [{"role": "user", "content": question}]
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, stream=True)
            
            if response.status_code == 200:
                return response
        
        st.error(f"All approaches failed. Last API Error: {response.status_code} - {response.text}")
        return None
            
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def create_assistant_if_needed():
    """Create the Deep Researcher assistant if it doesn't exist."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer dev-token"
        }
        
        # Try to create an assistant
        payload = {
            "graph_id": "Deep Researcher",
            "name": "Deep Researcher",
            "description": "AI-powered deep research agent"
        }
        
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants", json=payload, headers=headers)
        
        if response.status_code in [200, 201]:
            result = response.json()
            assistant_id = result.get("assistant_id") or result.get("id")
            st.success(f"Created assistant: {assistant_id}")
            return assistant_id
        else:
            st.warning(f"Could not create assistant: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.warning(f"Failed to create assistant: {e}")
        return None

def parse_streaming_response(response):
    """Parse the streaming response from LangGraph."""
    messages = []
    final_report = None
    
    try:
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    if data_str.strip() and data_str != '[DONE]':
                        try:
                            data = json.loads(data_str)
                            
                            # Handle different event types
                            if isinstance(data, list) and len(data) >= 2:
                                event_type, event_data = data[0], data[1]
                                
                                if event_type == "messages/partial":
                                    # Handle partial message updates
                                    if isinstance(event_data, list):
                                        for msg in event_data:
                                            if isinstance(msg, dict) and msg.get("content"):
                                                messages.append({
                                                    "type": "partial",
                                                    "content": msg["content"],
                                                    "timestamp": datetime.now()
                                                })
                                
                                elif event_type == "messages/complete":
                                    # Handle complete messages
                                    if isinstance(event_data, list):
                                        for msg in event_data:
                                            if isinstance(msg, dict) and msg.get("content"):
                                                messages.append({
                                                    "type": "complete",
                                                    "content": msg["content"],
                                                    "timestamp": datetime.now()
                                                })
                                
                                elif event_type == "values":
                                    # Handle final values/report
                                    if isinstance(event_data, dict):
                                        if "final_report" in event_data:
                                            final_report = event_data["final_report"]
                                        elif "messages" in event_data:
                                            # Extract final message
                                            msgs = event_data["messages"]
                                            if msgs and isinstance(msgs[-1], dict):
                                                final_report = msgs[-1].get("content")
                                
                        except json.JSONDecodeError:
                            continue
                            
    except Exception as e:
        st.error(f"Error parsing response: {e}")
    
    return messages, final_report

def main():
    st.set_page_config(
        page_title="Open Deep Research",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Open Deep Research")
    st.markdown("*AI-powered deep research agent using Azure OpenAI*")
    
    # Check server status
    if not check_server_health():
        st.error("⚠️ LangGraph server is not running!")
        st.markdown("""
        Please start the server first:
        ```bash
        uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev --allow-blocking
        ```
        """)
        return
    
    st.success("✅ Connected to LangGraph server")
    
    # Initialize session state
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "research_history" not in st.session_state:
        st.session_state.research_history = []
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Thread management
        if st.button("🔄 New Research Session"):
            st.session_state.thread_id = create_thread()
            st.session_state.research_history = []
            if st.session_state.thread_id:
                st.success(f"New session created!")
            else:
                st.error("Failed to create new session")
        
        if st.session_state.thread_id:
            st.info(f"Session ID: {st.session_state.thread_id[:8]}...")
        
        st.markdown("---")
        
        # Research tips
        st.header("💡 Research Tips")
        st.markdown("""
        **Good research questions:**
        - "Analyze the current state of renewable energy adoption in Europe"
        - "What are the latest developments in quantum computing?"
        - "Compare different approaches to treating diabetes"
        
        **The agent will:**
        - Search for current information
        - Analyze multiple sources
        - Generate a comprehensive report
        """)
    
    # Main interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Research Query")
        
        # Research input
        research_question = st.text_area(
            "What would you like to research?",
            height=100,
            placeholder="Enter your research question here..."
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            submit_button = st.button("🔍 Start Research", type="primary")
        
        # Handle research submission
        if submit_button and research_question.strip():
            if not st.session_state.thread_id:
                st.session_state.thread_id = create_thread()
            
            if st.session_state.thread_id:
                with st.spinner("🔍 Conducting research... This may take a few minutes."):
                    # Create placeholder for streaming updates
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    
                    # Submit query
                    response = submit_research_query(st.session_state.thread_id, research_question)
                    
                    if response:
                        # Parse streaming response
                        messages, final_report = parse_streaming_response(response)
                        
                        # Update progress
                        progress_bar.progress(100)
                        status_placeholder.success("✅ Research completed!")
                        
                        # Store in history
                        research_entry = {
                            "question": research_question,
                            "report": final_report,
                            "timestamp": datetime.now(),
                            "messages": messages
                        }
                        st.session_state.research_history.append(research_entry)
                        
                        # Display result
                        if final_report:
                            st.success("Research completed successfully!")
                        else:
                            st.warning("Research completed but no final report was generated.")
                    else:
                        progress_bar.progress(0)
                        status_placeholder.error("❌ Research failed")
            else:
                st.error("Failed to create research session")
    
    with col2:
        st.header("Server Status")
        
        # Server info
        try:
            response = requests.get(f"{LANGGRAPH_API_URL}/docs")
            if response.status_code == 200:
                st.success("🟢 API Server: Online")
            else:
                st.error("🔴 API Server: Error")
        except:
            st.error("🔴 API Server: Offline")
        
        st.markdown(f"**Server URL:** `{LANGGRAPH_API_URL}`")
        
        # Quick actions
        st.markdown("---")
        st.header("Quick Actions")
        
        if st.button("📊 View API Docs"):
            st.markdown(f"[Open API Documentation]({LANGGRAPH_API_URL}/docs)")
        
        if st.button("🧹 Clear History"):
            st.session_state.research_history = []
            st.success("History cleared!")
    
    # Display research history
    if st.session_state.research_history:
        st.header("📚 Research History")
        
        for i, entry in enumerate(reversed(st.session_state.research_history)):
            with st.expander(f"🔍 {entry['question'][:100]}..." if len(entry['question']) > 100 else f"🔍 {entry['question']}", expanded=(i==0)):
                st.markdown(f"**Asked:** {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                if entry['report']:
                    st.markdown("### 📄 Research Report")
                    st.markdown(entry['report'])
                else:
                    st.warning("No final report available for this research.")
                
                # Download option
                if entry['report']:
                    st.download_button(
                        label="📥 Download Report",
                        data=entry['report'],
                        file_name=f"research_report_{entry['timestamp'].strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )

if __name__ == "__main__":
    main()