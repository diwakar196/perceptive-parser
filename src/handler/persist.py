import logging

from fastapi import HTTPException

storage: list[dict] = []

logger = logging.getLogger(__name__)


class PersistHandler:

    @staticmethod
    def save(data: dict) -> None:
        try :
            storage.append(data)
            logger.info(f"Data saved successfully: {data}")
        except Exception as e:
            logger.error(f"Error while saving data: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_all() -> list[dict]:
        return storage

    @staticmethod
    def get_by_id(id: int) -> dict | None:
        if 0 <= id < len(storage):
            return storage[id]
        return None

