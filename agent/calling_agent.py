from agent.prompt import prompt,introduction

import os
import json
import logging

from line.llm_agent import LlmAgent, LlmConfig,  end_call
from line.voice_agent_app import  AgentEnv, CallRequest

from tools import save_intake_summary, flag_for_clinic_callback, verify_medication
from patient_context import PATIENT_CONTEXT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = prompt(PATIENT_CONTEXT)
INTRODUCTION = introduction(PATIENT_CONTEXT)

async def get_agent(env: AgentEnv, call_request: CallRequest):
    return LlmAgent(
        model="gpt-4o", # I am saving some of my cost by using gpt 4o and mini versions
        api_key=os.getenv("OPENAI_API_KEY"),
        tools=[verify_medication, save_intake_summary, flag_for_clinic_callback, end_call],
        config=LlmConfig(
            system_prompt=SYSTEM_PROMPT,
            introduction=INTRODUCTION,
            temperature=0.4,  # Lower temp for clinical accuracy
        ),
    )

