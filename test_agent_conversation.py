#!/usr/bin/env python3
"""Test script to simulate a conversation between LangChain and Google ADK agents.

This script demonstrates A2A communication between:
- LangChain agent (port 2026) - uses standard A2A format
- Google ADK agent (port 8002) - uses to_a2a() format

Prerequisites:
1. Start LangChain agent: cd langchain_agent && langgraph dev --port 2026
   (Copy the assistant_id from the output)
2. Start Google ADK agent: uvicorn google_adk.agent:a2a_app --host localhost --port 8002
"""

import asyncio
import aiohttp
import os
import sys
import uuid
from dotenv import load_dotenv

load_dotenv(override=True)


async def send_to_langchain(session, assistant_id, text, thread_id):
    """Send a message to LangChain agent using standard A2A format.
    
    Uses consistent thread_id to maintain conversation context and adds
    session_id in metadata to group traces in LangSmith.
    """
    url = f"http://127.0.0.1:2024/a2a/{assistant_id}"
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}]
            },
            "messageId": str(uuid.uuid4()),
            "thread": {"threadId": thread_id}
        },
        "metadata": {"session_id": thread_id}  # Groups traces in LangSmith
    }
    
    headers = {"Accept": "application/json"}
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return True, result["result"]["artifacts"][0]["parts"][0]["text"]
            else:
                text = await response.text()
                return False, f"Error {response.status}: {text[:200]}"
    except Exception as e:
        return False, f"Exception: {str(e)}"


async def send_to_google_adk(session, text, thread_id):
    """Send a message to Google ADK agent using to_a2a() format.
    
    Google ADK to_a2a() expects:
    - messageId inside the message object (not at params level)
    - Uses consistent thread_id to maintain conversation context
    - Adds session_id in metadata to group traces in LangSmith
    """
    url = "http://localhost:8002/"
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": str(uuid.uuid4())
            },
            "thread": {"threadId": thread_id}
        },
        "metadata": {"session_id": thread_id}  # Groups traces in LangSmith
    }
    
    headers = {"Accept": "application/json"}
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return True, result["result"]["artifacts"][0]["parts"][0]["text"]
            else:
                text = await response.text()
                return False, f"Error {response.status}: {text[:200]}"
    except Exception as e:
        return False, f"Exception: {str(e)}"


async def simulate_conversation(langchain_assistant_id, num_rounds=5, initial_message=None):
    """Simulate a conversation between LangChain and Google ADK agents."""
    
    if initial_message is None:
        initial_message = "Repeat this exact message back to me: Hello! I'm a LangChain agent. Can you help me calculate something?"
    
    print("=" * 70)
    print("Agent-to-Agent Conversation Simulation")
    print("=" * 70)
    print(f"LangChain Agent: http://127.0.0.1:2024/a2a/{langchain_assistant_id}")
    print(f"Google ADK Agent: http://localhost:8002/")
    print("=" * 70)
    print()
    
    message = initial_message
    
    # Generate consistent thread IDs (used as session_id in metadata for LangSmith)
    langchain_thread_id = str(uuid.uuid4())
    adk_thread_id = str(uuid.uuid4())
    
    print(f"📎 Session IDs - LangChain: {langchain_thread_id}, ADK: {adk_thread_id}")
    print("(These will be used as session_id in metadata to group traces in LangSmith)")
    print()
    
    async with aiohttp.ClientSession() as session:
        for i in range(num_rounds):
            print(f"--- Round {i + 1} ---")
            print(f"📎 Thread IDs - LangChain: {langchain_thread_id}, ADK: {adk_thread_id}")
            print()
            
            # LangChain agent responds
            print(f"📤 Sending to LangChain: {message[:60]}...")
            success, response = await send_to_langchain(
                session, langchain_assistant_id, message, langchain_thread_id
            )
            
            if success:
                print(f"🟡 LangChain Agent: {response}")
                message = response
            else:
                print(f"❌ LangChain Error: {response}")
                break
            
            print()
            
            # Google ADK agent responds
            print(f"📤 Sending to Google ADK: {message[:60]}...")
            success, response = await send_to_google_adk(
                session, message, adk_thread_id
            )
            
            if success:
                print(f"🟢 Google ADK Agent: {response}")
                message = response
            else:
                print(f"❌ Google ADK Error: {response}")
                break
            
            print()
            print("-" * 70)
            print()
            
            # Small delay between rounds
            await asyncio.sleep(0.5)
    
    print("=" * 70)
    print("Conversation completed!")
    print("=" * 70)


def main():
    """Main entry point."""
    # Get LangChain assistant ID from environment or command line
    langchain_assistant_id = os.getenv("LANGCHAIN_ASSISTANT_ID")
    
    if len(sys.argv) > 1:
        langchain_assistant_id = sys.argv[1]
    
    if not langchain_assistant_id:
        print("Error: LangChain assistant ID is required")
        print()
        print("Usage:")
        print("  python test_agent_conversation.py <langchain_assistant_id>")
        print()
        print("Or set environment variable:")
        print("  export LANGCHAIN_ASSISTANT_ID=<assistant_id>")
        print()
        print("To get the assistant_id:")
        print("  1. Start LangChain agent: cd langchain_agent && langgraph dev --port 2026")
        print("  2. Copy the assistant_id from the output")
        sys.exit(1)
    
    # Get number of rounds (optional)
    num_rounds = int(os.getenv("NUM_ROUNDS", "5"))
    if len(sys.argv) > 2:
        num_rounds = int(sys.argv[2])
    
    # Get initial message (optional)
    initial_message = os.getenv("INITIAL_MESSAGE")
    if len(sys.argv) > 3:
        initial_message = sys.argv[3]
    
    print("Starting conversation simulation...")
    print(f"LangChain Assistant ID: {langchain_assistant_id}")
    print(f"Number of rounds: {num_rounds}")
    print()
    
    asyncio.run(simulate_conversation(
        langchain_assistant_id,
        num_rounds=num_rounds,
        initial_message=initial_message
    ))


if __name__ == "__main__":
    main()
