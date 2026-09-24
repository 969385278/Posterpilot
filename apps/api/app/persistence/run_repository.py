from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import literal_column, select, update

from app.core.exceptions import PosterPilotError
from app.persistence.database import Database
from app.persistence.models import RunRow
from app.schemas.brief import PosterBrief
from app.schemas.run import ArtifactReference, RunRecord, RunStatus


class RunNotFoundError(PosterPilotError):
    def __init__(self, run_id: UUID):
        super().__init__(
            f"Run {run_id} was not found.",
            code="run_not_found",
            status_code=404,
        )


class RunRepository:
    def __init__(self, database_url: str):
        self.database = Database(database_url)

    def create(self, brief: PosterBrief) -> RunRecord:
        record = RunRecord(brief=brief)
        row = RunRow(
            id=str(record.id),
            status=record.status,
            brief=brief.model_dump(mode="json"),
            current_node=record.current_node,
            error_code=record.error_code,
            error_message=record.error_message,
            artifacts=[],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        with self.database.session() as session:
            session.add(row)
            session.commit()
        return record

    def interrupt_abandoned_runs(self) -> list[RunRecord]:
        """Caller must own the exclusive runtime lock; preserve paused/final runs."""
        with self.database.session() as session:
            rows = session.scalars(
                update(RunRow)
                .where(RunRow.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    current_node="startup_recovery",
                    error_code="execution_interrupted",
                    error_message="上次服务退出时执行尚未完成。已有版本已保留，请检查后新建任务；未自动重放模型调用。",
                    updated_at=datetime.now(UTC),
                )
                .returning(RunRow)
            ).all()
            records = [self._to_record(row) for row in rows]
            session.commit()
            return records

    def get(self, run_id: UUID) -> RunRecord | None:
        with self.database.session() as session:
            row = session.get(RunRow, str(run_id))
            return self._to_record(row) if row else None

    def list(self, *, limit: int = 50) -> list[RunRecord]:
        bounded_limit = max(1, min(limit, 200))
        with self.database.session() as session:
            # Windows clocks may give adjacent inserts identical timestamps. SQLite
            # rowid preserves insertion order for this ordinary rowid table; UUID4
            # ordering does not. Other database backends still get a stable tie-break.
            tie_break = literal_column("rowid") if self.database.engine.dialect.name == "sqlite" else RunRow.id
            statement = select(RunRow).order_by(RunRow.created_at.desc(), tie_break.desc()).limit(bounded_limit)
            rows = session.scalars(statement).all()
            return [self._to_record(row) for row in rows]

    def update_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        current_node: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> RunRecord:
        with self.database.session() as session:
            row = session.get(RunRow, str(run_id))
            if row is None:
                raise RunNotFoundError(run_id)

            row.status = status
            row.current_node = current_node
            row.error_code = error_code
            row.error_message = error_message
            row.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    def failed_page(self, *, after_id: UUID | None = None, limit: int = 100) -> list[RunRecord]:
        """Keyset page for recoverable failure projections, without the UI history cap."""
        statement = select(RunRow).where(RunRow.status == "failed")
        if after_id is not None:
            statement = statement.where(RunRow.id > str(after_id))
        statement = statement.order_by(RunRow.id).limit(max(1, min(limit, 200)))
        with self.database.session() as session:
            return [self._to_record(row) for row in session.scalars(statement).all()]

    def transition_status(
        self,
        run_id: UUID,
        *,
        expected: RunStatus,
        status: RunStatus,
        current_node: str,
        expected_updated_at: datetime | None = None,
    ) -> RunRecord | None:
        """Claim a transition in the database; only one concurrent caller wins."""
        with self.database.session() as session:
            statement = update(RunRow).where(RunRow.id == str(run_id), RunRow.status == expected)
            if expected_updated_at is not None:
                statement = statement.where(RunRow.updated_at == expected_updated_at)
            result = session.execute(
                statement.values(
                    status=status,
                    current_node=current_node,
                    error_code=None,
                    error_message=None,
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
            row = session.get(RunRow, str(run_id))
            return self._to_record(row)

    def add_artifact(self, run_id: UUID, artifact: ArtifactReference) -> RunRecord:
        with self.database.session() as session:
            row = session.get(RunRow, str(run_id))
            if row is None:
                raise RunNotFoundError(run_id)

            row.artifacts = [*row.artifacts, artifact.model_dump(mode="json")]
            row.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(row)
            return self._to_record(row)

    @staticmethod
    def _to_record(row: RunRow) -> RunRecord:
        return RunRecord.model_validate(
            {
                "id": row.id,
                "status": row.status,
                "brief": row.brief,
                "current_node": row.current_node,
                "error_code": row.error_code,
                "error_message": row.error_message,
                "artifacts": row.artifacts,
                "created_at": RunRepository._as_utc(row.created_at),
                "updated_at": RunRepository._as_utc(row.updated_at),
            }
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
