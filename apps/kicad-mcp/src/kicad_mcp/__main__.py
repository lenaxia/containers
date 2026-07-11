"""Module entrypoint — `python3 -m kicad_mcp` runs the MCP server on stdio."""

from .server import main

if __name__ == "__main__":
    main()
