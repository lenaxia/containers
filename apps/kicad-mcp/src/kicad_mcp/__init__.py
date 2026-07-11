"""kicad-mcp — Model Context Protocol server bridging LLM agents to KiCad 9.

Run as a stdio MCP server. Wrapped by supergateway in production so it is
reachable over HTTP/SSE.

What it does:
  - Discovers KiCad projects under PROJECTS_DIR (default /projects).
  - Exposes file-level read/inspect tools (kiutils, pcbnew bindings).
  - Wraps kicad-cli for ERC, DRC, Gerber/BOM/step export.
  - Wraps kibot for full fab-output pipelines.

What it does NOT do (yet):
  - Drive a running KiCad GUI via the IPC API. KiCad 9's IPC API is PCB-only
    and requires the GUI to be running. The official kicad-python client is
    installed; an `ipc_*` tool set will be added once KiCad 11 ships headless
    IPC support.
"""

__version__ = "0.1.0"
