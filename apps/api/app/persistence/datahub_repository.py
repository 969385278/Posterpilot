from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import PosterPilotError
from app.persistence.database import Database
from app.persistence.models import HubCaseRow
from app.schemas.datahub import HubCase


class DataHubRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self, case_id: UUID) -> HubCase:
        with self.database.session() as session:
            row = session.get(HubCaseRow, str(case_id))
            if row is None:
                raise PosterPilotError("案例不存在。", code="case_not_found", status_code=404)
            return HubCase.model_validate(row.payload)

    def find_source(self, run_id: UUID, round_number: int) -> HubCase | None:
        with self.database.session() as session:
            row = session.scalar(
                select(HubCaseRow).where(
                    HubCaseRow.run_id == str(run_id),
                    HubCaseRow.round_number == round_number,
                )
            )
            return HubCase.model_validate(row.payload) if row else None

    def list(self, *, status: str | None = None, run_id: UUID | None = None) -> list[HubCase]:
        statement = select(HubCaseRow)
        if status:
            statement = statement.where(HubCaseRow.status == status)
        if run_id:
            statement = statement.where(HubCaseRow.run_id == str(run_id))
        with self.database.session() as session:
            values = [HubCase.model_validate(row.payload) for row in session.scalars(statement)]
        return sorted(values, key=lambda case: (case.created_at, case.round_number), reverse=True)

    def insert(self, case: HubCase) -> HubCase:
        try:
            with self.database.session() as session:
                session.add(
                    HubCaseRow(
                        id=str(case.id),
                        run_id=str(case.run_id),
                        round_number=case.round_number,
                        revision=case.revision,
                        status=case.status,
                        payload=case.model_dump(mode="json"),
                    )
                )
                session.commit()
        except IntegrityError:
            existing = self.find_source(case.run_id, case.round_number)
            if existing is None:
                raise
            if existing.evidence_hash != case.evidence_hash:
                raise PosterPilotError(
                    "该轮来源已变化，不能覆盖已保存证据。",
                    code="evidence_changed",
                    status_code=409,
                ) from None
            return existing
        return case

    def replace(self, case: HubCase, *, expected_revision: int) -> HubCase:
        with self.database.session() as session:
            result = session.execute(
                update(HubCaseRow)
                .where(
                    HubCaseRow.id == str(case.id),
                    HubCaseRow.revision == expected_revision,
                )
                .values(
                    revision=case.revision,
                    status=case.status,
                    payload=case.model_dump(mode="json"),
                )
            )
            if result.rowcount != 1:
                raise PosterPilotError(
                    "案例已被修改，请刷新后重新提交。",
                    code="stale_case_revision",
                    status_code=409,
                )
            session.commit()
        return case
