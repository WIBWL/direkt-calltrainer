"""Load test for the schema through the app's own write and read paths, on a
throwaway database beside the one POSTGRES_URL names. Exit 0 only if nothing failed.

    python -m backend.scripts.stress_db --sessions 300 --writers 16
    python -m backend.scripts.stress_db --volume 5000 --readers 32 --duration 20"""
# duplicate-code: copies the test fixtures (not in the image) and the exact wrap-up read.
# pylint: disable=duplicate-code

from __future__ import annotations

import argparse
import logging
import os
import random
import statistics
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import selectinload

# pylint: disable=import-outside-toplevel
from shared.db import ALEMBIC_INI
from shared.db.session import build_database_url
from shared.feedback.acoustics import Pause
from shared.turn import Turn
from backend import consent, library

logger = logging.getLogger("stress")

# Read once, before database_env() points it elsewhere.
_SERVER = os.environ.get("POSTGRES_URL")


def server_url() -> URL:
    if not _SERVER:
        sys.exit("POSTGRES_URL is not set -- `source .env` first")
    return build_database_url()


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Points build_database_url(), and so Alembic and the engine, at `url`."""
    previous = {k: os.environ.pop(k, None) for k in ("POSTGRES_URL", "POSTGRES_PASSWORD")}
    os.environ["POSTGRES_URL"] = url
    try:
        yield
    finally:
        os.environ.pop("POSTGRES_URL")
        os.environ.update({k: v for k, v in previous.items() if v is not None})


@contextmanager
def throwaway_database(keep: bool) -> Iterator[str]:
    """Never the POSTGRES_URL database: tens of thousands of rows would ruin it."""
    server = server_url()
    name = f"calltrainer_stress_{uuid.uuid4().hex[:10]}"
    admin = create_engine(server.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    logger.info("Throwaway database: %s", name)
    try:
        yield server.set(database=name).render_as_string(hide_password=False)
    finally:
        if keep:
            logger.info("Keeping %s -- drop it yourself when done", name)
        else:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            logger.info("Dropped %s", name)
        admin.dispose()


def provision(url: str, pool_size: int) -> None:
    """Migrated and seeded, as the app boots."""
    from alembic import command
    from alembic.config import Config

    from shared.db import session as db_session
    from backend.db.provision import seed

    with database_env(url):
        # Before the engine is built: get_engine() memoises.
        db_session.POOL_SIZE = pool_size
        db_session.POOL_MAX_OVERFLOW = pool_size
        db_session.reset_engine()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        with db_session.session_scope() as db:
            seed(db)
            for index in range(SUBJECTS):
                consent.record_decision(db, subject(index), True)


# Each granted consent in `provision`, or every write is refused (ADR 0066).
SUBJECTS = 50


def subject(index: int) -> str:
    return f"stress-{index % SUBJECTS:03d}"


_SENTENCES = (
    "Guten Tag, vielen Dank fuer Ihren Anruf bei uns im Support.",
    "Ich verstehe Ihr Anliegen und schaue mir das direkt einmal an.",
    "Darf ich kurz nachfragen, seit wann das Problem bei Ihnen auftritt?",
    "Das laesst sich in Ihrem Vertrag ohne Zusatzkosten anpassen.",
    "Ich fasse kurz zusammen, damit wir beide vom Gleichen sprechen.",
    "Wenn das fuer Sie so passt, hinterlege ich das gleich im System.",
)


def synthetic_turns(count: int, rng: random.Random) -> list[Turn]:
    """Plausible, not real values."""
    turns: list[Turn] = []
    clock = 0
    for seq in range(count):
        persona_ms = rng.randint(4000, 12000)
        user_ms = rng.randint(3000, 15000)
        persona_start, clock = clock, clock + persona_ms
        gap = rng.randint(200, 1500)
        user_start, clock = clock + gap, clock + gap + user_ms
        turns.append(Turn(
            seq=seq,
            persona_text=" ".join(rng.choices(_SENTENCES, k=rng.randint(1, 3))),
            user_text=" ".join(rng.choices(_SENTENCES, k=rng.randint(1, 4))),
            persona_offset_ms=persona_start,
            persona_end_ms=persona_start + persona_ms,
            user_offset_ms=user_start,
            user_end_ms=user_start + user_ms,
            user_speech_ms=int(user_ms * 0.8),
            pauses=[Pause(offset_ms=user_start + i * 900,
                          duration_ms=rng.randint(300, 900))
                    for i in range(rng.randint(1, 4))],
            # One sample per 100ms, a third silent, as acoustics.py produces.
            loudness_db=[None if rng.random() < 0.35 else rng.uniform(45.0, 70.0)
                         for _ in range(user_ms // 100)],
        ))
    return turns


@dataclass
class Samples:
    name: str
    values: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wall_s: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, ms: float) -> None:
        with self._lock:
            self.values.append(ms)

    def fail(self, exc: BaseException) -> None:
        with self._lock:
            self.errors.append(f"{type(exc).__name__}: {exc}")

    def quantile(self, q: float) -> float:
        """Nearest-rank: every value reported was actually measured."""
        ordered = sorted(self.values)
        return ordered[min(len(ordered) - 1, int(q * len(ordered)))]

    def report(self) -> str:
        if not self.values:
            return f"{self.name}\n  no successful operations ({len(self.errors)} errors)"
        rate = len(self.values) / self.wall_s if self.wall_s else float("nan")
        return (
            f"{self.name}\n"
            f"  ok={len(self.values)}  errors={len(self.errors)}  "
            f"wall={self.wall_s:.1f}s  throughput={rate:.1f} ops/s\n"
            f"  min={min(self.values):.0f}  p50={self.quantile(0.50):.0f}  "
            f"p95={self.quantile(0.95):.0f}  p99={self.quantile(0.99):.0f}  "
            f"max={max(self.values):.0f}  mean={statistics.fmean(self.values):.0f}  (ms)"
        )


@contextmanager
def timed(samples: Samples) -> Iterator[None]:
    """Swallows the exception: one failure is a data point, not a reason to stop."""
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:  # pylint: disable=broad-except
        samples.fail(exc)
    else:
        samples.record((time.perf_counter() - start) * 1000)


def write_load(
    total: int, workers: int, turns_per_session: int, label: str = "WRITE",
) -> tuple[Samples, list[uuid.UUID]]:
    from backend.session.persistence import FinishedCall, persist_session

    samples = Samples(f"{label}  persist_session  ({workers} threads)")
    written: list[uuid.UUID] = []
    lock = threading.Lock()

    personas = library.list_personas()
    scenarios = library.list_scenarios("stress", 1)

    def one(index: int) -> None:
        rng = random.Random(index)
        extern_id = uuid.uuid4()
        turns = synthetic_turns(turns_per_session, rng)
        with timed(samples):
            stored = persist_session(FinishedCall(
                extern_id=extern_id,
                subject_id=subject(index),
                persona=personas[index % len(personas)],
                scenario=scenarios[index % len(scenarios)],
                turns=turns,
                started_at=datetime.now(UTC) - timedelta(minutes=3),
                reason="completed",
            ))
            # A refusal is not an exception; count it as a failure.
            if stored is None:
                raise RuntimeError(f"persist_session stored nothing for {subject(index)}")
            with lock:
                written.append(extern_id)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(total)))
    samples.wall_s = time.perf_counter() - start
    return samples, written


def read_load(ids: list[uuid.UUID], readers: int, duration_s: float) -> Samples:
    """The query the post-call screen polls, eager loads and all."""
    from shared.db import models as db_models
    from shared.db.session import session_scope

    samples = Samples(f"READ   session by extern_id  ({readers} threads)")
    deadline = time.perf_counter() + duration_s

    def one(seed: int) -> None:
        rng = random.Random(seed)
        while time.perf_counter() < deadline:
            extern_id = rng.choice(ids)
            with timed(samples):
                with session_scope() as db:
                    found = (
                        db.query(db_models.Session)
                        .filter_by(extern_id=extern_id)
                        .options(
                            selectinload(db_models.Session.turns),
                            selectinload(db_models.Session.measurements)
                            .selectinload(db_models.Measurement.metric_type),
                            selectinload(db_models.Session.feedback)
                            .selectinload(db_models.Feedback.points),
                            selectinload(db_models.Session.jobs),
                            selectinload(db_models.Session.persona),
                            selectinload(db_models.Session.scenario),
                        )
                        .one_or_none()
                    )
                    if found is None:
                        raise LookupError(f"{extern_id} not found mid-run")

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=readers) as pool:
        list(pool.map(one, range(readers)))
    samples.wall_s = time.perf_counter() - start
    return samples


def explain_read(extern_id: uuid.UUID) -> str:
    """Whether the unique index on extern_id is used."""
    from shared.db.session import session_scope

    with session_scope() as db:
        rows = db.execute(
            text("EXPLAIN (ANALYZE, BUFFERS) "
                 "SELECT * FROM session WHERE extern_id = :x"),
            {"x": str(extern_id)},
        ).fetchall()
    return "\n".join("  " + row[0] for row in rows)


def table_sizes() -> str:
    from shared.db.session import session_scope

    with session_scope() as db:
        rows = db.execute(text(
            "SELECT relname, n_live_tup, "
            "       pg_size_pretty(pg_total_relation_size(relid)) AS size "
            "FROM pg_stat_user_tables WHERE n_live_tup > 0 "
            "ORDER BY n_live_tup DESC"
        )).fetchall()
    width = max((len(r[0]) for r in rows), default=12)
    return "\n".join(f"  {r[0]:<{width}}  {r[1]:>9,} rows  {r[2]:>10}" for r in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", type=int, default=200,
                        help="Sessions to write in the write phase (default 200)")
    parser.add_argument("--writers", type=int, default=8,
                        help="Concurrent writer threads (default 8)")
    parser.add_argument("--turns", type=int, default=12,
                        help="Exchanges per synthetic Session (default 12)")
    parser.add_argument("--volume", type=int, default=0,
                        help="Sessions to bulk-load before measuring, to test how "
                             "the read scales with table size (default 0)")
    parser.add_argument("--readers", type=int, default=16,
                        help="Concurrent reader threads (default 16)")
    parser.add_argument("--duration", type=float, default=15.0,
                        help="Seconds of read load (default 15)")
    parser.add_argument("--pool-size", type=int, default=5,
                        help="pool_size and max_overflow (default 5, the "
                             "application's own setting)")
    parser.add_argument("--keep", action="store_true",
                        help="Do not drop the throwaway database afterwards")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("backend.session.persistence").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)

    with throwaway_database(args.keep) as url:
        provision(url, args.pool_size)
        with database_env(url):
            print(f"\nPool: size={args.pool_size} + overflow={args.pool_size} "
                  f"(the app itself runs 5 + 5)\n")

            ids: list[uuid.UUID] = []
            if args.volume:
                logger.info("Bulk-loading %d Sessions for volume...", args.volume)
                bulk, loaded = write_load(args.volume, args.writers, args.turns, "FILL ")
                ids.extend(loaded)
                logger.info("  %.1fs, %d errors", bulk.wall_s, len(bulk.errors))

            logger.info("Write phase: %d Sessions x %d turns over %d threads...",
                        args.sessions, args.turns, args.writers)
            writes, written = write_load(args.sessions, args.writers, args.turns)
            ids.extend(written)

            if not ids:
                print("Nothing was written -- no read phase to run.")
                return 1

            logger.info("Read phase: %d threads for %.0fs...", args.readers, args.duration)
            reads = read_load(ids, args.readers, args.duration)

            print("\n" + "=" * 74)
            print(writes.report())
            print(reads.report())
            print("\nTable volume at measurement time:")
            print(table_sizes())
            print("\nPlan for the wrap-up lookup:")
            print(explain_read(ids[0]))
            print("=" * 74)

            for label, samples in (("write", writes), ("read", reads)):
                for message in list(dict.fromkeys(samples.errors))[:5]:
                    print(f"  {label} error: {message}")

            return 1 if writes.errors or reads.errors else 0


if __name__ == "__main__":
    sys.exit(main())
