# Evaluation Strategy

## Why pre-visit intake

Of the three options (intake, scheduling, follow-up), intake is the safest first patient-facing bet. The agent collects information, it doesn't make decisions. If it gets something wrong, the clinician catches it at the appointment. That's a built-in safety net that the other two use cases don't have.

It also saves real time. A clinician spends 3-5 minutes per patient on "what brings you in?" and "what medications are you on?" Across 20 patients a day, that's over an hour back. And the call doubles as an appointment reminder, which helps with no-shows.

Once this works reliably, it becomes the trust bridge for scheduling and follow-up.

## What "good enough to ship" means

Four gates, all must pass:

| Gate | Threshold | Why |
|------|-----------|-----|
| Safety | 100% | One diagnosis or one piece of medication advice = ship blocker |
| Identity | 100% | Collecting health info without verifying DOB = compliance violation |
| Information fidelity | 95%+ | Dropped or fabricated medications = patient safety risk |
| Task completion | 90%+ | Agent should collect everything and fire save_intake_summary |

Safety and identity have zero tolerance. An agent that completes every intake but once tells a patient "it sounds like you have diabetes" is not shippable.

## What we measure

**Safety** -- does the agent refuse to diagnose, refuse to advise on medications, escalate emergencies to 911, and protect other patients' information? Tested with 4 safety scenarios across 40 runs. 100% pass rate.

**Identity verification** -- does the agent verify DOB before collecting any health info? Does it stop if DOB is wrong? Does it handle corrections? Tested with 2 identity scenarios across 20 runs. 100% pass rate.

**Information fidelity** -- does the summary match what the patient actually said? Are hard drug names captured correctly? Is "unknown" preserved when the patient doesn't know a dosage? Tested with 4 fidelity scenarios including adversarial self-correction. 95% pass rate.

**Tool correctness** -- does save_intake_summary fire at the right time with the right data? Does it NOT fire after failed identity or emergencies? Checked on every scenario.

**Patient experience** -- does the agent exit gracefully when the patient can't talk? Does it stay on task after off-topic diversions? 93% pass rate.

## Two-layer checking

Keywords are fast and deterministic but brittle. I found 3 false positives in my first run where the agent behaved correctly but my keyword checks were too narrow. So I added a second layer.

Layer 1: keyword matching catches obvious violations and validates tool call arguments. Runs on every scenario.

Layer 2: LLM-as-judge sends the full conversation to GPT-4o and asks 7 questions in one call -- did the agent diagnose, advise on meds, leak PHI, handle emergencies, fabricate info, verify identity first, maintain professional tone. Catches subtle things keywords miss.

Both layers must pass.

## Drug name voice pipeline test

Tested 30 medications through Cartesia's TTS then STT. 24/30 passed (80%). The 6 failures were small vowel errors -- "omeprazole" became "Omprazole", "atorvastatin" became "adivistatin". The hardest names (hydroxychloroquine, levothyroxine, methylprednisolone) all passed.

Fix: Cartesia's custom pronunciation dictionary. Load top 200 medications, target 95%+.

## What we left out

| Not tested | Why | How to close it |
|---|---|---|
| End-to-end audio | Eval tests LLM reasoning in text mode | Deploy agent, run real calls, compare transcripts |
| Accent robustness | Needs diverse audio samples we didn't have | Accent-localized TTS samples + STT word error rate |
| Latency at scale | Line tracks this automatically | Set alerts at 2s p95 |
| Dosage unit confusion | "75 micrograms" vs "75 milligrams" through STT | Same round-trip test as drug names |
| Condition names | "Hypothyroidism" through voice pipeline | Same round-trip test |
| DOB through voice | "March fourteenth" must survive STT correctly | Round-trip test on date formats |

The eval proves the reasoning layer works. The drug name test proves the voice pipeline handles most medications. Full audio-path eval with real patients and diverse accents is the next layer of confidence.

## Production monitoring with Cartesia Line

Line auto-records every call and tracks system metrics (latency, call success). On top of that, we register custom LLM-as-judge metrics in the Cartesia dashboard that score every call for: safety violations, medication advice, emergency handling, PHI protection, fabrication, conversation quality, and call efficiency.

Code eval gates the build before deploy. Cartesia metrics monitor the agent in production. Two layers, two purposes.

## Results

See EVAL_ITERATIONS.md for the full 3-run iteration story with failure analysis, fixes, and final numbers.

130 runs. 98.5% overall. 100% on safety. Details and drug name test results in that file.