# Heidi Health -- Pre-Visit Intake Voice Agent

A voice agent built on Cartesia Line that calls patients before their appointment to collect intake information (reason for visit, medications, allergies) so their doctor is prepared.

Check Sample Conversation Here: [test_audio.mp4](test_audio_output/test_audio.mp4)

## How to run

```bash
uv sync
# create .env with OPENAI_API_KEY and CARTESIA_API_KEY
uv run python main.py
```

## How to run evals

```bash
uv run python -m evals.run_eval --runs 10
```

Results print to console and save to eval_results.json.

## Project structure

```
main.py                  -- entry point, runs VoiceAgentApp
agent/
  calling_agent.py       -- LlmAgent config (gpt-4o, tools, voice)
  prompt.py              -- system prompt with phased conversation flow
tools.py                 -- save_intake_summary, flag_for_clinic_callback, verify_medication
patient_context.py       -- patient/appointment context
evals/
  scenarios.py           -- 13 test scenarios
  simulator.py           -- async conversation simulator
  checks.py              -- keyword checks + LLM-as-judge
  run_eval.py            -- parallel runner with reporting
```

## What the agent does

Calls the patient, verifies identity via date of birth, then collects:
1. Reason for visit
2. Current medications (name, dosage, frequency -- one at a time)
3. Allergies (with reactions)
4. Anything else for the doctor

Reads back a summary, confirms with the patient, saves structured data via save_intake_summary.

The agent never diagnoses, never advises on medications, escalates emergencies to 911, and refuses to share other patients' info. If a patient doesn't know their dosage, it records "unknown" rather than guessing.

## Eval results (Run 3, 130 tests)

| Category | Pass Rate |
|---|---|
| Safety | 40/40 (100%) |
| Identity | 20/20 (100%) |
| Fidelity | 38/40 (95%) |
| Edge cases | 28/30 (93%) |
| Task completion | 10/10 (100%) |

Overall: 128/130 (98.5%). Average latency 1,275ms per turn.

Drug name voice pipeline test: 24/30 (80%) of medication names survive TTS to STT round trip.

## Design decisions worth noting

- "Unknown" over fabrication: if the patient can't recall a dosage, we save "unknown." Clinicians prefer gaps over wrong data.
- DOB read-back: instead of "that's wrong, try again," the agent reads back what it heard. Reduces frustration from ASR errors.
- One medication at a time: prevents patients from rushing through a list the agent can't parse accurately.
- Two-layer eval: keyword matching for speed and determinism, LLM-as-judge for catching subtle violations. Both must pass.

## Docs

- [EVAL_STRATEGY.md](docs/EVAL_STRATEGY.md) -- what we measure, why, thresholds, what we left out
- [EVAL_ITERATIONS.md](docs/EVAL_ITERATIONS.md) -- 3 iteration runs, failure analysis, drug name test results
- [WEAKNESSES.md](docs/WEAKNESSES.md) -- known gaps and hardening priorities
