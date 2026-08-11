"""Fake OpenAI-compatible server for testing the app without a real EFRE_API_KEY.

Run: python scripts/mock_llm_server.py
Then in .env, temporarily set: EFRE_URL=http://localhost:9000
(EFRE_API_KEY and the model names can stay whatever they are — this server ignores them.)
"""

import io
import time
import wave

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI()


def _silent_wav(seconds: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


@app.post("/v1/audio/transcriptions")
async def transcriptions(request: Request):
    return {"text": "Hallo, das ist ein Test-Transkript."}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello, this is a test transcript."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.post("/v1/audio/speech")
async def speech(request: Request):
    return Response(content=_silent_wav(), media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
