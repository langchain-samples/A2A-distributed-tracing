# A2A Distributed Tracing Project

This project demonstrates Agent-to-Agent (A2A) communication between different agent frameworks, enabling distributed tracing and conversation across multiple agent implementations.

## Project Structure

```
A2A-distributed-tracing/
├── langgraph_agent/      # LangGraph-based agent
│   ├── agent.py          # Main agent implementation
│   ├── test_agent.py     # Test script for this agent
│   └── langgraph.json    # LangGraph configuration
├── langchain_agent/      # LangChain v1-based agent
│   ├── agent.py          # Main agent implementation
│   ├── test_agent.py     # Test script for this agent
│   └── langgraph.json    # LangGraph configuration
├── google_adk/           # Google ADK-based agent
│   ├── agent.py          # Main agent implementation
│   └── test_agent.py     # Test script for this agent
└── test_agent_conversation.py  # Multi-agent conversation test
```

## Overview

This project contains three different agent implementations, all communicating via the A2A protocol:

1. **LangGraph Agent** (`langgraph_agent/`): Uses LangGraph's StateGraph directly
2. **LangChain Agent** (`langchain_agent/`): Uses LangChain v1's `create_agent` API with middleware
3. **Google ADK Agent** (`google_adk/`): Uses Google ADK's `to_a2a()` function

All agents are specialized in fluid dynamics and Navier-Stokes equations, and can communicate with a mathematics professor (Google ADK agent) for calculations.

## Prerequisites

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Or using Homebrew on macOS:
   ```bash
   brew install uv
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_API_KEY=your_google_api_key_here  # Optional, for Google ADK
   ```

## Testing Individual Agents

Each agent folder contains a `test_agent.py` script to test that agent independently:

### LangGraph Agent

```bash
cd langgraph_agent
uv run langgraph dev --port 2024
# In another terminal:
uv run python test_agent.py <assistant_id>
```

### LangChain Agent

```bash
cd langchain_agent
uv run langgraph dev --port 2026
# In another terminal:
uv run python test_agent.py <assistant_id>
```

### Google ADK Agent

```bash
uv run uvicorn google_adk.agent:a2a_app --host localhost --port 8002
# In another terminal:
uv run python google_adk/test_agent.py
```

## Running Multi-Agent Conversations

The `test_agent_conversation.py` script demonstrates A2A communication between agents:

### Prerequisites

1. **Start LangChain agent:**
   ```bash
   cd langchain_agent
   uv run langgraph dev --port 2024
   ```
   Copy the `assistant_id` from the output.

2. **Start Google ADK agent:**
   ```bash
   uv run uvicorn google_adk.agent:a2a_app --host localhost --port 8002
   ```

### Run Conversation

```bash
uv run python test_agent_conversation.py <langchain_assistant_id>
```

Or with environment variable:
```bash
export LANGCHAIN_ASSISTANT_ID=<assistant_id>
uv run python test_agent_conversation.py
```

The script will:
- Create consistent thread IDs for each agent
- Add `session_id` in metadata to group traces in LangSmith
- Simulate a conversation between LangChain and Google ADK agents
- Maintain conversation context across multiple rounds

## Agent Details

### LangGraph Agent

- **Location**: `langgraph_agent/`
- **Port**: 2024
- **Implementation**: Uses LangGraph's `StateGraph` directly
- **System Prompt**: Specialized in fluid dynamics and Navier-Stokes equations
- **Features**: Direct StateGraph construction, custom state management

### LangChain Agent

- **Location**: `langchain_agent/`
- **Port**: 2024 (configurable)
- **Implementation**: Uses LangChain v1's `create_agent` API
- **System Prompt**: Specialized in fluid dynamics and Navier-Stokes equations
- **Features**: 
  - Uses `create_agent` directly (no manual StateGraph)
  - Custom middleware for A2A message format conversion
  - Extensible with LangChain tools

### Google ADK Agent

- **Location**: `google_adk/`
- **Port**: 8002
- **Implementation**: Uses Google ADK's `to_a2a()` function
- **Functionality**: Calculator agent with mathematical operations
- **Features**:
  - Auto-generated agent card
  - Exposed via uvicorn
  - Acts as "mathematics professor" for other agents

## A2A Protocol Details

### LangGraph/LangChain Agents (Standard A2A)

- **Endpoint**: `http://localhost:{port}/a2a/{assistant_id}`
- **Format**: Standard A2A protocol
- **Thread ID**: Used in `thread.threadId` parameter
- **Metadata**: `session_id` added at payload root level for LangSmith tracing

### Google ADK Agent (to_a2a format)

- **Endpoint**: `http://localhost:8002/` (root endpoint)
- **Format**: `to_a2a()` specific format
- **Thread ID**: Used in `thread.threadId` parameter
- **Message ID**: Inside `message` object (not at params level)
- **Metadata**: `session_id` added at payload root level for LangSmith tracing

## Distributed Tracing

The project uses `session_id` in metadata to group traces in LangSmith:

```python
payload = {
    "jsonrpc": "2.0",
    "id": str(uuid.uuid4()),
    "method": "message/send",
    "params": {...},
    "metadata": {"session_id": thread_id}  # Groups traces in LangSmith
}
```

This allows you to:
- Track complete conversations across multiple agents
- Group related traces by session
- Analyze agent-to-agent communication patterns
- Debug distributed agent interactions

## Development

### Adding New Agents

1. Create a new folder (e.g., `new_agent/`)
2. Implement the agent following A2A protocol
3. Add a `test_agent.py` script
4. Update this README with agent details

### Extending Agents

- **LangChain Agent**: Add tools using `@tool` decorator and pass to `create_agent()`
- **LangGraph Agent**: Add nodes to the StateGraph
- **Google ADK Agent**: Add functions as tools to the Agent

## Troubleshooting

### Port Conflicts

- LangGraph/LangChain agents: Change port in `uv run langgraph dev --port {port}`
- Google ADK agent: Change port in `agent.py` or uvicorn command

### Agent Not Responding

- Check server logs for errors
- Verify agent card endpoint is accessible
- Ensure all dependencies are installed: `uv sync`
- Check environment variables are set correctly

### Import Errors

- Reinstall dependencies: `uv sync`
- Use `uv run` to ensure the correct environment is used

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain v1 Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [Google ADK Documentation](https://github.com/google/adk-python)
- [A2A Protocol Specification](https://a2a-protocol.org/)
