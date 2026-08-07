import os
from datetime import datetime

from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://calltrainer:calltrainer@localhost:5432/calltrainer"
)

engine = create_engine(DATABASE_URL)


class TrainingRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = "anonymous"
    persona_id: str
    scenario_id: str
    language_id: str
    transcript: str
    reply: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def save_training_record(
    *,
    user_id: str,
    persona_id: str,
    scenario_id: str,
    language_id: str,
    transcript: str,
    reply: str,
) -> TrainingRecord:
    record = TrainingRecord(
        user_id=user_id,
        persona_id=persona_id,
        scenario_id=scenario_id,
        language_id=language_id,
        transcript=transcript,
        reply=reply,
    )
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
    return record


def get_training_records(user_id: str) -> list[TrainingRecord]:
    with Session(engine) as session:
        statement = (
            select(TrainingRecord)
            .where(TrainingRecord.user_id == user_id)
            .order_by(TrainingRecord.created_at.desc())
        )
        return list(session.exec(statement))
