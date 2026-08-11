import base64
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from backend.languages import DEFAULT_LANGUAGE_ID, LANGUAGES
from backend.personas import PERSONAS
from backend.scenarios import DEFAULT_SCENARIO_ID, SCENARIOS

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calltrainer")

app = FastAPI(title="CallTrainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

EFRE_URL = os.environ.get("EFRE_URL")
EFRE_API_KEY = os.environ.get("EFRE_API_KEY")

STT_MODEL = os.environ.get("STT_MODEL")
LLM_MODEL = os.environ.get("LLM_MODEL")
TTS_MODEL = os.environ.get("TTS_MODEL")

TTS_VOICE = os.environ.get("TTS_VOICE")


# Async client: these calls run inside `async def` routes under Uvicorn/Gunicorn.
# A blocking sync client freezes the event loop for the call's whole duration,
# which starves Gunicorn's worker heartbeat and can trigger a false WORKER TIMEOUT
# well before the configured --timeout is reached.
CLIENT = AsyncOpenAI(base_url=f"{EFRE_URL}/v1", api_key=EFRE_API_KEY)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/personas")
def list_personas() -> list[dict[str, str]]:
    return [
        {"id": p.id, "name": p.name, "training_goal": p.training_goal}
        for p in PERSONAS.values()
    ]


@app.get("/api/languages")
def list_languages() -> list[dict[str, str]]:
    return [{"id": id_, "name": name} for id_, name in LANGUAGES.items()]


@app.post("/api/process")
async def process(
    file: UploadFile = File(...),
    persona_id: str = Form(...),
    language_id: str = Form(DEFAULT_LANGUAGE_ID),
) -> dict[str, str]:
    persona = PERSONAS.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Unknown persona_id: {persona_id}")
    language_name = LANGUAGES.get(language_id)
    if language_name is None:
        raise HTTPException(status_code=404, detail=f"Unknown language_id: {language_id}")
    scenario = SCENARIOS[DEFAULT_SCENARIO_ID]

    audio_bytes = await file.read()
    logger.info(
        "Received audio %r (%d bytes) — persona=%s, language=%s",
        file.filename, len(audio_bytes), persona_id, language_id,
    )

    logger.info("[1/3] Transcribing via STT (%s)...", STT_MODEL)
    try:
        transcription = await CLIENT.audio.transcriptions.create(
            model=STT_MODEL,
            file=(file.filename, audio_bytes, file.content_type),
        )
        transcript = transcription.text
    except Exception as e:
        logger.error("STT request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"STT request failed: {e}") from e
    logger.info("Transcript: %s", transcript)

    logger.info("[2/3] Generating persona reply via LLM (%s)...", LLM_MODEL)
    try:
        completion = await CLIENT.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": persona.as_system_prompt(scenario, language_name),
                },
                {"role": "user", "content": transcript},
            ],
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        logger.error("LLM request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}") from e
    logger.info("Reply: %s", reply)

    logger.info("[3/3] Synthesizing speech via TTS (%s, voice=%s)...", TTS_MODEL, TTS_VOICE)
    try:
        speech = await CLIENT.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=reply,
            response_format="wav",
        )
    except Exception as e:
        logger.error("TTS request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"TTS request failed: {e}") from e
    logger.info("Speech synthesized: %d bytes", len(speech.content))

    return {
        "transcript": transcript,
        "reply": reply,
        "audio_base64": base64.b64encode(speech.content).decode(),
    }


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
