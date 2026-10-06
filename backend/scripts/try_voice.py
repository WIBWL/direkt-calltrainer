"""Audition KugelAudio voices: synthesize a line per voice id, then transcribe it
back, since a voice can return audio of the right length and be unintelligible.

    python -m backend.scripts.try_voice [--language de] [--text "..."] 1885 1071
    python -m backend.scripts.try_voice --list
"""
import argparse
import asyncio
import os

from backend.clients import stt, tts
from backend.clients.config import KUGELAUDIO_CLIENT, KUGELAUDIO_MODEL

SAMPLE_TEXT = {
    "en": (
        "Hi, this is Samantha Ferris from marketing, I'm calling about the "
        "recent increase in our subscription costs."
    ),
    "de": "Guten Tag, hier ist Thomas Brandt, ich habe eine Frage zu unserem aktuellen Vertrag.",
}


def list_voices() -> None:
    offset = 0
    while True:
        page = KUGELAUDIO_CLIENT.voices.list(limit=50, offset=offset)
        voices = page.voices or []
        if not voices:
            return
        for v in voices:
            langs = ",".join(v.supported_languages or []) or "?"
            print(f"  {v.id:>5}  {langs:<12} {v.quality:<5} {v.name}")
        offset += 50


async def audition(voice_ids: list[int], text: str, language: str, out_dir: str) -> int:
    failures = 0
    for voice_id in voice_ids:
        # Straight at KugelAudio, bypassing the client wrapper.
        try:
            response = await KUGELAUDIO_CLIENT.tts.generate_async(
                text=text, model_id=KUGELAUDIO_MODEL, voice_id=voice_id, language=language
            )
        except Exception as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            print(f"  {voice_id}: SYNTHESIS FAILED - {type(e).__name__}: {e}")
            failures += 1
            continue

        wav = tts._pcm16_to_wav(response.audio, response.sample_rate)  # pylint: disable=protected-access
        path = os.path.join(out_dir, f"voice_{voice_id}.wav")
        with open(path, "wb") as f:
            f.write(wav)

        heard = (await stt.transcribe(wav, "audition.wav", "audio/wav", language)).strip()
        seconds = len(response.audio) / 2 / response.sample_rate
        print(f"  {voice_id}: {seconds:.1f}s -> {path}")
        print(f"         heard: {heard}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("voice_ids", nargs="*", type=int, help="KugelAudio voice ids")
    parser.add_argument("--language", default="en", help="bare code, e.g. en or de (not en-GB)")
    parser.add_argument("--text", help="line to speak; defaults to a sample in that language")
    parser.add_argument("--out-dir", default=".", help="where to write the .wav files")
    parser.add_argument("--list", action="store_true", help="list available voices and exit")
    args = parser.parse_args()

    if args.list:
        list_voices()
        return 0
    if not args.voice_ids:
        parser.error("give at least one voice id, or --list")

    text = args.text or SAMPLE_TEXT.get(args.language) or SAMPLE_TEXT["en"]
    print(f"spoken: {text}\n")
    return 1 if asyncio.run(audition(args.voice_ids, text, args.language, args.out_dir)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
