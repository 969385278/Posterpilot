import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from app.schemas.assistant import AssistantAnswer


class AssistantRepository:
    """Small, durable conversation log separate from generation checkpoints."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS assistant_answers ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, "
                "conversation_id TEXT NOT NULL, run_id TEXT, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS assistant_conversation "
                "ON assistant_answers(conversation_id, sequence)"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, answer: AssistantAnswer) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO assistant_answers(id,conversation_id,run_id,payload) VALUES(?,?,?,?)",
                (
                    str(answer.id),
                    str(answer.conversation_id),
                    str(answer.run_id) if answer.run_id else None,
                    answer.model_dump_json(),
                ),
            )

    def history(self, conversation_id: UUID) -> list[AssistantAnswer]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM assistant_answers WHERE conversation_id=? "
                "ORDER BY sequence DESC LIMIT 10",
                (str(conversation_id),),
            ).fetchall()
        return [AssistantAnswer.model_validate(json.loads(row[0])) for row in reversed(rows)]

    def get(self, answer_id: UUID) -> AssistantAnswer | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM assistant_answers WHERE id=?", (str(answer_id),)
            ).fetchone()
        return AssistantAnswer.model_validate_json(row[0]) if row else None
