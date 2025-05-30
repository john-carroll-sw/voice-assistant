# Intent: Modular Real-Time Speech Pipeline with WebSockets

## Goal

- Replace the current full-duplex GPT-4o Realtime API usage with a modular pipeline:
  1. Use **gpt-4o-mini-transcribe** for real-time speech-to-text (STT) only.
  2. Run custom "thinking" logic (multi-agent, tool-calling, etc.) in the backend.
  3. Use **gpt-4o-tts** for text-to-speech (TTS) to generate the spoken response.
- Retain the best possible real-time UX using WebSockets (not turn-based HTTP).
- Leverage server-side VAD/turn-detection for natural, auto-stop UX.

## Plan

1. **Frontend**
   - Continue streaming audio chunks to the backend over WebSocket as the user speaks.
   - Receive transcript deltas and final transcript in real time.
   - Receive TTS audio stream and play it back to the user.

2. **Backend**
   - Accept WebSocket connections from the frontend (as now).
   - For each session:
     1. **STT:**
        - Forward incoming audio chunks to the Azure OpenAI gpt-4o-mini-transcribe endpoint (using server_vad for turn detection).
        - Relay transcript deltas and final transcript to the frontend.
     2. **Thinking:**
        - When a final transcript is received, run custom logic (LLM, tool-calling, etc.).
     3. **TTS:**
        - Send the response text to the Azure OpenAI gpt-4o-tts endpoint.
        - Stream the resulting audio back to the frontend over the same WebSocket.
   - Manage session state and message routing for the above pipeline.

3. **Refactor [`rtmt.py`]**
   - Replace the current proxy logic (which connects to the full-duplex endpoint) with a pipeline:
     - STT (gpt-4o-mini-transcribe) → custom logic → TTS (gpt-4o-tts).
   - Use asyncio tasks to handle streaming and message passing between stages.
   - Ensure transcript and audio are streamed to the client as soon as available.

4. **Result**
   - The user gets a real-time, natural, streaming voice assistant experience, with full control over the "thinking" step and best-in-class speech UX.

---

**This file documents the intent and plan for refactoring the real-time backend pipeline.**
