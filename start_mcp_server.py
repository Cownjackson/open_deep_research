#!/usr/bin/env python3
"""
Simple script to start the Deep Research MCP server.
Run this after starting your LangGraph API server.
"""

import asyncio
import logging
from mcp_deep_research_server import main

if __name__ == "__main__":
    print("🚀 Starting Deep Research MCP Server...")
    print("Make sure your LangGraph API is running on http://localhost:2024")
    print("Press Ctrl+C to stop")
    
    # Set up basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 MCP Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")