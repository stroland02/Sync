"""Watching somebody else's MCP server as a vendor.

Not `sync.mcp`, which is Sync exposing its own graph as tools to an agent. This is the
opposite direction: a server out there advertises tools, and a change in what it advertises
breaks the callers that were written against them.
"""
