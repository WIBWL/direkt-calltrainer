"""Reading the text out of an uploaded PDF (F-58), in a process of its own.

pypdf is a pure-Python parser fed a file the User chose, and a crafted PDF can
make it loop or inflate a stream far past the upload's size. Run on the
backend's one event loop, one such file froze every live call (ADR 0109). So
`read_pdf` hands the bytes to `python -m backend.pdf_text`, which runs under a
memory ceiling and is killed after `READ_TIMEOUT_S`. Nothing here imports the
model client, so the child starts in a fraction of a second.
"""
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

# Every upload is read into memory before it is parsed, so this is a memory
# bound, not a policy one. The number lives once, here, and the German message
# below is built from it: a literal "5 MB" in a string drifts the first time
# this changes.
MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
TOO_LARGE = f"Die Datei ist größer als {MAX_UPLOAD_MB} MB."

# A text-layer PDF of 5 MB reads in well under a second; thirty is for a slow
# machine, not for a document that needs it.
READ_TIMEOUT_S = 30.0
# The child's address space. A decompression bomb then ends in a MemoryError in
# the child rather than in the backend's memory. Linux only: macOS refuses
# RLIMIT_AS, and development runs without the ceiling.
CHILD_MEMORY_BYTES = 1024 * 1024 * 1024
# PDFs read at once across all Users; the rest wait their turn. Each is a
# process, and the per-User rate limit alone does not bound the sum.
MAX_READERS = 2

_UNREADABLE = "Die Datei konnte nicht als PDF gelesen werden."
_TOO_SLOW = (
    "Das Lesen der Datei hat zu lange gedauert. Bitte eine kleinere oder "
    "einfacher aufgebaute PDF-Datei verwenden."
)

# What the child runs, after the interpreter. A module constant so a test can
# swap in a child that hangs or crashes.
_CHILD_ARGS: tuple[str, ...] = ("-m", "backend.pdf_text")
# The directory `backend` is importable from, whatever the parent's cwd.
_IMPORT_ROOT = Path(__file__).resolve().parents[1]

_readers = asyncio.Semaphore(MAX_READERS)


class DocumentError(ValueError):
    """The upload is not a usable text-layer PDF. The message is shown to the
    User as-is, so it is in German."""


def labelled(name: str, message: str) -> str:
    """`message`, saying which file it is about. A lone upload names nothing --
    the User has exactly one file in mind and the name would be noise -- but one
    bad file among several has to be identifiable, or the whole batch is."""
    return f"{name}: {message}" if name else message


def extract_pdf_text(data: bytes, name: str = "") -> tuple[str, int]:
    """The full extracted text of a text-layer PDF plus its page count. Every
    page is read -- the upload gates are the only bound (`summarise_facts` then
    hands the whole text to the model). Raises DocumentError for anything that
    is not a readable text PDF; `name` puts the offending file in the message
    where a request carried more than one.

    Runs in whatever process calls it; the route reaches it through `read_pdf`."""
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
            parts.append("")  # a broken page is skipped, not fatal
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
    """`extract_pdf_text` in a child process that is killed after
    `READ_TIMEOUT_S`. A child that crashes, runs out of memory or overruns is
    a DocumentError like any other unreadable file."""
    # The cheap refusals need no process.
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
            # Also on cancellation: a client that goes away must not leave the
            # child parsing.
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
    """Cap this process's address space at `CHILD_MEMORY_BYTES`, where the
    platform allows it."""
    try:
        import resource  # pylint: disable=import-outside-toplevel  # POSIX only

        resource.setrlimit(resource.RLIMIT_AS, (CHILD_MEMORY_BYTES, CHILD_MEMORY_BYTES))
    except (ImportError, ValueError, OSError):
        pass


def main() -> None:
    """The child: PDF bytes on stdin, one JSON object on stdout -- the text and
    page count, or the German refusal (unnamed; the parent names the file)."""
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
