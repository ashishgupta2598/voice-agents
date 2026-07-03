import os
from dotenv import load_dotenv
load_dotenv()

from agent.calling_agent import get_agent
from line.voice_agent_app import VoiceAgentApp



app = VoiceAgentApp(get_agent=get_agent)
if __name__ == "__main__":
    app.run()