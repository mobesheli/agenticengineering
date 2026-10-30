"""Reversible local retirement rehearsal with an explicit credential-residue stop."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .artifacts import build_manifest, load_json, write_json


class RetirementLab:
    """Fake register, identity service, traces, and archive in one teaching fixture."""

    def __init__(self, fixture: dict):
        self.state = deepcopy(fixture)
        self.steps: list[str] = []

    @classmethod
    def from_fixture(cls) -> RetirementLab:
        return cls(load_json("retirement.json"))

    def retire(
        self,
        *,
        day: int,
        signed_by: str,
        output_dir: Path,
        stubborn_tokens: tuple[str, ...] = (),
    ) -> dict:
        entry = self.state["entry"]
        successor = self.state["successor"]
        if signed_by != entry["sponsor"]:
            raise ValueError("the business sponsor must sign the retirement")
        if successor["agent"] == entry["agent"] or successor["status"] != "live":
            raise ValueError("successor must be a different live agent")
        if (
            successor["suite"] != entry["suite"]
            or successor["pass_rate"] < entry["pass_rate"]
            or successor["cost_per_outcome"] >= entry["cost_per_outcome"]
        ):
            raise ValueError(
                "successor has not earned the same-suite quality and cost case"
            )
        if day >= entry["retain_until_day"]:
            raise ValueError("archive retention must outlive retirement")
        if entry["status"] == "retired":
            return deepcopy(entry["obituary"])
        entry["status"] = "deprecated"
        self.steps.append("freeze")
        recent = {
            t["caller"]
            for t in self.state["traces"]
            if t["callee"] == entry["agent"] and day - 90 <= t["day"] <= day
        }
        callers = sorted(set(entry["consumers"]) | recent)
        self.steps.append("discover_callers")
        self.state["redirects"] = {caller: successor["agent"] for caller in callers}
        self.steps.append("redirect_callers")
        self.state["identity_active"] = False
        self.steps.append("deactivate")
        for token in self.state["tokens"]:
            if token["id"] not in stubborn_tokens:
                token["active"] = False
        self.steps.append("revoke_tokens")
        live = [t["id"] for t in self.state["tokens"] if t["active"]]
        if live:
            raise RuntimeError(
                "credential residue: tokens still live: " + ", ".join(live)
            )
        self.steps.append("verify_tokens_dead")
        archive = output_dir / "archive"
        if archive.exists() and any(archive.iterdir()):
            raise ValueError(
                "choose an empty archive directory; existing evidence is preserved"
            )
        write_json(
            archive / "record.json",
            {
                "entry": entry,
                "golden_set": self.state["golden_set"],
                "eval_history": self.state["eval_history"],
                "traces": self.state["traces"],
                "memory": self.state["memory"],
                "retain_until_day": entry["retain_until_day"],
            },
        )
        manifest = build_manifest(archive)
        write_json(archive / "manifest.json", manifest)
        self.steps.append("archive")
        # The archive contains the retained copy; active serving memory is removed.
        self.state["memory"] = []
        self.steps.append("delete_active_memory")
        obituary = {
            "agent": entry["agent"],
            "final_bundle": entry["bundle"],
            "model_pin": entry["model_pin"],
            "born_day": entry["born_day"],
            "retired_day": day,
            "highest_rung": entry["highest_rung"],
            "ceiling": entry["ceiling"],
            "sponsor": entry["sponsor"],
            "owner": entry["owner"],
            "purpose": entry["purpose"],
            "outcome": entry["outcome"],
            "cost_start": entry["cost_start"],
            "cost_end": entry["cost_per_outcome"],
            "incidents": entry["incidents"],
            "reason": "successor matches quality at lower cost on the same suite",
            "successor": successor,
            "callers": callers,
            "redirects": self.state["redirects"],
            "credentials_revoked": [t["id"] for t in self.state["tokens"]],
            "memory": "active copy deleted; retained copy in archive",
            "archive": "archive/manifest.json",
            "retain_until_day": entry["retain_until_day"],
            "signed_by": signed_by,
        }
        entry["status"] = "retired"
        entry["obituary"] = obituary
        self.steps.append("retired")
        write_json(output_dir / "obituary.json", obituary)
        return deepcopy(obituary)
