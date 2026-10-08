"""Runnable deployment and platform-harness companion for Chapter 10."""

from .adapter import adapt_legacy_report
from .board import board_rows, load_board
from .contracts import ContractEnforcer, ContractHook
from .evidence import emit_deployment_evidence, verify_manifest
from .gate import compare_reports, run_pipeline, scan_secrets, wilson_interval
from .intake import recommend_route
from .register import FileRepository, listing_check, run_listing_demo
from .release import ParkedRunStore, ReleasePointer, bundle_digest, load_bundle
from .switches import KillSwitchMap

__all__ = [
    "ContractEnforcer",
    "ContractHook",
    "FileRepository",
    "KillSwitchMap",
    "ParkedRunStore",
    "ReleasePointer",
    "adapt_legacy_report",
    "board_rows",
    "bundle_digest",
    "compare_reports",
    "emit_deployment_evidence",
    "listing_check",
    "load_board",
    "load_bundle",
    "recommend_route",
    "run_listing_demo",
    "run_pipeline",
    "scan_secrets",
    "verify_manifest",
    "wilson_interval",
]
