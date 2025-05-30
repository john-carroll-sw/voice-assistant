import asyncio
import json
import logging
from enum import Enum
from typing import Any, Callable, Optional

import aiohttp
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from order_state import order_state_singleton  # Import the order state singleton

logger = logging.getLogger("coffee-chat")

class ToolResultDirection(Enum):
    TO_SERVER = 1
    TO_CLIENT = 2

class ToolResult:
    text: str
    destination: ToolResultDirection

    def __init__(self, text: str, destination: ToolResultDirection):
        self.text = text
        self.destination = destination

    def to_text(self) -> str:
        if self.text is None:
            return ""
        return self.text if type(self.text) == str else json.dumps(self.text)

class Tool:
    target: Callable[..., ToolResult]
    schema: Any

    def __init__(self, target: Any, schema: Any):
        self.target = target
        self.schema = schema

class RTToolCall:
    tool_call_id: str
    previous_id: str

    def __init__(self, tool_call_id: str, previous_id: str):
        self.tool_call_id = tool_call_id
        self.previous_id = previous_id

class RTMiddleTier:
    endpoint: str
    deployment: str
    key: Optional[str] = None
    
    # Tools are server-side only for now, though the case could be made for client-side tools
    # in addition to server-side tools that are invisible to the client
    tools: dict[str, Tool] = {}

    # Server-enforced configuration, if set, these will override the client's configuration
    # Typically at least the model name and system message will be set by the server
    model: Optional[str] = None
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    disable_audio: Optional[bool] = None
    voice_choice: Optional[str] = None
    api_version: str = "2024-10-01-preview"
    _tools_pending = {}
    _token_provider = None
    _session_map = {}

    def __init__(self, endpoint: str, deployment: str, credentials: AzureKeyCredential | DefaultAzureCredential, voice_choice: Optional[str] = None):
        self.endpoint = endpoint
        self.deployment = deployment
        self.voice_choice = voice_choice
        if voice_choice is not None:
            logger.info("Realtime voice choice set to %s", voice_choice)
        if isinstance(credentials, AzureKeyCredential):
            self.key = credentials.key
        else:
            self._token_provider = get_bearer_token_provider(credentials, "https://cognitiveservices.azure.com/.default")
            self._token_provider() # Warm up during startup so we have a token cached when the first request arrives

    async def _process_message_to_client(self, msg: str, client_ws: web.WebSocketResponse, server_ws: web.WebSocketResponse) -> Optional[str]:
        message = json.loads(msg.data)
        updated_message = msg.data
        session_id = self._session_map[client_ws]
        if message is not None:
            match message["type"]:
                case "session.created":
                    session = message["session"]
                    # Hide the instructions, tools and max tokens from clients, if we ever allow client-side 
                    # tools, this will need updating
                    session["instructions"] = ""
                    session["tools"] = []
                    session["voice"] = self.voice_choice
                    session["tool_choice"] = "none"
                    session["max_response_output_tokens"] = None
                    updated_message = json.dumps(message)

                case "response.output_item.added":
                    if "item" in message and message["item"]["type"] == "function_call":
                        updated_message = None

                case "conversation.item.created":
                    if "item" in message and message["item"]["type"] == "function_call":
                        item = message["item"]
                        if item["call_id"] not in self._tools_pending:
                            self._tools_pending[item["call_id"]] = RTToolCall(item["call_id"], message["previous_item_id"])
                        updated_message = None
                    elif "item" in message and message["item"]["type"] == "function_call_output":
                        updated_message = None

                case "response.function_call_arguments.delta":
                    updated_message = None
                
                case "response.function_call_arguments.done":
                    updated_message = None

                case "response.output_item.done":
                    if "item" in message and message["item"]["type"] == "function_call":
                        item = message["item"]
                        tool_call = self._tools_pending[message["item"]["call_id"]]
                        tool = self.tools[item["name"]]
                        args = item["arguments"]
                        if item["name"] in ["update_order", "get_order"]:
                            result = await tool.target(json.loads(args), session_id)
                        else:
                            result = await tool.target(json.loads(args))
                        await server_ws.send_json({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": item["call_id"],
                                "output": result.to_text() if result.destination == ToolResultDirection.TO_SERVER else ""
                            }
                        })
                        if result.destination == ToolResultDirection.TO_CLIENT:
                            # TODO: this will break clients that don't know about this extra message, rewrite 
                            # this to be a regular text message with a special marker of some sort
                            await client_ws.send_json({
                                "type": "extension.middle_tier_tool_response",
                                "previous_item_id": tool_call.previous_id,
                                "tool_name": item["name"],
                                "tool_result": result.to_text()
                            })
                        updated_message = None

                case "response.done":
                    if len(self._tools_pending) > 0:
                        self._tools_pending.clear() # Any chance tool calls could be interleaved across different outstanding responses?
                        await server_ws.send_json({
                            "type": "response.create"
                        })
                    if "response" in message:
                        replace = False
                        try:
                            for i in range(len(message["response"]["output"]) - 1, -1, -1):
                                if message["response"]["output"][i]["type"] == "function_call":
                                    message["response"]["output"].pop(i)
                                    replace = True
                        except IndexError as e:
                            logging.error(f"Error processing message: {e}")
                        if replace:
                            updated_message = json.dumps(message)

        return updated_message

    async def _process_message_to_server(self, msg: str, ws: web.WebSocketResponse) -> Optional[str]:
        message = json.loads(msg.data)
        updated_message = msg.data
        if message is not None:
            match message["type"]:
                case "session.update":
                    session = message["session"]
                    if self.system_message is not None:
                        session["instructions"] = self.system_message
                    if self.temperature is not None:
                        session["temperature"] = self.temperature
                    if self.max_tokens is not None:
                        session["max_response_output_tokens"] = self.max_tokens
                    if self.disable_audio is not None:
                        session["disable_audio"] = self.disable_audio
                    if self.voice_choice is not None:
                        session["voice"] = self.voice_choice
                    session["tool_choice"] = "auto" if len(self.tools) > 0 else "none"
                    session["tools"] = [tool.schema for tool in self.tools.values()]
                    updated_message = json.dumps(message)

        return updated_message

    async def _stream_to_transcribe(self, audio_queue, transcript_queue):
        """
        Streams audio chunks from audio_queue to Azure gpt-4o-mini-transcribe endpoint,
        relays transcript deltas and final transcript to transcript_queue.
        """
        endpoint = self.endpoint.replace("https", "wss") + "/openai/realtime?api-version=2025-04-01-preview&intent=transcription"
        headers = {"api-key": self.key} if self.key else {"Authorization": f"Bearer {self._token_provider()}"}
        import websockets
        import base64
        async with websockets.connect(endpoint, extra_headers=headers) as ws:
            # Send session config
            session_config = {
                "type": "transcription_session.update",
                "session": {
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "prompt": "Respond in English.",
                    },
                    "turn_detection": {"type": "server_vad"},
                },
            }
            await ws.send(json.dumps(session_config))
            async def send_audio():
                while True:
                    chunk = await audio_queue.get()
                    if chunk is None:
                        break
                    audio_base64 = base64.b64encode(chunk).decode("utf-8")
                    await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio_base64}))
                await ws.send(json.dumps({"type": "input_audio_buffer.end"}))
            async def receive_transcript():
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("type") == "conversation.item.input_audio_transcription.delta":
                        logger.info(f"[STT DELTA] {data.get('delta', '')}")
                        await transcript_queue.put({"delta": data.get("delta", "")})
                    if data.get("type") == "conversation.item.input_audio_transcription.completed":
                        logger.info(f"[STT FINAL] {data.get('transcript', '')}")
                        await transcript_queue.put({"final": data.get("transcript", "")})
                        break
            await asyncio.gather(send_audio(), receive_transcript())

    async def _think(self, transcript):
        # Placeholder for your custom logic (LLM, tool-calling, etc.)
        # For now, just echo the transcript
        return transcript

    async def _text_to_speech(self, text, audio_queue):
        """
        Sends text to gpt-4o-tts endpoint, streams resulting audio chunks to audio_queue.
        """
        # TODO: Implement Azure OpenAI TTS streaming call here
        # For now, just simulate with silence
        import time
        await asyncio.sleep(0.5)
        await audio_queue.put(b"FAKEAUDIO")
        await audio_queue.put(None)

    async def _forward_messages(self, ws: web.WebSocketResponse):
        # Queues for streaming between stages
        audio_queue = asyncio.Queue()
        transcript_queue = asyncio.Queue()
        tts_audio_queue = asyncio.Queue()
        # Start STT streaming task
        stt_task = asyncio.create_task(self._stream_to_transcribe(audio_queue, transcript_queue))
        # Start TTS streaming task (will be triggered after thinking)
        tts_task = None
        # Main loop: receive audio from client, send transcript, run thinking, send TTS
        try:
            while True:
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await audio_queue.put(msg.data)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    # Optionally handle text messages (e.g., control)
                    pass
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    await audio_queue.put(None)
                    break
                # Check for transcript
                while not transcript_queue.empty():
                    tmsg = await transcript_queue.get()
                    if "delta" in tmsg:
                        await ws.send_json({"type": "transcript.delta", "delta": tmsg["delta"]})
                    if "final" in tmsg:
                        await ws.send_json({"type": "transcript.final", "text": tmsg["final"]})
                        # Run thinking
                        response_text = await self._think(tmsg["final"])
                        # Start TTS
                        tts_task = asyncio.create_task(self._text_to_speech(response_text, tts_audio_queue))
                # Stream TTS audio to client
                if tts_task and not tts_audio_queue.empty():
                    audio_chunk = await tts_audio_queue.get()
                    if audio_chunk is not None:
                        await ws.send_bytes(audio_chunk)
        finally:
            stt_task.cancel()
            if tts_task:
                tts_task.cancel()

    async def _websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Create a new session for each WebSocket connection
        session_id = order_state_singleton.create_session()
        self._session_map[ws] = session_id

        await self._forward_messages(ws)
        return ws
    
    def attach_to_app(self, app, path):
        app.router.add_get(path, self._websocket_handler)
