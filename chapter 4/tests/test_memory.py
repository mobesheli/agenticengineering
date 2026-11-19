from datetime import UTC, datetime, timedelta

from agents import Agent, Runner
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from chapter4.embedding import local_embed
from chapter4.episodes import (
    Extraction,
    rank_by_relevance_and_recency,
    recall_episodes,
    redact,
    remember,
)
from chapter4.knowledge import search_knowledge
from chapter4.memory import MemoryScope
from chapter4.skills import describe_skills, load_skill
from chapter4.stores import Episode, EpisodeHit
from examples import billing_session
from examples.scripted import tool_outputs
from tests.conftest import user_texts

NOW = datetime.now(UTC)


def episode(
    text: str, days_old: int, importance: int = 5, decays: bool = True
) -> Episode:
    return Episode(
        summary=text,
        importance=importance,
        occurred_at=NOW - timedelta(days=days_old),
        decays=decays,
    )


async def test_session_feeds_the_first_turn_into_the_second(tmp_path):
    seen = []

    def reply(text):
        def step(call):
            seen.append(user_texts(call.input))
            return [assistant_message(text)]

        return ModelStep.respond(step)

    model = ScriptedModel(
        [reply("Sorry about that."), reply("You were double charged in March.")]
    )
    answer = await billing_session.main(model, str(tmp_path / "c.db"))

    assert "March" in answer
    assert seen[0] == ["I was double charged in March."]
    assert seen[1] == [
        "I was double charged in March.",
        "I got cut off. Where were we?",
    ]


async def test_knowledge_search_returns_passages_with_their_source(memory):
    for source, text in [
        ("policy/refunds-eu", "Refunds for European orders take five days."),
        ("policy/shipping", "We ship on weekdays."),
    ]:
        memory.knowledge.add(source, text, await local_embed(text))
    captured = {}

    def answer(call):
        captured.update(tool_outputs(call.input))
        return [assistant_message("Five days.")]

    model = ScriptedModel(
        [
            ModelStep.respond(
                lambda call: [
                    function_call(
                        "search_knowledge",
                        {"query": "refunds for European orders", "top_k": 1},
                        call_id="k",
                    )
                ]
            ),
            ModelStep.respond(answer),
        ]
    )
    agent = Agent(name="support", model=model, tools=[search_knowledge])
    await Runner.run(agent, "How long do EU refunds take?", context=memory)

    assert (
        "policy/refunds-eu" in captured["k"] and "policy/shipping" not in captured["k"]
    )


async def test_remember_extracts_redacts_and_scopes(memory):
    extraction = {
        "episodes": [
            {
                "summary": "Patient MRN 4471982 reported a severe reaction to amoxicillin.",
                "importance": 9,
                "decays": False,
            }
        ]
    }
    import json

    model = ScriptedModel(
        [ModelStep.respond(lambda call: [assistant_message(json.dumps(extraction))])]
    )

    stored = await remember(
        "Clinician: any reactions? Patient: amoxicillin, badly.", memory, model
    )

    assert stored == 1
    row = memory.episodes.rows[0]
    assert (
        "4471982" not in row.episode.summary
        and "[identifier removed]" in row.episode.summary
    )
    assert (row.org_id, row.user_id) == ("st-marys", "patient-alvarez")
    assert abs(row.episode.occurred_at - datetime.now(UTC)) < timedelta(minutes=1)
    assert row.episode.decays is False


def test_the_model_is_never_asked_for_a_date():
    asked_for = Extraction.model_json_schema()["$defs"]["Observation"]["properties"]

    assert set(asked_for) == {"summary", "importance", "decays"}


async def test_another_tenant_cannot_see_these_episodes(memory):
    ep = episode("Simvastatin stopped by Dr. Reed.", 10)
    await memory.episodes.append(memory.scope, await local_embed(ep.summary), ep)
    vector = await local_embed("simvastatin")

    other_org = MemoryScope(
        org_id="other-hospital", user_id="patient-alvarez", agent_id="med-rec"
    )
    other_user = MemoryScope(
        org_id="st-marys", user_id="patient-brown", agent_id="med-rec"
    )

    assert len(await memory.episodes.search(memory.scope, vector, 5)) == 1
    assert await memory.episodes.search(other_org, vector, 5) == []
    assert await memory.episodes.search(other_user, vector, 5) == []


def test_recent_beats_old_but_an_allergy_never_fades():
    old = EpisodeHit(episode("Asked about opening hours.", 700), 0.80)
    recent = EpisodeHit(episode("Asked to move the appointment.", 3), 0.75)
    allergy = EpisodeHit(
        episode("Severe reaction to amoxicillin.", 700, importance=10, decays=False),
        0.70,
    )

    ranked = rank_by_relevance_and_recency([old, recent, allergy])

    assert [e.summary for e in ranked] == [
        "Severe reaction to amoxicillin.",
        "Asked to move the appointment.",
        "Asked about opening hours.",
    ]


async def test_recall_tool_reads_scope_from_the_run_context(memory):
    ep = episode("Duplicate statin resolved. Simvastatin stopped.", 90, importance=8)
    await memory.episodes.append(memory.scope, await local_embed(ep.summary), ep)
    captured = {}

    def answer(call):
        captured.update(tool_outputs(call.input))
        return [assistant_message("Noted.")]

    model = ScriptedModel(
        [
            ModelStep.respond(
                lambda call: [
                    function_call(
                        "recall_episodes",
                        {"situation": "statin duplicate"},
                        call_id="r",
                    )
                ]
            ),
            ModelStep.respond(answer),
        ]
    )
    agent = Agent(name="clinic", model=model, tools=[recall_episodes])
    await Runner.run(agent, "Reconcile.", context=memory)

    assert "Simvastatin stopped" in captured["r"]
    schema = recall_episodes.params_json_schema["properties"]
    assert set(schema) == {"situation", "top_k"}


async def test_erasure_removes_from_retrieval_and_respects_legal_hold(memory):
    a, b = (
        episode("Prefers morning appointments.", 5),
        episode("Statin decision recorded.", 5),
    )
    await memory.episodes.append(memory.scope, await local_embed(a.summary), a)
    await memory.episodes.append(
        memory.scope, await local_embed(b.summary), b, legal_hold=True
    )

    erased = memory.episodes.erase("st-marys", "patient-alvarez")
    left = await memory.episodes.search(
        memory.scope, await local_embed("appointments statin"), 5
    )

    assert erased == 1
    assert [hit.episode.summary for hit in left] == ["Statin decision recorded."]
    assert len(memory.episodes.rows) == 2


def test_redaction_leaves_ordinary_numbers_alone():
    assert (
        redact("Dose raised to 40 mg after 180 days.")
        == "Dose raised to 40 mg after 180 days."
    )
    assert redact("SSN 123-45-6789 on file.") == "[identifier removed] on file."
    assert (
        redact("Patient MRN 4471982 reported a reaction.")
        == "Patient [identifier removed] reported a reaction."
    )


def test_skills_cost_one_line_until_loaded():
    catalog = describe_skills()
    body = load_skill("medication-reconciliation")

    assert list(catalog) == ["medication-reconciliation"]
    assert len(catalog["medication-reconciliation"]) < 160
    assert (
        body.startswith("Steps:")
        and "Do not finalize" in body
        and "description:" not in body
    )
