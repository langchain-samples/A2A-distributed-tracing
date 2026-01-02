"""LangChain v1 A2A conversational agent.

Supports the A2A protocol with messages input for conversational interactions.
Uses LangChain v1's create_agent directly without manual LangGraph construction.
Uses middleware for state modifications and custom behavior.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentState, before_model, after_model
from langchain_openai import ChatOpenAI
from langgraph.runtime import Runtime

load_dotenv()

# Initialize the model
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=100,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# System prompt for the agent
system_prompt = (
    "You are a helpful conversational agent specialized in fluid dynamics. "
    "Your main task is to calculate simplified versions of the Navier-Stokes equations. "
    "You will communicate with an expert mathematics professor who has mathematical tools "
    "available to help with calculations. When you need to perform mathematical computations, "
    "delegate them to the mathematics professor. Keep responses brief and engaging, and "
    "focus on providing clear mathematical solutions when asked about fluid dynamics problems."
)


# Middleware for handling A2A message format conversion
@before_model
def convert_a2a_messages(state: AgentState, runtime: Runtime) -> Dict[str, Any] | None:
    """Convert A2A message format to LangChain message format.
    
    This middleware ensures messages are in the correct format for the agent.
    """
    messages = state.get("messages", [])
    
    # Convert A2A format (dict with role/content) to LangChain format if needed
    converted_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            # Already in dict format, keep as is
            converted_messages.append(msg)
        elif hasattr(msg, "role") and hasattr(msg, "content"):
            # Convert message object to dict
            converted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        else:
            # Keep original format
            converted_messages.append(msg)
    
    if converted_messages != messages:
        return {"messages": converted_messages}
    return None


@after_model
def ensure_response_format(state: AgentState, runtime: Runtime) -> Dict[str, Any] | None:
    """Ensure the response is in the correct format for A2A protocol.
    
    This middleware ensures the last message has the correct structure.
    """
    messages = state.get("messages", [])
    if not messages:
        return None
    
    last_message = messages[-1]
    
    # Ensure the last message is in dict format for A2A compatibility
    if not isinstance(last_message, dict):
        if hasattr(last_message, "role") and hasattr(last_message, "content"):
            # Convert to dict format
            new_messages = messages[:-1] + [{
                "role": last_message.role,
                "content": last_message.content if hasattr(last_message, "content") else str(last_message)
            }]
            return {"messages": new_messages}
    
    return None


# Create the agent using LangChain v1's create_agent directly
# No manual LangGraph StateGraph construction - create_agent handles it internally
# Use middleware for any state modifications or custom behavior
agent = create_agent(
    model=model,
    tools=[],  # No tools initially - can be extended
    system_prompt=system_prompt,
    middleware=[convert_a2a_messages],
)

