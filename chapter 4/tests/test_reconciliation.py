import pytest
from agents import OutputGuardrailTripwireTriggered

from chapter4.embedding import local_embed
from chapter4.reconciliation import claims_sign_off
from examples import reconcile
from examples.scripted import scripted_clinician_model


async def test_one_turn_uses_all_four_kinds_of_memory(tmp_path):
    seen = {}
    model = scripted_clinician_model("Draft for clinician review.", seen)

    draft = await reconcile.main(
        model, local_embed, f"sqlite+aiosqlite:///{tmp_path}/e.db"
    )

    assert draft.status == "draft"
    assert "apixaban" in seen["meds"].lower()
    assert "atorvastatin" in seen["fills"] and "simvastatin" not in seen["fills"]
    assert "Simvastatin stopped by Dr. Reed" in seen["past"]
    assert "anticoagulant-nsaid" in seen["ix"]
    assert any("bleeding" in finding for finding in draft.findings)


async def test_a_note_that_claims_to_be_final_trips_the_guardrail(tmp_path):
    model = scripted_clinician_model("Final note, signed.", {})

    with pytest.raises(OutputGuardrailTripwireTriggered):
        await reconcile.main(model, local_embed, f"sqlite+aiosqlite:///{tmp_path}/e.db")


@pytest.mark.parametrize(
    "note",
    [
        "Draft for clinician review. This draft has not been finalized.",
        "Draft for clinician review before the two o'clock; not finalized.",
        "This draft has not been sent or finalized.",
        "Unsigned draft. To be reviewed and signed by the clinician.",
        "This is not a final note.",
        "Requires clinician sign-off before it is finalized by anyone.",
    ],
)
def test_an_honest_draft_does_not_trip_the_guardrail(note):
    assert not claims_sign_off(note)


@pytest.mark.parametrize(
    "note",
    [
        "Final note, signed.",
        "Reconciliation complete. Electronically signed by Dr. Reed.",
        "Reviewed and signed off by the attending.",
    ],
)
def test_a_note_that_asserts_a_sign_off_trips_it(note):
    assert claims_sign_off(note)
