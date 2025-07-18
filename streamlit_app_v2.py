#!/usr/bin/env python3
"""
Simple Streamlit interface for Open Deep Research - V2
Clean, focused implementation that properly extracts the final report.
"""

import streamlit as st
import requests
import json
from datetime import datetime

# Configuration
LANGGRAPH_API_URL = "http://localhost:2024"

def check_server():
    """Simple server health check."""
    try:
        response = requests.get(f"{LANGGRAPH_API_URL}/docs", timeout=5)
        return response.status_code == 200
    except:
        return False

def create_thread():
    """Create a new research thread."""
    try:
        headers = {"Authorization": "Bearer dev-token"}
        response = requests.post(f"{LANGGRAPH_API_URL}/threads", json={}, headers=headers)
        if response.status_code in [200, 201]:
            result = response.json()
            return result.get("thread_id") or result.get("id")
    except Exception as e:
        st.error(f"Failed to create thread: {e}")
    return None

def get_or_create_assistant():
    """Get or create the Deep Researcher assistant."""
    try:
        headers = {"Authorization": "Bearer dev-token"}
        
        # First, try to search for existing assistants
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants/search", json={}, headers=headers)
        if response.status_code == 200:
            assistants = response.json()
            if assistants:
                # Use the first available assistant
                return assistants[0].get("assistant_id") or assistants[0].get("id")
        
        # If no assistants found, create one
        payload = {
            "graph_id": "Deep Researcher",
            "name": "Deep Researcher",
            "description": "AI research agent"
        }
        response = requests.post(f"{LANGGRAPH_API_URL}/assistants", json=payload, headers=headers)
        if response.status_code in [200, 201]:
            result = response.json()
            return result.get("assistant_id") or result.get("id")
            
    except Exception as e:
        st.error(f"Failed to get/create assistant: {e}")
    
    return None

def submit_research(thread_id, question):
    """Submit research query and get the final result."""
    try:
        headers = {"Authorization": "Bearer dev-token"}
        
        # Get assistant ID
        assistant_id = get_or_create_assistant()
        if not assistant_id:
            st.error("Could not get assistant ID")
            return None
        
        # Submit research (non-streaming first to get run_id)
        url = f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs"
        payload = {
            "assistant_id": assistant_id,
            "input": {"messages": [{"role": "user", "content": question}]}
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            st.error(f"Failed to start research: {response.status_code} - {response.text}")
            return None
            
        run_data = response.json()
        run_id = run_data.get("run_id")
        
        if not run_id:
            st.error("No run ID returned")
            return None
        
        # Wait for completion and get final state
        return wait_for_completion(thread_id, run_id, headers)
        
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def wait_for_completion(thread_id, run_id, headers):
    """Wait for the run to complete and get the final state."""
    import time
    
    max_wait = 300  # 5 minutes max
    wait_time = 0
    
    while wait_time < max_wait:
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
                        return state_data.get("values", {}).get("final_report")
                    
                elif status == "error":
                    st.error("Research run failed")
                    return None
                    
            time.sleep(2)
            wait_time += 2
            
        except Exception as e:
            st.error(f"Error checking status: {e}")
            return None
    
    st.error("Research timed out")
    return None



def main():
    st.set_page_config(
        page_title="Open Deep Research V2",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Open Deep Research V2")
    st.markdown("*Simple AI research agent interface*")
    
    # Check server
    if not check_server():
        st.error("⚠️ LangGraph server is not running!")
        st.code("uvx --refresh --from \"langgraph-cli[inmem]\" --with-editable . --python 3.11 langgraph dev --allow-blocking --config langgraph.dev.json")
        return
    
    st.success("✅ Server connected")
    
    # Initialize session state
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "reports" not in st.session_state:
        st.session_state.reports = []
    
    # Main interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header("Research Query")
        
        question = st.text_area(
            "What would you like to research?",
            height=120,
            placeholder="Enter your research question..."
        )
        
        if st.button("🔍 Start Research", type="primary"):
            if not question.strip():
                st.warning("Please enter a research question.")
                return
                
            # Create thread if needed
            if not st.session_state.thread_id:
                st.session_state.thread_id = create_thread()
                
            if not st.session_state.thread_id:
                st.error("Failed to create research session.")
                return
            
            # Submit research
            with st.spinner("🔍 Researching... This may take a few minutes."):
                final_report = submit_research(st.session_state.thread_id, question)
                
                if final_report:
                    st.success("✅ Research completed!")
                    
                    # Display the report
                    st.markdown("### 📄 Research Report")
                    st.markdown(final_report)
                    
                    # Save to history
                    st.session_state.reports.append({
                        "question": question,
                        "report": final_report,
                        "timestamp": datetime.now()
                    })
                    
                    # Download button
                    st.download_button(
                        label="📥 Download Report",
                        data=final_report,
                        file_name=f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
                else:
                    st.error("❌ No final report was generated. Please try again.")
    
    with col2:
        st.header("Status")
        
        if check_server():
            st.success("🟢 Server Online")
        else:
            st.error("🔴 Server Offline")
            
        if st.session_state.thread_id:
            st.info(f"Session: {st.session_state.thread_id[:8]}...")
            
        if st.button("🔄 New Session"):
            st.session_state.thread_id = create_thread()
            if st.session_state.thread_id:
                st.success("New session created!")
        
        if st.button("🧹 Clear History"):
            st.session_state.reports = []
            st.success("History cleared!")
    
    # Research History
    if st.session_state.reports:
        st.header("📚 Research History")
        
        for i, report in enumerate(reversed(st.session_state.reports)):
            with st.expander(f"🔍 {report['question'][:80]}...", expanded=(i==0)):
                st.markdown(f"**Asked:** {report['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                st.markdown("### Report")
                st.markdown(report['report'])
                
                st.download_button(
                    label="📥 Download",
                    data=report['report'],
                    file_name=f"research_{report['timestamp'].strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key=f"download_history_{i}"
                )

if __name__ == "__main__":
    main()