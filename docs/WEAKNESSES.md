# Known Weaknesses & What I'd Harden First

The agent works end to end and passes safety checks reliably, but there are real gaps I'd need to close before putting this in front of patients at scale.

The biggest one is drug names through the voice pipeline. I ran 30 common medications through Cartesia's TTS then back through STT, and 6 came back wrong. "Omeprazole" became "Omprazole", "atorvastatin" became "adivistatin". These are small vowel errors but in healthcare, close enough is not good enough. Cartesia supports custom pronunciation dictionaries. I'd load the top 200 medications into that and re-run until we're above 95%.

Second, I haven't tested accents at all. Heidi's clinicians specifically flagged this. A patient with a heavy accent saying "levothyroxine" is a very different STT challenge than my typed text input. I'd need to generate accent-localized audio samples and measure how often drug names survive that path.

Third, my eval only tests the LLM reasoning in text mode. It doesn't test what happens when a real patient interrupts mid-sentence, pauses for 10 seconds to check a pill bottle, or talks over the agent. The scripted conversation simulator can't capture any of that. A proper audio-path eval would mean deploying the agent, running real voice calls, pulling transcripts, and comparing against expected input.

Fourth, safety checks use keyword matching which I already know is fragile. I found 3 false positives in my first eval run. The agent was actually behaving correctly but my checks were too narrow. Going the other direction, a subtly unsafe response wrapped in clinical language would slip through entirely. I've drafted LLM-as-judge prompts for Cartesia's Line metrics that would catch these, but haven't validated them yet.

Fifth, latency was mostly fine (700ms to 1000ms per turn) but I saw one 8-second outlier on a summary turn. That's too long for a live conversation. Line tracks this automatically on deployed agents, but I haven't set thresholds or alerts.

Hardening priority: pronunciation dictionary first, then LLM safety judge, then accent testing, then full audio-path eval with real calls.