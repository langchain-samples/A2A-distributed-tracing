"""Minimal Google ADK agent exposed via A2A protocol.

This agent demonstrates a simple calculator agent that can perform
basic mathematical operations and is exposed via the A2A protocol.
Includes OpenTelemetry tracing to LangSmith for distributed tracing.
"""

from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.genai import types
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
import os
import logging
from fastapi import Request
from opentelemetry import trace
from opentelemetry.context import set_value, attach
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Import custom OpenTelemetry components
from utils.otel_exporter import (
    TraceModifyingSpanProcessor,
    ModifyingSpanExporter,
)

load_dotenv()

# Set up logging for OpenTelemetry debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
otel_logger = logging.getLogger("opentelemetry")
otel_logger.setLevel(logging.DEBUG)  # Enable detailed OTEL logging

# Configure OpenTelemetry tracing directly to LangSmith
# Project name can be overridden via LANGSMITH_PROJECT environment variable
project_name = os.getenv("LANGSMITH_PROJECT", "agent2agent")
langsmith_api_key = os.getenv("LANGSMITH_API_KEY")

# Get LangSmith endpoint from environment or use default
# For EU region, use: https://eu.api.smith.langchain.com/otel/v1/traces
langsmith_endpoint = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "https://api.smith.langchain.com/otel/v1/traces"
)

logger.info("=" * 60)
logger.info("Configuring OpenTelemetry for LangSmith")
logger.info(f"Endpoint: {langsmith_endpoint}")
logger.info(f"Project: {project_name}")

# Build headers for LangSmith
# Priority: OTEL_EXPORTER_OTLP_HEADERS env var > individual env vars
headers = {}

# Check if OTEL_EXPORTER_OTLP_HEADERS is set (takes precedence)
env_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
if env_headers:
    logger.info("Using OTEL_EXPORTER_OTLP_HEADERS from environment")
    # Parse headers from environment variable
    # Format: "key1=value1,key2=value2" or "key1: value1,key2: value2"
    for header_pair in env_headers.split(","):
        header_pair = header_pair.strip()
        if "=" in header_pair:
            key, value = header_pair.split("=", 1)
            headers[key.strip()] = value.strip()
            # Don't log the full API key value
            if "api" in key.lower() and "key" in key.lower():
                logger.info(f"  Header: {key.strip()}=***")
            else:
                logger.info(f"  Header: {key.strip()}={value.strip()}")
        elif ":" in header_pair:
            key, value = header_pair.split(":", 1)
            headers[key.strip()] = value.strip()
            if "api" in key.lower() and "key" in key.lower():
                logger.info(f"  Header: {key.strip()}=***")
            else:
                logger.info(f"  Header: {key.strip()}={value.strip()}")
else:
    logger.info("Using individual environment variables (LANGSMITH_API_KEY, LANGSMITH_PROJECT)")
    # Fall back to individual environment variables if OTEL_EXPORTER_OTLP_HEADERS not set
    if langsmith_api_key:
        headers["x-api-key"] = langsmith_api_key
        logger.info("  Header: x-api-key=*** (from LANGSMITH_API_KEY)")
    else:
        logger.warning("  WARNING: LANGSMITH_API_KEY not set!")
    if project_name:
        headers["Langsmith-Project"] = project_name
        logger.info(f"  Header: Langsmith-Project={project_name}")

if not headers:
    logger.error("ERROR: No headers configured! Traces will not be sent to LangSmith.")
    logger.error("Please set either:")
    logger.error("  - OTEL_EXPORTER_OTLP_HEADERS='x-api-key=YOUR_KEY,Langsmith-Project=YOUR_PROJECT'")
    logger.error("  - OR set LANGSMITH_API_KEY and LANGSMITH_PROJECT environment variables")

# Create the OTLP exporter for LangSmith
logger.info("Creating OTLPSpanExporter...")
otlp_exporter = OTLPSpanExporter(
    endpoint=langsmith_endpoint,
    headers=headers if headers else None,
    timeout=10,
)

# Configure span filtering patterns from environment variable
# Format: comma-separated regex patterns, e.g., "a2a\.server.*,a2a\.utils.*,EventQueue\..*"
# Default: Filter out a2a.server and a2a.utils spans
filter_patterns_str = os.getenv("OTEL_SPAN_FILTER_PATTERNS", "a2a\\.server.*,a2a\\.utils.*")
filter_patterns_list = [p.strip() for p in filter_patterns_str.split(",") if p.strip()]

# Wrap the exporter with our custom modifying exporter
# This allows us to filter or log traces before they are sent to LangSmith
# The exporter will compile the pattern strings internally
logger.info("Wrapping exporter with ModifyingSpanExporter...")
modifying_exporter = ModifyingSpanExporter(otlp_exporter, filter_patterns=filter_patterns_list)

# Set up the TracerProvider with our custom processor and exporter
logger.info("Setting up TracerProvider with TraceModifyingSpanProcessor and BatchSpanProcessor...")
tracer_provider = TracerProvider()

# Add the modifying span processor FIRST (modifies spans when they end)
modifying_processor = TraceModifyingSpanProcessor()
tracer_provider.add_span_processor(modifying_processor)

# Add the batch processor with our modifying exporter SECOND (exports to LangSmith)
batch_processor = BatchSpanProcessor(modifying_exporter)
tracer_provider.add_span_processor(batch_processor)

trace.set_tracer_provider(tracer_provider)
logger.info("OpenTelemetry configuration complete!")
logger.info("=" * 60)

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

# Add middleware to extract session_id from metadata and set as thread_id in OpenTelemetry
@a2a_app.middleware("http")
async def set_thread_id_middleware(request: Request, call_next):
    """Extract session_id from metadata and set as thread_id in OpenTelemetry spans."""
    tracer = trace.get_tracer(__name__)
    
    thread_id = None
    if request.method == "POST":
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                body = json.loads(body_bytes)
                if "metadata" in body:
                    thread_id = body["metadata"].get("thread_id")
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
        except:
            pass
    
    if thread_id:
        ctx = set_value("thread_id", thread_id)
        token = attach(ctx)
    else:
        token = None
    
    try:
        logger.info(f"Creating span 'google_adk_agent' for {request.method} {request.url.path}")
        with tracer.start_as_current_span("google_adk_agent") as span:
            logger.debug(f"Span created: trace_id={span.get_span_context().trace_id:x}, span_id={span.get_span_context().span_id:x}")
            if thread_id:
                span.set_attribute("langsmith.metadata.thread_id", thread_id)
                logger.info(f"Set thread_id attribute: {thread_id}")
            else:
                logger.warning("No thread_id found in request metadata")
            response = await call_next(request)
            logger.info(f"Request completed, span will be exported")
            return response
    finally:
        if token:
            from opentelemetry.context import detach
            detach(token)
