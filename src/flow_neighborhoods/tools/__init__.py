"""Tool logic shared by the MCP server and any other front end (one module per tool).

Each module exposes a plain function that takes a Recommender plus the tool's
arguments and returns a JSON-safe dict. mcp_server.py registers them; keep MCP
imports out of these modules so they stay testable without an MCP client.
"""
