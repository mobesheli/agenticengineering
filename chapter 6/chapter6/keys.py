"""Demo signing keys.

The key pairs in ``demo_keys/`` are deliberately public teaching material so
that a signature can be produced and verified on a laptop. A real card-signing
key lives in a key management service, and only its public half is ever shared.
"""

from __future__ import annotations

from pathlib import Path

KEY_DIR = Path(__file__).resolve().parents[1] / "demo_keys"


def private_pem(kid: str) -> str:
    return (KEY_DIR / f"{kid}.private.pem").read_text()


def public_pem(kid: str) -> str:
    return (KEY_DIR / f"{kid}.public.pem").read_text()
