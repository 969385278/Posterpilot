from uuid import UUID

from sqlalchemy import select, update

from app.core.exceptions import PosterPilotError
from app.persistence.database import Database
from app.persistence.models import DecisionCardRow
from app.schemas.decision import DecisionCard


class DecisionRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self, card_id: UUID) -> DecisionCard:
        with self.database.session() as session:
            row = session.get(DecisionCardRow, str(card_id))
            if row is None:
                raise PosterPilotError("决策卡不存在", code="decision_not_found", status_code=404)
            return DecisionCard.model_validate(row.payload)

    def list(self, *, approved_only=False) -> list[DecisionCard]:
        query = select(DecisionCardRow)
        if approved_only:
            query = query.where(DecisionCardRow.status == "approved")
        with self.database.session() as session:
            return [DecisionCard.model_validate(row.payload) for row in session.scalars(query)]

    def insert(self, card: DecisionCard) -> DecisionCard:
        with self.database.session() as session:
            session.add(
                DecisionCardRow(
                    id=str(card.id),
                    revision=card.revision,
                    status=card.status,
                    payload=card.model_dump(mode="json"),
                )
            )
            session.commit()
        return card

    def replace(self, card: DecisionCard, *, expected_revision: int) -> DecisionCard:
        with self.database.session() as session:
            result = session.execute(
                update(DecisionCardRow)
                .where(
                    DecisionCardRow.id == str(card.id),
                    DecisionCardRow.revision == expected_revision,
                )
                .values(
                    revision=card.revision, status=card.status, payload=card.model_dump(mode="json")
                )
            )
            if result.rowcount != 1:
                raise PosterPilotError(
                    "决策卡已更新，请刷新",
                    code="stale_decision_revision",
                    status_code=409,
                )
            session.commit()
        return card
