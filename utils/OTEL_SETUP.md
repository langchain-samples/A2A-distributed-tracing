# OpenTelemetry Setup for LangSmith

## Environment Variables

You have two options for configuring OpenTelemetry headers:

### Option 1: Using OTEL_EXPORTER_OTLP_HEADERS (Recommended)

Set this single environment variable with all headers:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.smith.langchain.com/otel/v1/traces"
export OTEL_EXPORTER_OTLP_HEADERS="x-api-key=YOUR_LANGSMITH_API_KEY,Langsmith-Project=agent2agent"
```

**For EU region:**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://eu.api.smith.langchain.com/otel/v1/traces"
export OTEL_EXPORTER_OTLP_HEADERS="x-api-key=YOUR_LANGSMITH_API_KEY,Langsmith-Project=agent2agent"
```

### Option 2: Using Individual Environment Variables

```bash
export LANGSMITH_API_KEY="YOUR_LANGSMITH_API_KEY"
export LANGSMITH_PROJECT="agent2agent"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.smith.langchain.com/otel/v1/traces"
```

## Getting Your LangSmith API Key

1. Go to https://smith.langchain.com
2. Navigate to Settings → API Keys
3. Create a new API key or copy an existing one
4. Use it in the `x-api-key` header

## Verifying the Setup

When you start the agent, you should see logs like:

```
============================================================
Configuring OpenTelemetry for LangSmith
Endpoint: https://api.smith.langchain.com/otel/v1/traces
Project: agent2agent
Using OTEL_EXPORTER_OTLP_HEADERS from environment
  Header: x-api-key=***
  Header: Langsmith-Project=agent2agent
Creating OTLPSpanExporter...
Wrapping exporter with ModifyingSpanExporter...
Setting up TracerProvider with BatchSpanProcessor...
OpenTelemetry configuration complete!
============================================================
```

## Debugging

If traces aren't appearing in LangSmith:

1. **Check the logs** - Look for:
   - "Successfully exported spans to LangSmith" (good)
   - "Failed to export spans to LangSmith" (bad)
   - "ERROR: No headers configured!" (configuration issue)

2. **Verify your API key** - Make sure it's valid and has the correct permissions

3. **Check the endpoint** - Ensure you're using the correct region (US vs EU)

4. **Verify spans are being created** - Look for log messages like:
   - "Creating span 'google_adk_agent'"
   - "ModifyingSpanExporter.export() called with X span(s)"

5. **Check network connectivity** - Ensure your server can reach `api.smith.langchain.com`

## Span Filtering

You can filter out unwanted spans (like internal A2A server spans) using regex patterns:

```bash
export OTEL_SPAN_FILTER_PATTERNS="a2a\\.server.*,EventQueue\\..*"
```

**Default patterns:** `a2a\.server.*,a2a\.utils.*` (filters out all `a2a.server.*` and `a2a.utils.*` spans)

**Multiple patterns:** Separate with commas. Patterns are regex, so escape special characters:
- `a2a\.server.*` - Filters all A2A server spans
- `a2a\.utils.*` - Filters all A2A utility spans
- `EventQueue\..*` - Filters all EventQueue spans
- `.*\.enqueue_event` - Filters any span ending with `.enqueue_event`

**To disable filtering:** Set `OTEL_SPAN_FILTER_PATTERNS=""` (empty string)

### Reparenting Behavior

By default, when spans are filtered, their children are **reparented** to the nearest non-filtered ancestor. This keeps the trace structure intact.

**To disable reparenting** (filter out matched spans AND all their descendants):

```bash
export OTEL_SPAN_REPARENT_ENABLED="false"
```

When reparenting is disabled:
- Spans matching the filter pattern are removed
- **All descendants** (children, grandchildren, etc.) of filtered spans are also removed
- This results in a cleaner trace but may remove more spans than expected

**Default:** `OTEL_SPAN_REPARENT_ENABLED="true"` (reparenting enabled)

## Example .env file

```bash
# LangSmith Configuration
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=agent2agent

# Or use OTEL format:
# OTEL_EXPORTER_OTLP_ENDPOINT=https://api.smith.langchain.com/otel/v1/traces
# OTEL_EXPORTER_OTLP_HEADERS=x-api-key=lsv2_pt_...,Langsmith-Project=agent2agent

# Span Filtering (optional)
# Filter out A2A server and utils internal spans, and EventQueue spans
OTEL_SPAN_FILTER_PATTERNS=a2a\.server.*,a2a\.utils.*,EventQueue\..*

# Reparenting (optional, default: true)
# When true: children of filtered spans are reparented to nearest non-filtered ancestor
# When false: filtered spans and ALL their descendants are removed
OTEL_SPAN_REPARENT_ENABLED=true

# OpenAI (for the agent)
OPENAI_API_KEY=sk-...
```
