import base64
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

load_dotenv()

app = FastAPI(title="CallTrainer API")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

LLM_URL = os.environ.get("LLM_URL")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
STT_MODEL = os.environ.get("STT_MODEL")
LLM_MODEL = os.environ.get("LLM_MODEL")
TTS_MODEL = os.environ.get("TTS_MODEL")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/process")
async def process(file: UploadFile = File(...)) -> dict[str, str]:
    audio_bytes = await file.read()
    client = OpenAI(base_url=f"{LLM_URL.rstrip('/')}/v1", api_key=LLM_API_KEY)

    try:
        transcript = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=(file.filename, audio_bytes, file.content_type),
        ).text

        translation = client.chat.completions.create(
            model=LLM_MODEL
        ,
            messages=[
                {
                    "role": "system",
                    "content": "Translate the user's message into English. Reply with only the translation, nothing else.",
                },
                {"role": "user", "content": transcript},
            ],
        ).choices[0].message.content

        speech = client.audio.speech.create(
            model=TTS_MODEL,
            voice="alloy",
            input=translation,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}") from e

    return {
        "transcript": transcript,
        "translation": translation,
        "audio_base64": base64.b64encode(speech.content).decode(),
    }


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
