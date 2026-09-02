"""Load test for the Postgres schema, driven through the application's own
write and read paths.

Why not pgbench alone: pgbench measures the server, not this application. What
can actually fall over here is the shape of our own access -- one fat
transaction per finished Session (backend/session/persistence.py), a wide
eager-loaded read per wrap-up poll (backend/api/sessions.py), and a connection
pool of POOL_SIZE + POOL_MAX_OVERFLOW shared by every request. This script
exercises exactly those, so a number it produces means something about the app.

Safety: it refuses to touch the database named in .env. It creates its own
throwaway database, migrates and seeds it the way the app would, and drops it
afterwards -- the same approach the persistence tests take.

    python scripts/stress_db.py --sessions 300 --writers 16
    python scripts/stress_db.py --volume 5000 --readers 32 --duration 20
    python scripts/stress_db.py --sessions 200 --writers 32 --pool-size 20

Exit code is 0 only if no operation failed.
"""

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
from datetime import datetime, timedelta

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import selectinload

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imported after the path insert above, so this file runs as `python
# scripts/stress_db.py` without PYTHONPATH -- the same shape as
# scripts/seed_reference_data.py.
# pylint: disable=wrong-import-position,import-outside-toplevel
from backend.feedback.acoustics import Pause  # noqa: E402
from backend.personas import PERSONAS  # noqa: E402
from backend.scenarios import SCENARIOS  # noqa: E402
from backend.session.models import Turn  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Read, not loaded: dotenv_values leaves os.environ alone, so nothing here can
# put the developer's real database into the environment by accident.
_ENV = dotenv_values(os.path.join(PROJECT_ROOT, ".env"))

logger = logging.getLogger("stress")

_DB_SETTINGS = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
                "POSTGRES_HOST", "POSTGRES_PORT")


# --- Environment ----------------------------------------------------------

def server_url() -> URL:
    """The configured database server, from .env."""
    missing = [k for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
               if not _ENV.get(k)]
    if missing:
        sys.exit(f"Missing from .env: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=_ENV["POSTGRES_USER"],
        password=_ENV["POSTGRES_PASSWORD"],
        host=_ENV.get("POSTGRES_HOST") or "localhost",
        port=int(_ENV.get("POSTGRES_PORT") or 5432),
        database=_ENV["POSTGRES_DB"],
    )


@contextmanager
def database_env(url: str) -> Iterator[None]:
    """Points build_database_url() -- and therefore Alembic and the app's
    engine -- at `url` for the duration of the block."""
    parsed = make_url(url)
    previous = {k: os.environ.get(k) for k in _DB_SETTINGS}
    os.environ.update({
        "POSTGRES_USER": parsed.username,
        "POSTGRES_PASSWORD": parsed.password,
        "POSTGRES_DB": parsed.database,
        "POSTGRES_HOST": parsed.host,
        "POSTGRES_PORT": str(parsed.port or 5432),
    })
    try:
        yield
    finally:
        for key, was in previous.items():
            if was is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = was


@contextmanager
def throwaway_database(keep: bool) -> Iterator[str]:
    """Creates a database for this run and drops it afterwards.

    Never the .env database: a load test writes tens of thousands of rows and
    would leave the development data unusable.
    """
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
    """Migrate to head and seed the reference tables -- the state the app boots
    into."""
    from alembic import command
    from alembic.config import Config

    from backend.db import session as db_session
    from backend.db.provision import seed

    with database_env(url):
        # Set before the engine is built: get_engine() reads these at call time
        # and memoises the result, so raising the pool afterwards has no effect.
        db_session.POOL_SIZE = pool_size
        db_session.POOL_MAX_OVERFLOW = pool_size
        db_session.reset_engine()
        command.upgrade(Config(os.path.join(PROJECT_ROOT, "alembic.ini")), "head")
        with db_session.session_scope() as db:
            seed(db)


# --- Synthetic load -------------------------------------------------------

_SENTENCES = (
    "Guten Tag, vielen Dank fuer Ihren Anruf bei uns im Support.",
    "Ich verstehe Ihr Anliegen und schaue mir das direkt einmal an.",
    "Darf ich kurz nachfragen, seit wann das Problem bei Ihnen auftritt?",
    "Das laesst sich in Ihrem Vertrag ohne Zusatzkosten anpassen.",
    "Ich fasse kurz zusammen, damit wir beide vom Gleichen sprechen.",
    "Wenn das fuer Sie so passt, hinterlege ich das gleich im System.",
)


