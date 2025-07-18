#!/usr/bin/env python3
"""
Startup script to run both LangGraph server and Streamlit app locally.
This provides a complete local research environment.
"""

import subprocess
import time
import sys
import os
import signal
import requests
from threading import Thread

def check_server_health(url="http://127.0.0.1:2024", timeout=5):
    """Check if the LangGraph server is running."""
    try:
        response = requests.get(f"{url}/health", timeout=timeout)
        return response.status_code == 200
    except:
        return False

def start_langgraph_server():
    """Start the LangGraph development server."""
    print("🚀 Starting LangGraph server...")
    cmd = [
        "uvx", "--refresh", "--from", "langgraph-cli[inmem]", 
        "--with-editable", ".", "--python", "3.11", 
        "langgraph", "dev", "--allow-blocking", "--no-browser"
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Monitor server startup
        for line in iter(process.stdout.readline, ''):
            print(f"[LangGraph] {line.strip()}")
            if "Server started" in line:
                print("✅ LangGraph server is ready!")
                break
                
        return process
    except Exception as e:
        print(f"❌ Failed to start LangGraph server: {e}")
        return None

def start_streamlit_app():
    """Start the Streamlit application."""
    print("🎨 Starting Streamlit app...")
    cmd = ["streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Monitor Streamlit startup
        for line in iter(process.stdout.readline, ''):
            print(f"[Streamlit] {line.strip()}")
            if "You can now view your Streamlit app" in line:
                print("✅ Streamlit app is ready!")
                break
                
        return process
    except Exception as e:
        print(f"❌ Failed to start Streamlit app: {e}")
        return None

def wait_for_server(max_attempts=30):
    """Wait for LangGraph server to be ready."""
    print("⏳ Waiting for LangGraph server to be ready...")
    
    for attempt in range(max_attempts):
        if check_server_health():
            print("✅ LangGraph server is healthy!")
            return True
        
        print(f"   Attempt {attempt + 1}/{max_attempts}...")
        time.sleep(2)
    
    print("❌ LangGraph server failed to start properly")
    return False

def main():
    """Main function to orchestrate the startup."""
    print("🔍 Open Deep Research - Local Server Startup")
    print("=" * 50)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("Please create a .env file with your Azure OpenAI credentials.")
        print("See .env.example for reference.")
        return
    
    processes = []
    
    try:
        # Start LangGraph server in background
        langgraph_process = start_langgraph_server()
        if not langgraph_process:
            return
        processes.append(langgraph_process)
        
        # Wait for server to be ready
        if not wait_for_server():
            return
        
        # Start Streamlit app
        streamlit_process = start_streamlit_app()
        if not streamlit_process:
            return
        processes.append(streamlit_process)
        
        print("\n" + "=" * 50)
        print("🎉 Both services are running!")
        print("📊 LangGraph API: http://127.0.0.1:2024")
        print("🎨 Streamlit App: http://127.0.0.1:8501")
        print("📚 API Docs: http://127.0.0.1:2024/docs")
        print("\n🌐 Access from other devices on your network:")
        print("🎨 Streamlit App: http://YOUR_LOCAL_IP:8501")
        print("\nPress Ctrl+C to stop both services")
        print("=" * 50)
        
        # Keep running until interrupted
        try:
            while True:
                # Check if processes are still running
                for process in processes:
                    if process.poll() is not None:
                        print(f"⚠️  Process {process.pid} has stopped")
                        return
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down services...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        # Clean up processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        print("✅ Services stopped")

if __name__ == "__main__":
    main()