import logging
from fastapi import UploadFile, HTTPException
from src.handler import persist

logger = logging.getLogger(__name__)


class ParseHandler:

    @staticmethod
    async def handle_parse(file: UploadFile) -> dict:
        try :
            content = await file.read()
            
            result = {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(content)
            }
            
            return result

        except Exception as e:
            logger.error(f"Error parsing file: {e}")
            raise HTTPException(status_code=500, detail=str(e))




    async def persist_result(self, result: dict) -> None:
        persist.PersistHandler.save(result)

