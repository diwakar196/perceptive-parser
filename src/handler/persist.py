storage: list[dict] = []


class PersistHandler:

    @staticmethod
    def save(data: dict) -> None:
        storage.append(data)

    @staticmethod
    def get_all() -> list[dict]:
        return storage

    @staticmethod
    def get_by_id(id: int) -> dict | None:
        if 0 <= id < len(storage):
            return storage[id]
        return None

