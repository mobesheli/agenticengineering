"""Run the chapter's local exercises and export one verifiable review pack."""

from __future__ import annotations

from pathlib import Path

from .artifacts import build_manifest, load_json, verify_manifest, write_json
from .board import load_register, replay_year, write_board
from .controls import drill_report, improvement_gate
from .drift import fallback_drill
from .fleet import contract_gaps, reconcile
from .memory import MemoryStore, hygiene_pass, offline_merge
from .retirement import RetirementLab


async def emit_evidence(
    output_dir: Path, *, day: int = 365, merge=offline_merge
) -> dict:
    if not 0 <= day <= 365:
        raise ValueError("day must be between 0 and 365")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            "choose an empty output directory to preserve existing evidence"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = replay_year()
    write_json(output_dir / "board-state.json", frames[day])
    write_json(output_dir / "year-replay.json", frames)
    write_board(output_dir / "board.html", frames)
    memory = MemoryStore.from_fixture()
    hygiene = await hygiene_pass(
        memory,
        load_json("asset-register.json"),
        load_json("memory-probes.json"),
        day=180,
        merge=merge,
    )
    write_json(output_dir / "memory-hygiene.json", hygiene)
    write_json(
        output_dir / "memory-lineage.json",
        {
            "quarantined": memory.quarantine("contractor-email"),
            "erasure": memory.erase("employee-event"),
        },
    )
    write_json(
        output_dir / "fleet-reconciliation.json",
        reconcile(load_register(), load_json("identities.json"), day=240),
    )
    contract = load_json("parts-contract.json")
    write_json(
        output_dir / "consumer-contracts.json",
        {
            "compatible": contract_gaps(
                contract,
                {
                    "part_id": "bearing-17",
                    "lead_time_days": 3,
                    "available_quantity": 20,
                },
                call_version=3,
                day=261,
            ),
            "breaking": contract_gaps(
                contract,
                {"part_id": "bearing-17", "eta": "soon"},
                call_version=3,
                day=261,
            ),
        },
    )
    write_json(
        output_dir / "fallback-drill.json",
        fallback_drill(
            "frontier-v2", load_json("fallback.json"), "maintenance-golden@8"
        ),
    )
    write_json(
        output_dir / "improvement-gates.json",
        [improvement_gate(**p) for p in load_json("improvements.json")],
    )
    write_json(
        output_dir / "two-clock-drill.json",
        {
            "first": drill_report(
                damage_seconds=4, page_seconds=3 * 3600 + 600, soft_delete=True
            ),
            "repaired": drill_report(
                damage_seconds=4, page_seconds=360, soft_delete=True
            ),
        },
    )
    lab = RetirementLab.from_fixture()
    residue = ""
    try:
        lab.retire(
            day=340,
            signed_by="Casey Patel",
            output_dir=output_dir / "retirement",
            stubborn_tokens=("token-b",),
        )
    except RuntimeError as exc:
        residue = str(exc)
    lab.retire(day=340, signed_by="Casey Patel", output_dir=output_dir / "retirement")
    write_json(
        output_dir / "retirement-rehearsal.json",
        {
            "first_attempt": residue,
            "steps": lab.steps,
            "final_status": lab.state["entry"]["status"],
        },
    )
    write_json(output_dir / "manifest.json", build_manifest(output_dir))
    return {
        "day": day,
        "rung": frames[day]["entry"]["rung"],
        "ceiling": frames[day]["entry"]["ceiling"],
        "replay_days": len(frames),
        "hygiene_rolled_back": hygiene["rolled_back"],
        "retirement": lab.state["entry"]["status"],
        "manifest_verified": verify_manifest(output_dir),
    }
