from fastapi import UploadFile
from src.handler import persist


class ParseHandler:

    @staticmethod
    async def handle_parse(file: UploadFile) -> dict:
        content = await file.read()
        
        result = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content)
        }
        
        persist.PersistHandler.save(result)
        
        return result

