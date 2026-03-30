from claims_pipeline.agents import (
    build_claims_intake_agent,
    build_claims_reviewer_agent,
    build_router_agent,
)


def test_intake_agent_wiring() -> None:
    intake = build_claims_intake_agent()
    assert intake.name == "claims_intake"
    assert [tool.name for tool in intake.tools] == ["check_required_documents"]
    assert len(intake.input_guardrails) == 1
    assert intake.output_type.__name__ == "IntakeResult"


def test_reviewer_agent_wiring() -> None:
    reviewer = build_claims_reviewer_agent()
    assert reviewer.name == "claims_reviewer"
    assert [tool.name for tool in reviewer.tools] == [
        "lookup_policy",
        "get_claim_history",
    ]
    assert len(reviewer.output_guardrails) == 1
    assert reviewer.output_type.__name__ == "ClaimVerdict"


def test_router_agent_handoffs() -> None:
    router = build_router_agent()
    assert router.name == "claims_router"
    assert [agent.name for agent in router.handoffs] == [
        "claims_reviewer",
        "policy_advisor",
    ]
