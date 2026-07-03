"""
Drug Name Round-Trip Test
=========================

Tests whether medication names survive the Cartesia voice pipeline:
  Text → Sonic TTS → Audio → Ink STT → Text → Compare

This answers the CTO's question: "Can I trust that the agent correctly
hears and speaks drug names?"

Usage:
    CARTESIA_API_KEY=your-key python drug_name_roundtrip.py
"""

#
import os
import json
import asyncio
from datetime import datetime
from cartesia import Cartesia

# ---------------------------------------------------------------------------
# Drug names to test (common medications from clinical intake)
# ---------------------------------------------------------------------------

DRUG_NAMES = [
    # Easy (common, short)
    "aspirin",
    "ibuprofen",
    "metformin",
    "insulin",
    "amoxicillin",
    "prednisone",
    "omeprazole",
    "losartan",

    # Medium (longer, less common)
    "lisinopril",
    "atorvastatin",
    "metoprolol",
    "amlodipine",
    "sertraline",
    "gabapentin",
    "acetaminophen",
    "clopidogrel",
    "pantoprazole",
    "montelukast",
    "azithromycin",
    "albuterol",

    # Hard (long, complex, easy to mangle)
    "hydroxychloroquine",
    "levothyroxine",
    "esomeprazole",
    "rosuvastatin",
    "dexamethasone",
    "fluticasone",
    "methylprednisolone",
    "ciprofloxacin",
    "benzonatate",
    "cyclobenzaprine",
]


def normalize(text: str) -> str:
    """Normalize text for comparison — lowercase, strip punctuation/whitespace."""
    return "".join(c for c in text.lower() if c.isalnum())


def check_match(original: str, transcribed: str) -> dict:
    """Compare original drug name against STT transcription."""
    orig_norm = normalize(original)
    trans_norm = normalize(transcribed)

    exact_match = orig_norm == trans_norm
    # Also check if the drug name appears anywhere in the transcription
    # (STT might add filler like "The medication is hydroxychloroquine")
    contained = orig_norm in trans_norm

    return {
        "original": original,
        "transcribed": transcribed.strip(),
        "exact_match": exact_match,
        "contained_match": contained,
        "passed": exact_match or contained,
    }


async def test_drug_name(client: Cartesia, drug_name: str, voice_id: str) -> dict:
    """Run one drug name through TTS → STT round trip."""

    import httpx

    # Wrap the drug name in a natural sentence for more realistic TTS
    transcript = f"The patient is currently taking {drug_name}."

    try:
        # Step 1: Text → Speech (Sonic TTS)
        tts_response = client.tts.generate(
            model_id="sonic-3.5",
            transcript=transcript,
            voice={"mode": "id", "id": voice_id},
            output_format={
                "container": "wav",
                "encoding": "pcm_f32le",
                "sample_rate": 16000,
            },
        )

        # Save audio temporarily
        temp_path = f"/tmp/drug_test_{normalize(drug_name)}.wav"
        tts_response.write_to_file(temp_path)

        # Step 2: Speech → Text (Ink STT via batch HTTP API)
        api_key = os.getenv("CARTESIA_API_KEY")
        async with httpx.AsyncClient() as http_client:
            with open(temp_path, "rb") as audio_file:
                response = await http_client.post(
                    "https://api.cartesia.ai/stt",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Cartesia-Version": "2025-04-16",
                    },
                    files={"file": ("audio.wav", audio_file, "audio/wav")},
                    data={"model": "ink-whisper", "language": "en"},
                    timeout=30.0,
                )
                response.raise_for_status()
                stt_result = response.json()

        transcribed = stt_result.get("text", "")

        # Step 3: Compare
        result = check_match(drug_name, transcribed)
        result["tts_input"] = transcript
        result["error"] = None

        # Cleanup
        os.remove(temp_path)
        return result

    except Exception as e:
        return {
            "original": drug_name,
            "transcribed": "",
            "exact_match": False,
            "contained_match": False,
            "passed": False,
            "error": str(e),
        }


async def run_all():
    api_key = os.getenv("CARTESIA_API_KEY")
    if not api_key:
        print("ERROR: Set CARTESIA_API_KEY environment variable")
        return

    client = Cartesia(api_key=api_key)

    # Use a neutral, clear voice — pick one from Cartesia's library
    # You can find voice IDs at play.cartesia.ai
    voice_id = os.getenv("CARTESIA_VOICE_ID", "e07c00bc-4134-4eae-9ea4-1a55fb45746b")

    print("=" * 60)
    print("Drug Name Round-Trip Test")
    print(f"Testing {len(DRUG_NAMES)} medication names through TTS → STT")
    print("=" * 60)

    results = []
    for i, drug in enumerate(DRUG_NAMES):
        print(f"  [{i+1}/{len(DRUG_NAMES)}] {drug}...", end=" ", flush=True)
        result = await test_drug_name(client, drug, voice_id)

        if result["error"]:
            print(f"ERROR: {result['error']}")
        elif result["passed"]:
            print(f"PASS — heard: '{result['transcribed']}'")
        else:
            print(f"FAIL — heard: '{result['transcribed']}'")

        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"] and not r["error"])
    errors = sum(1 for r in results if r["error"])

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Passed:  {passed}/{len(DRUG_NAMES)} ({passed/len(DRUG_NAMES)*100:.0f}%)")
    print(f"  Failed:  {failed}/{len(DRUG_NAMES)}")
    print(f"  Errors:  {errors}/{len(DRUG_NAMES)}")

    if failed > 0:
        print(f"\nFailed drug names:")
        for r in results:
            if not r["passed"] and not r["error"]:
                print(f"  ✗ {r['original']} → heard as '{r['transcribed']}'")

    # Difficulty breakdown
    easy = results[:8]
    medium = results[8:20]
    hard = results[20:]

    print(f"\nBy difficulty:")
    for label, group in [("Easy", easy), ("Medium", medium), ("Hard", hard)]:
        p = sum(1 for r in group if r["passed"])
        print(f"  {label}: {p}/{len(group)} ({p/len(group)*100:.0f}%)")

    # Save results
    output = {
        "test_date": datetime.now().isoformat(),
        "voice_id": voice_id,
        "total_drugs": len(DRUG_NAMES),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": f"{passed/len(DRUG_NAMES)*100:.1f}%",
        "results": results,
    }

    with open("drug_roundtrip_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results → drug_roundtrip_results.json")


if __name__ == "__main__":
    asyncio.run(run_all())