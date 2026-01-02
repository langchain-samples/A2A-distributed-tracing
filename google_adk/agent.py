"""Minimal Google ADK agent exposed via A2A protocol.

This agent demonstrates a simple calculator agent that can perform
basic mathematical operations and is exposed via the A2A protocol.
"""

from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.genai import types
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
import os

load_dotenv()

def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely.

    Args:
        expression: A string containing a mathematical expression (e.g., "2 + 2", "10 * 5").

    Returns:
        A string with the result of the calculation or an error message.
    """
    try:
        # Use eval with a restricted namespace for basic math operations
        allowed_names = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
        }
        result = eval(expression, allowed_names)
        return f"The result is: {result}"
    except Exception as e:
        return f"Error calculating expression: {str(e)}"


llm = LiteLlm(
    model="openai/gpt-4o",
    api_base="https://api.openai.com/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Create the agent
root_agent = Agent(
    model=llm,
    name="calculator_agent",
    description="A simple calculator agent that can perform basic mathematical operations.",
    instruction="""
        You are a helpful calculator assistant. When users ask you to perform calculations,
        use the calculate tool with a mathematical expression as a string.
        
        Examples:
        - "What is 5 + 3?" -> call calculate("5 + 3")
        - "Calculate 10 * 7" -> call calculate("10 * 7")
        - "What's 100 / 4?" -> call calculate("100 / 4")
        
        Always use the calculate tool for any mathematical operations. Be friendly and clear
        in your responses.
    """,
    tools=[calculate],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.7,
    ),
)

# Expose the agent via A2A protocol
# This creates an A2A-compatible FastAPI app that can be served with uvicorn
a2a_app = to_a2a(root_agent, port=8002)
