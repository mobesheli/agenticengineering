"""A small read-only MCP server standing in for a hospital FHIR endpoint.

It exposes two read tools and no write tool. The agent cannot finalize a note
through this server because the server offers no way to do it.

    python -m chapter4.fhir_server
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

RECORDS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "alvarez.json").read_text()
)
server = MCPServer("fhir-read-only")


@server.tool()
def get_active_medications(patient_ref: str) -> list[dict]:
    """Return the MedicationRequest entries currently active for a patient."""
    return RECORDS[patient_ref]["active_medications"]


@server.tool()
def get_pharmacy_fills(patient_ref: str, days: int = 180) -> list[dict]:
    """Return pharmacy dispensing records for a patient over the last N days."""
    return [fill for fill in RECORDS[patient_ref]["fills"] if fill["days_ago"] <= days]


if __name__ == "__main__":
    server.run("stdio")