def synthetic_turns(count: int, rng: random.Random) -> list[Turn]:
    """A Session of `count` exchanges, shaped like a real one.

    Alternating speech windows on a rising timeline, plus the paraverbal facts
    the live path measures per Turn (ADR 0048). Values are plausible, not real:
    the point is row count and column width, not acoustic truth.
    """
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
            # One sample per 100ms, a third of them silent -- the same shape
            # acoustics.py produces.
            loudness_db=[None if rng.random() < 0.35 else rng.uniform(45.0, 70.0)
                         for _ in range(user_ms // 100)],
        ))
    return turns


# --- Measurement ----------------------------------------------------------

@dataclass
class Samples:
    """Latencies of one workload, in milliseconds, plus what went wrong."""

    name: str
    values: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wall_s: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, ms: float) -> None:
        """One successful operation, at `ms` milliseconds."""
        with self._lock:
            self.values.append(ms)

    def fail(self, exc: BaseException) -> None:
        """One failed operation, kept as text so the run can report it."""
        with self._lock:
            self.errors.append(f"{type(exc).__name__}: {exc}")

    def quantile(self, q: float) -> float:
        """The `q`-quantile latency. Nearest-rank, not interpolated: every
        value reported is one that was actually measured."""
        ordered = sorted(self.values)
        return ordered[min(len(ordered) - 1, int(q * len(ordered)))]

    def report(self) -> str:
        """The workload's line in the summary."""
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
    """Times the block, recording either its latency or its exception. Swallows
    the exception on purpose: one failed operation is a data point, not a reason
    to stop the run."""
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:  # pylint: disable=broad-except
        samples.fail(exc)
    else:
        samples.record((time.perf_counter() - start) * 1000)


# --- Workloads ------------------------------------------------------------

def write_load(
    total: int, workers: int, turns_per_session: int, label: str = "WRITE",
) -> tuple[Samples, list[uuid.UUID]]:
    """`total` finished Sessions written concurrently through persist_session --
    the real transaction, including its Measurement rows and its queued job."""
    from backend.session.persistence import persist_session

    samples = Samples(f"{label}  persist_session  ({workers} threads)")
    written: list[uuid.UUID] = []
    lock = threading.Lock()

    def one(index: int) -> None:
        rng = random.Random(index)
        extern_id = uuid.uuid4()
        turns = synthetic_turns(turns_per_session, rng)
        with timed(samples):
            persist_session(
                extern_id=extern_id,
                subject_id=f"stress-{index % 50:03d}",
                persona=PERSONAS[index % len(PERSONAS)],
                scenario=SCENARIOS[index % len(SCENARIOS)],
                turns=turns,
                started_at=datetime.now() - timedelta(minutes=3),
                reason="completed",
            )
        with lock:
            written.append(extern_id)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(total)))
    samples.wall_s = time.perf_counter() - start
    return samples, written


def read_load(ids: list[uuid.UUID], readers: int, duration_s: float) -> Samples:
    """The wrap-up read, hammered for `duration_s`.

    This is the query the post-call screen polls, eager loads and all -- the one
    read that has to stay fast as the tables grow.
    """
    from backend.db import models as db_models
    from backend.db.session import session_scope

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
    """EXPLAIN ANALYZE of the lookup, to show whether the unique index on
    extern_id is used or the planner has fallen back to a sequential scan."""
    from backend.db.session import session_scope

    with session_scope() as db:
        rows = db.execute(
            text("EXPLAIN (ANALYZE, BUFFERS) "
                 "SELECT * FROM session WHERE extern_id = :x"),
            {"x": str(extern_id)},
        ).fetchall()
    return "\n".join("  " + row[0] for row in rows)


def table_sizes() -> str:
    """Row counts and on-disk size per table -- the volume the numbers above
    were measured at."""
    from backend.db.session import session_scope

    with session_scope() as db:
        rows = db.execute(text(
            "SELECT relname, n_live_tup, "
            "       pg_size_pretty(pg_total_relation_size(relid)) AS size "
            "FROM pg_stat_user_tables WHERE n_live_tup > 0 "
            "ORDER BY n_live_tup DESC"
        )).fetchall()
    width = max((len(r[0]) for r in rows), default=12)
    return "\n".join(f"  {r[0]:<{width}}  {r[1]:>9,} rows  {r[2]:>10}" for r in rows)


# --- Entry point ----------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """The command line."""
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
    """Provision a throwaway database, run both workloads, print the report."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # persist_session logs one line per Session; at this volume that is noise.
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
