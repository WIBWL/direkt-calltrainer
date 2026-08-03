import base64
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from backend.languages import DEFAULT_LANGUAGE_ID, LANGUAGES
from backend.personas import PERSONAS
from backend.scenarios import DEFAULT_SCENARIO_ID, SCENARIOS

load_dotenv()

app = FastAPI(title="CallTrainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

LLM_URL = os.environ.get("LLM_URL")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
STT_MODEL = os.environ.get("STT_MODEL")
LLM_MODEL = os.environ.get("LLM_MODEL")
TTS_MODEL = os.environ.get("TTS_MODEL")


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
    client = OpenAI(base_url=f"{LLM_URL.rstrip('/')}/v1", api_key=LLM_API_KEY)

    try:
        transcript = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=(file.filename, audio_bytes, file.content_type),
        ).text

        reply = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": persona.as_system_prompt(scenario, language_name),
                },
                {"role": "user", "content": transcript},
            ],
        ).choices[0].message.content

        speech = client.audio.speech.create(
            model=TTS_MODEL,
            voice="alloy",
            input=reply,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}") from e

    return {
        "transcript": transcript,
        "reply": reply,
        "audio_base64": base64.b64encode(speech.content).decode(),
    }


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
