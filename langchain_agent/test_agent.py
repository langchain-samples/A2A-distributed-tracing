#!/usr/bin/env python3
"""Test script to verify the LangChain agent is working.

Run this script after starting the agent server with:
    cd langchain_agent && langgraph dev --port 2024
"""

import asyncio
import aiohttp
import uuid
import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)


async def test_agent(assistant_id, port=2024):
    """Test the LangChain agent via A2A protocol."""
    url = f"http://127.0.0.1:{port}/a2a/{assistant_id}"
    
    # Generate a consistent thread ID for this test session
    thread_id = str(uuid.uuid4())
    session_id = thread_id  # Use same ID for session tracking
    
    test_cases = [
        "Hello! Can you help me with fluid dynamics?",
        "What is a simplified Navier-Stokes equation?",
        "Can you explain the continuity equation?",
    ]
    
    print("Testing LangChain Agent")
    print("=" * 60)
    print(f"Agent URL: {url}")
    print(f"Thread ID: {thread_id}")
    print(f"Session ID: {session_id}")
    print("=" * 60)
    print()
    
    async with aiohttp.ClientSession() as session:
        for i, question in enumerate(test_cases, 1):
            print(f"--- Test {i} ---")
            print(f"Question: {question}")
            
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": question}]
                    },
                    "messageId": str(uuid.uuid4()),
                    "thread": {"threadId": thread_id}
                },
                "metadata": {"session_id": session_id}
            }
            
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "result" in result and "artifacts" in result["result"]:
                            artifacts = result["result"]["artifacts"]
                            if artifacts and len(artifacts) > 0:
                                if "parts" in artifacts[0] and len(artifacts[0]["parts"]) > 0:
                                    text = artifacts[0]["parts"][0].get("text", "")
                                    print(f"✅ Response: {text}")
                                else:
                                    print(f"⚠️  Unexpected response format: {result}")
                            else:
                                print(f"⚠️  No artifacts in response: {result}")
                        else:
                            print(f"⚠️  Unexpected response: {result}")
                    else:
                        text = await response.text()
                        print(f"❌ Error {response.status}: {text[:200]}")
            except Exception as e:
                print(f"❌ Exception: {e}")
            
            print()


def main():
    """Main entry point."""
    assistant_id = os.getenv("LANGCHAIN_ASSISTANT_ID")
    
    if len(sys.argv) > 1:
        assistant_id = sys.argv[1]
    
    if not assistant_id:
        print("Error: Assistant ID is required")
        print()
        print("Usage:")
        print("  python test_agent.py <assistant_id>")
        print()
        print("Or set environment variable:")
        print("  export LANGCHAIN_ASSISTANT_ID=<assistant_id>")
        print()
        print("To get the assistant_id:")
        print("  1. Start the agent: cd langchain_agent && langgraph dev --port 2024")
        print("  2. Copy the assistant_id from the output")
        sys.exit(1)
    
    port = int(os.getenv("LANGCHAIN_PORT", "2024"))
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    
    asyncio.run(test_agent(assistant_id, port))


if __name__ == "__main__":
    main()
