"""Minimal stateless container entry point for the Chapter 10 template."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml


def runtime_descriptor() -> dict[str, object]:
    bundle = yaml.safe_load(Path("bundle.yaml").read_text(encoding="utf-8"))
    return {
        "status": "ready",
        "bundle": bundle["bundle"],
        "model": os.getenv("MODEL_ID", bundle["model"]["primary"]["id"]),
        "gateway": os.getenv("MODEL_GATEWAY", "not-configured"),
        "identity": os.getenv("AGENT_IDENTITY", "not-configured"),
        "holds_session_state": False,
        "secret_source": "workload-identity",
    }


def main() -> None:
    print(json.dumps(runtime_descriptor(), indent=2))


if __name__ == "__main__":
    main()
