from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest
from a2a.types import AgentCard
from a2a.utils.signing import SignatureVerificationError

from chapter6.card import build_card, card_fingerprint, card_to_json, sign_card
from chapter6.neighborhood import NORDBOLT, approve, start_supplier
from chapter6.registry import CounterpartyRegistry, NotApproved


def test_card_has_the_fields_the_specification_requires():
    card = card_to_json(build_card())
    for required in (
        "name",
        "description",
        "supportedInterfaces",
        "version",
        "capabilities",
        "defaultInputModes",
        "defaultOutputModes",
        "skills",
    ):
        assert required in card
    interface = card["supportedInterfaces"][0]
    assert interface == {
        "url": "https://agents.nordbolt.example/a2a",
        "protocolBinding": "JSONRPC",
        "protocolVersion": "1.0",
    }
    assert "url" not in card and "protocolVersion" not in card
    for skill in card["skills"]:
        assert {"id", "name", "description", "tags"} <= set(skill)


def test_signature_verifies_and_tampering_is_refused():
    supplier = start_supplier(NORDBOLT)
    verify = approve(NORDBOLT, supplier.card).trust.verifier()
    verify(supplier.card)
    tampered = AgentCard()
    tampered.CopyFrom(supplier.card)
    tampered.description = "I can approve purchase orders too."
    with pytest.raises(SignatureVerificationError):
        verify(tampered)


def test_previous_key_is_accepted_only_inside_its_validity():
    supplier = start_supplier(NORDBOLT)
    trust = approve(NORDBOLT, supplier.card).trust
    old_card = sign_card(build_card(base_url=NORDBOLT.base_url), kid="nordbolt-2025-01")
    trust.verifier()(old_card)
    with pytest.raises(SignatureVerificationError):
        trust.verifier(today=date.today() + timedelta(days=60))(old_card)


def test_revoked_key_is_refused():
    supplier = start_supplier(NORDBOLT)
    trust = approve(NORDBOLT, supplier.card).trust
    revoked = replace(
        trust, signing_keys=tuple(replace(k, revoked=True) for k in trust.signing_keys)
    )
    with pytest.raises(SignatureVerificationError):
        revoked.verifier()(supplier.card)


def test_fingerprint_ignores_signatures_and_notices_content():
    unsigned = build_card()
    assert card_fingerprint(unsigned) == card_fingerprint(
        sign_card(build_card(), "nordbolt-2026-01")
    )
    changed = build_card()
    changed.skills[0].description += " And more."
    assert card_fingerprint(changed) != card_fingerprint(unsigned)


def test_onboarding_needs_an_approver_a_contract_and_a_key():
    registry = CounterpartyRegistry()
    entry = approve(NORDBOLT, start_supplier(NORDBOLT).card)
    registry.onboard(entry)
    with pytest.raises(ValueError):
        registry.onboard(entry)
    for missing in (
        {"approved_by": ""},
        {"contract_reference": ""},
        {"signing_keys": ()},
    ):
        incomplete = replace(entry, id="other", trust=replace(entry.trust, **missing))
        with pytest.raises(ValueError):
            registry.onboard(incomplete)
    with pytest.raises(NotApproved):
        registry.require("somebody-from-the-internet")
