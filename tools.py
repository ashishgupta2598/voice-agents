
from typing import Annotated
from line.llm_agent import  loopback_tool, ToolEnv

from patient_context import PATIENT_CONTEXT
from datetime import datetime
from difflib import get_close_matches
import json

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEDICATION_REFERENCE = {
    "metformin": {"class": "antidiabetic", "common_dosages": ["500mg", "850mg", "1000mg"]},
    "lisinopril": {"class": "ACE inhibitor", "common_dosages": ["5mg", "10mg", "20mg", "40mg"]},
    "atorvastatin": {"class": "statin", "common_dosages": ["10mg", "20mg", "40mg", "80mg"]},
    "omeprazole": {"class": "proton pump inhibitor", "common_dosages": ["20mg", "40mg"]},
    "amlodipine": {"class": "calcium channel blocker", "common_dosages": ["2.5mg", "5mg", "10mg"]},
    "metoprolol": {"class": "beta blocker", "common_dosages": ["25mg", "50mg", "100mg", "200mg"]},
    "levothyroxine": {"class": "thyroid hormone", "common_dosages": ["25mcg", "50mcg", "75mcg", "88mcg", "100mcg"]},
    "albuterol": {"class": "bronchodilator", "common_dosages": ["90mcg/puff"]},
    "sertraline": {"class": "SSRI antidepressant", "common_dosages": ["25mg", "50mg", "100mg"]},
    "gabapentin": {"class": "anticonvulsant", "common_dosages": ["100mg", "300mg", "600mg", "800mg"]},
    "hydroxychloroquine": {"class": "antimalarial/immunomodulator", "common_dosages": ["200mg", "400mg"]},
    "azithromycin": {"class": "antibiotic", "common_dosages": ["250mg", "500mg"]},
    "amoxicillin": {"class": "antibiotic", "common_dosages": ["250mg", "500mg", "875mg"]},
    "ibuprofen": {"class": "NSAID", "common_dosages": ["200mg", "400mg", "600mg", "800mg"]},
    "acetaminophen": {"class": "analgesic", "common_dosages": ["325mg", "500mg", "650mg"]},
    "prednisone": {"class": "corticosteroid", "common_dosages": ["5mg", "10mg", "20mg", "50mg"]},
    "losartan": {"class": "ARB", "common_dosages": ["25mg", "50mg", "100mg"]},
    "montelukast": {"class": "leukotriene inhibitor", "common_dosages": ["4mg", "5mg", "10mg"]},
    "pantoprazole": {"class": "proton pump inhibitor", "common_dosages": ["20mg", "40mg"]},
    "clopidogrel": {"class": "antiplatelet", "common_dosages": ["75mg"]},
}


@loopback_tool
async def verify_medication(
    ctx: ToolEnv,
    medication_name: Annotated[str, "Medication name the patient stated. Use only to verify spelling/recognition, not to suggest medications."],
) -> str:
    """Verify whether a patient-stated medication name is recognized."""

    normalized = medication_name.strip().lower()
    if normalized in MEDICATION_REFERENCE:
        entry = MEDICATION_REFERENCE[normalized]
        dosages = ", ".join(entry["common_dosages"])
        return (
            f"Recognized medication: {normalized}. Class: {entry['class']}. "
            f"Common dosages include: {dosages}. Do not suggest this medication to the patient; "
            "only use this to confirm the medication name they stated."
        )

    close_matches = get_close_matches(normalized, MEDICATION_REFERENCE.keys(), n=3, cutoff=0.72)
    if close_matches:
        return (
            f"Medication '{medication_name}' was not found exactly. Close matches: "
            f"{', '.join(close_matches)}. Ask the patient to spell or clarify the medication name."
        )

    return (
        f"Medication '{medication_name}' was not found. Ask the patient to spell or clarify the "
        "medication name. Do not guess or suggest medications."
    )

@loopback_tool
async def save_intake_summary(
    ctx: ToolEnv,
    reason_for_visit: Annotated[str, "The patient's stated reason for visiting the doctor"],
    medications: Annotated[str, "JSON array of medications. Each item must have 'name', 'dosage' (use 'unknown' if patient didn't know), and 'frequency' (use 'unknown' if not stated). Example: [{\"name\": \"metformin\", \"dosage\": \"500mg\", \"frequency\": \"twice daily\"}, {\"name\": \"gabapentin\", \"dosage\": \"unknown\", \"frequency\": \"unknown\"}]"],
    allergies: Annotated[str, "JSON array of allergies. Each item must have 'allergen' and 'reaction' (use 'unknown' if reaction not stated). Example: [{\"allergen\": \"penicillin\", \"reaction\": \"rash\"}]. Use '[]' if no known allergies."],
    additional_notes: Annotated[str, "Any additional information the patient shared, or empty string if none"],
    identity_verified: Annotated[bool, "Whether the patient's identity was successfully verified via date of birth"],
) -> str:
    """Save the structured pre-visit intake summary to the clinic's system. Call this after confirming the summary with the patient."""

    summary = {
        "patient_name": PATIENT_CONTEXT["patient_name"],
        "date_of_birth": PATIENT_CONTEXT["date_of_birth"],
        "appointment_date": PATIENT_CONTEXT["appointment_date"],
        "appointment_time": PATIENT_CONTEXT["appointment_time"],
        "doctor": PATIENT_CONTEXT["doctor_name"],
        "identity_verified": identity_verified,
        "reason_for_visit": reason_for_visit,
        "medications": json.loads(medications) if medications else [],
        "allergies": json.loads(allergies) if allergies else [],
        "additional_notes": additional_notes,
        "collected_at": datetime.now().isoformat(),
        "collected_by": "heidi-intake-agent-v1",
    }

    # In production: POST to clinic's EHR API
    # For now: save to local file for evaluation
    output_path = f"intake_summary_{PATIENT_CONTEXT['patient_name'].replace(' ', '_').lower()}.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Intake summary saved: {json.dumps(summary, indent=2)}")
    return f"Intake summary saved successfully for {PATIENT_CONTEXT['patient_name']}. The information will be ready for {PATIENT_CONTEXT['doctor_name']}."


@loopback_tool
async def flag_for_clinic_callback(
    ctx: ToolEnv,
    reason: Annotated[str, "Why the patient needs a callback from the clinic staff"],
    urgency: Annotated[str, "One of: 'routine', 'urgent', 'emergency'"],
) -> str:
    """Flag this patient for a callback from clinic staff. Use when:
    - Patient asks a clinical question you cannot answer
    - Patient wants to change or cancel their appointment
    - Patient requests to speak with a human
    - Patient reports symptoms that need clinical attention but are not an emergency
    """

    flag = {
        "patient_name": PATIENT_CONTEXT["patient_name"],
        "phone": PATIENT_CONTEXT["phone"],
        "appointment_date": PATIENT_CONTEXT["appointment_date"],
        "doctor": PATIENT_CONTEXT["doctor_name"],
        "reason": reason,
        "urgency": urgency,
        "flagged_at": datetime.now().isoformat(),
    }

    logger.info(f"Clinic callback flagged: {json.dumps(flag, indent=2)}")
    return f"Got it — I've flagged this for the clinic. Someone from {PATIENT_CONTEXT['clinic_name']} will call you back."
