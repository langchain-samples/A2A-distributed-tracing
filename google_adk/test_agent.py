#!/usr/bin/env python3
"""Simple test script to verify the Google ADK agent is working.

Run this script after starting the agent server with:
    uvicorn google_adk.agent:a2a_app --host localhost --port 8002
"""

import asyncio
import aiohttp
import json


async def test_endpoint(session, url, question, test_num):
    """Test a specific endpoint with a question."""
    # Based on the error, messageId should be inside the message object
    payload = {
        "jsonrpc": "2.0",
        "id": str(test_num),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": question}],
                "messageId": f"msg-{test_num}"
            },
            "thread": {"threadId": "test-thread-1"}
        }
    }
    
    try:
        async with session.post(
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                result = await response.json()
                # Extract the response text
                if "result" in result and "artifacts" in result["result"]:
                    artifacts = result["result"]["artifacts"]
                    if artifacts and "parts" in artifacts[0]:
                        text = artifacts[0]["parts"][0].get("text", "")
                        return True, text
                    else:
                        return True, json.dumps(result, indent=2)
                else:
                    return True, json.dumps(result, indent=2)
            else:
                text = await response.text()
                return False, f"Error {response.status}: {text[:200]}"
    except Exception as e:
        return False, f"Exception: {e}"


async def test_agent():
    """Test the calculator agent via A2A protocol."""
    # When using to_a2a() for a single agent, the endpoint is at root
    url = "http://localhost:8002/"
    
    test_cases = [
        "What is 5 + 3?"
    ]
    
    print("Testing Google ADK Calculator Agent")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        for i, question in enumerate(test_cases, 1):
            print(f"\n--- Test {i} ---")
            print(f"Question: {question}")
            success, result = await test_endpoint(session, url, question, i)
            if success:
                print(f"✅ Response: {result}")
            else:
                print(f"❌ Error: {result}")
                # If we get an error, try to parse it for debugging
                try:
                    error_data = json.loads(result.split("Error")[-1] if "Error" in result else result)
                    if isinstance(error_data, dict) and "error" in error_data:
                        print(f"   Error details: {error_data['error'].get('message', 'Unknown error')}")
                except:
                    pass


if __name__ == "__main__":
    print("Testing Google ADK Calculator Agent")
    print("=" * 50)
    print("Make sure the agent server is running:")
    print("  uvicorn google_adk.agent:a2a_app --host localhost --port 8002")
    print("=" * 50)
    asyncio.run(test_agent())
