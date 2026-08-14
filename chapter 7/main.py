"""Convenience entry point for the Chapter 7 evaluation suite."""

from __future__ import annotations

import asyncio

from chapter7.__main__ import main

if __name__ == "__main__":
    asyncio.run(main())
