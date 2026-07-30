"""opengist-mcp — MCP server bridging LLM agents to an Opengist instance.

Run as a stdio MCP server. Wrapped by supergateway in production so it is
reachable over HTTP/SSE.

Auth modes:
  - Preloaded: OPENGIST_TOKEN env var at startup
  - Per-call: optional ``token`` parameter on each tool
"""

__version__ = "0.1.0"
