# JARVIS — Voice AI Assistant for macOS

Voice assistant inspired by Iron Man's JARVIS: talks on any topic and **controls the Mac** to complete tasks.

## Features
- 🎙 Voice input (wake word) and natural speech output (ElevenLabs / Gemini TTS / Edge TTS / macOS voice)
- 🧠 Two interchangeable "brains": **Claude (Anthropic API)** or **Gemini API** with tool calling
- 🖥 Mac control tools: shell commands, AppleScript, screenshots + vision (`look_at_screen`), mouse clicks, typing, hotkeys, scrolling
- 🌐 Web search for news, weather, facts
- 💾 Long-term memory: `remember` / `recall` / `forget`, conversation summaries
- 📚 Self-improvement: after each task it reflects and saves "lessons" for next time
- 😀 Animated face with emotions (GUI), text mode for debugging
- 🔒 Confirmation before risky actions

## Stack
Python · Anthropic API · Gemini API · function/tool calling · speech recognition · TTS · pyautogui · AppleScript · multithreading / asyncio

## Run
```bash
pip install -r requirements.txt
cp .env.example .env     # add API keys
python3 jarvis.py         # voice + face
python3 jarvis.py --text  # text mode
```
