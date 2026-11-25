# Verification record

Checked on 25 November 2026 with Python 3.13, openai-agents 0.24.0, openai 3.55.0,
pydantic 2.14.3.

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 51 passed |
| `ruff check .` and `ruff format --check .` | clean, line length 81 |
| Every example against its file in `outputs/` | identical |
| `python scripts/build_notebook.py` | 22 cells, 0 errors |
| `python -m examples.live_check` against a live model, three times | 4 of 4 each time |

## SDK and API interfaces this code relies on

- `agents.Agent(output_type=...)` with a pydantic model. The SDK builds a strict
  JSON schema from it, and a strict schema does not accept a free-form
  dictionary, which is why `Merged.claims` is a list of name and value pairs.
- `agents.Runner.run(...)` and `.final_output`.
- `agents.tracing.TracingProcessor`, and `ResponseSpanData.response`, the
  provider's response object on the span the SDK writes for a Responses API call.
- `openai.types.responses.Response`: `model`, `reasoning.effort`,
  `text.verbosity`, `service_tier`, `truncation`, `temperature`, `top_p`,
  `parallel_tool_calls`, `max_output_tokens`.
- `agents.testing.ScriptedModel` and `ModelStep`, for the scripted replies.

## The live run

`examples/live_check.py` was run on 25 November 2026 with a temporary key, against
the primary model named in `data/bundle.yaml`. It passed four checks on each of
three runs:

- The consolidator returned a merge that the deterministic checks accept.
- The provider's response reported the effective configuration, including
  settings the request never set (output verbosity, sampling, service tier).
- That configuration matched `observed_at_approval` in the bundle.
- A setting changed on purpose (verbosity set to high) was caught as a
  difference.

The first live run failed, and it found two faults the scripted runs had not:

1. The live model renamed the claim `service_days` to "service interval", so the
   check rejected a correct merge. The consolidator is now shown each memory's
   claims and told to keep their names and values exactly, and a test covers it.
2. The provider reports the model name exactly as it was sent, with no dated
   version. An earlier version of the data and the chapter assumed a dated name
   would reveal a silent change. The watch now relies on the settings the
   response reports, which the live run confirmed it does report.

## What is illustrative

Every number in `data/` is synthetic: the bands, the readings, the evidence, the
memories, the fleet, the drills, and the year. The change of a default on day two
is invented to show the mechanism. Change any of them and the examples follow.
