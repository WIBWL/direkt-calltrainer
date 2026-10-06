"""Reading a PDF's text in a child process (F-58, ADR 0109): a crafted PDF once
froze every live call on the event loop. The child is memory-capped and killed
after READ_TIMEOUT_S; this module imports no model client, so it starts fast."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.authored_text import clean

logger = logging.getLogger(__name__)

# A memory bound: uploads are read into memory before parsing.
MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
TOO_LARGE = f"Die Datei ist größer als {MAX_UPLOAD_MB} MB."

READ_TIMEOUT_S = 30.0
# Linux only: macOS refuses RLIMIT_AS.
CHILD_MEMORY_BYTES = 1024 * 1024 * 1024
# Across all Users; each read is a process, which the per-User limit does not bound.
MAX_READERS = 2

_UNREADABLE = "Die Datei konnte nicht als PDF gelesen werden."
_TOO_SLOW = (
    "Das Lesen der Datei hat zu lange gedauert. Bitte eine kleinere oder "
    "einfacher aufgebaute PDF-Datei verwenden."
)

# Swappable by tests for a child that hangs or crashes.
_CHILD_ARGS: tuple[str, ...] = ("-m", "backend.pdf_text")
_IMPORT_ROOT = Path(__file__).resolve().parents[1]

_readers = asyncio.Semaphore(MAX_READERS)


class DocumentError(ValueError):
    """Shown to the User as-is, so German."""


def labelled(name: str, message: str) -> str:
    """A lone upload names nothing; one bad file among several must be named."""
    return f"{name}: {message}" if name else message


def extract_pdf_text(data: bytes, name: str = "") -> tuple[str, int]:
    """Text and page count; every page is read. Runs in the caller's process;
    the route reaches it through `read_pdf`."""
    if not data:
        raise DocumentError(labelled(name, "Die Datei ist leer."))
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(labelled(name, TOO_LARGE))

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, OSError, ValueError) as e:
        raise DocumentError(labelled(name, _UNREADABLE)) from e

    if reader.is_encrypted:
        raise DocumentError(labelled(name, "Das PDF ist passwortgeschützt."))

    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except (PdfReadError, KeyError, ValueError):
            parts.append("")
    text = clean("\n".join(parts))

    if not text.strip():
        raise DocumentError(
            labelled(
                name,
                "In diesem PDF wurde kein Text gefunden. Eingescannte oder "
                "abfotografierte Dokumente werden nicht unterstützt.",
            )
        )
    return text, len(reader.pages)


async def read_pdf(data: bytes, name: str = "") -> tuple[str, int]:
    """A crash, OOM or overrun is a DocumentError like any unreadable file."""
    if not data:
        raise DocumentError(labelled(name, "Die Datei ist leer."))
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(labelled(name, TOO_LARGE))

    async with _readers:
        child = await asyncio.create_subprocess_exec(
            sys.executable, *_CHILD_ARGS,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=_IMPORT_ROOT,
        )
        try:
            out, _ = await asyncio.wait_for(child.communicate(data), READ_TIMEOUT_S)
        except TimeoutError as e:
            logger.warning("PDF read overran %.0f s; child killed", READ_TIMEOUT_S)
            raise DocumentError(labelled(name, _TOO_SLOW)) from e
        finally:
            # Also on cancellation: a vanished client must not leave the child parsing.
            if child.returncode is None:
                child.kill()
                await child.wait()

    if child.returncode != 0:
        logger.warning("PDF read failed in the child (exit %s)", child.returncode)
        raise DocumentError(labelled(name, _UNREADABLE))
    reply = json.loads(out)
    if "error" in reply:
        raise DocumentError(labelled(name, reply["error"]))
    return reply["text"], reply["pages"]


def _limit_memory() -> None:
    try:
        import resource  # pylint: disable=import-outside-toplevel  # POSIX only

        resource.setrlimit(resource.RLIMIT_AS, (CHILD_MEMORY_BYTES, CHILD_MEMORY_BYTES))
    except (ImportError, ValueError, OSError):
        pass


def main() -> None:
    """The child: PDF bytes on stdin, one JSON object on stdout."""
    _limit_memory()
    data = sys.stdin.buffer.read()
    try:
        text, pages = extract_pdf_text(data)
        reply: dict = {"text": text, "pages": pages}
    except DocumentError as e:
        reply = {"error": str(e)}
    sys.stdout.write(json.dumps(reply))


if __name__ == "__main__":
    main()
