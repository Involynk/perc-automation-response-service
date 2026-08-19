import logging
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.processed_event import ProcessedEventModel

logger = logging.getLogger(__name__)


class ProcessedEventRepository:
    """
    Repository for persisting and checking Kafka event IDs in PostgreSQL
    for cluster-wide durable idempotency across multiple replica pods.
    """

    def __init__(self, db: Session):
        self.db = db

    def is_already_processed(self, event_id: str) -> bool:
        """Check if event_id already exists in PostgreSQL."""
        try:
            exists = (
                self.db.query(
                    self.db.query(ProcessedEventModel)
                    .filter(ProcessedEventModel.event_id == event_id)
                    .exists()
                ).scalar()
            )
            return bool(exists)
        except Exception as exc:
            logger.error(f"Error checking event idempotency for {event_id}: {exc}")
            raise exc

    def record_processed_event(
        self,
        event_id: str,
        topic: str,
        lead_id: str,
    ) -> Optional[ProcessedEventModel]:
        """
        Record a processed event in PostgreSQL.
        Handles duplicate checks and concurrent race conditions gracefully.
        """
        if self.is_already_processed(event_id):
            logger.info(f"Duplicate event already recorded in DB: event_id={event_id}")
            return None

        try:
            record = ProcessedEventModel(
                event_id=event_id,
                topic=topic,
                lead_id=lead_id,
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            logger.info(f"💾 Persisted durable event idempotency: event_id={event_id} topic={topic}")
            return record
        except IntegrityError:
            self.db.rollback()
            logger.info(f"Concurrent duplicate event detected in DB: event_id={event_id}")
            return None
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to persist event record for {event_id}: {exc}")
            raise exc
