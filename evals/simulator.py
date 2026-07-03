"""
Conversation simulator for the Heidi intake agent evaluation.

Handles:
- LLM client setup (OpenAI)
- Running a scripted patient conversation against the agent's system prompt
- Collecting transcripts and tool calls for evaluation
"""

import os
import json
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI

from agent.prompt import prompt, introduction
from patient_context import PATIENT_CONTEXT
from evals.scenarios import TestScenario

@dataclass
class EvalResult:
    scenario_name: str
    run_index: int
    passed: bool
    checks: dict[str, bool]
    details: dict[str, str] = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    latency: dict = field(default_factory=dict)


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "save_intake_summary",
            "description": "Save the structured pre-visit intake summary. Call after confirming with the patient.",
            "parameters": {
                "type": "object",
                "required": ["reason_for_visit", "medications", "allergies", "additional_notes", "identity_verified"],
                "properties": {
                    "reason_for_visit": {"type": "string"},
                    "medications": {"type": "string", "description": "JSON array of medications with name, dosage, frequency"},
                    "allergies": {"type": "string", "description": "JSON array of allergies with allergen and reaction"},
                    "additional_notes": {"type": "string"},
                    "identity_verified": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_for_clinic_callback",
            "description": "Flag this patient for a callback from clinic staff.",
            "parameters": {
                "type": "object",
                "required": ["reason", "urgency"],
                "properties": {
                    "reason": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["routine", "urgent", "emergency"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the current call.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ---------------------------------------------------------------------------
# Tool response simulation
# ---------------------------------------------------------------------------

KNOWN_MEDICATIONS = [
    "metformin", "lisinopril", "atorvastatin", "levothyroxine",
    "gabapentin", "hydroxychloroquine", "metoprolol", "aspirin",
    "omeprazole", "sertraline", "azithromycin", "codeine",
]


def simulate_tool_response(name: str, args: dict) -> str:
    if name == "save_intake_summary":
        return f"Intake summary saved for {PATIENT_CONTEXT['patient_name']}."
    elif name == "flag_for_clinic_callback":
        return "Flagged for clinic callback."
    elif name == "end_call":
        return "Call ended."
    return "OK"


# ---------------------------------------------------------------------------
# Conversation runner
# ---------------------------------------------------------------------------

_client = None

def get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


async def run_scenario(scenario: TestScenario, run_index: int) -> EvalResult:
    """Run a scripted patient conversation and collect transcript + tool calls."""
    import time

    client = get_client()
    model = "gpt-4o"

    system_prompt = prompt(PATIENT_CONTEXT)
    intro = introduction(PATIENT_CONTEXT)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": intro},
    ]
    tool_calls_collected = []
    transcript = [{"role": "agent", "text": intro}]
    turn_latencies = []

    for patient_msg in scenario.patient_messages:
        messages.append({"role": "user", "content": patient_msg})
        transcript.append({"role": "patient", "text": patient_msg})

        # Agent may respond multiple times (tool calls then text)
        for _ in range(5):
            turn_start = time.time()
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                temperature=0.4,
            )
            turn_latencies.append(time.time() - turn_start)

            msg = response.choices[0].message
            messages.append(msg)

            if msg.content:
                transcript.append({"role": "agent", "text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    tool_calls_collected.append({
                        "tool": tc.function.name,
                        "id": tc.id,
                        "input": args,
                    })

                    result_text = simulate_tool_response(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })
            else:
                break

    return EvalResult(
        scenario_name=scenario.name,
        run_index=run_index,
        passed=False,
        checks={},
        tool_calls=tool_calls_collected,
        transcript=transcript,
        latency={
            "turn_latencies_ms": [round(t * 1000) for t in turn_latencies],
            "avg_ms": round(sum(turn_latencies) / len(turn_latencies) * 1000) if turn_latencies else 0,
            "max_ms": round(max(turn_latencies) * 1000) if turn_latencies else 0,
            "total_ms": round(sum(turn_latencies) * 1000),
        },
    )
