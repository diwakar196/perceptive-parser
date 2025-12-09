from http import HTTPStatus
import logging

from fastapi import APIRouter, File, UploadFile, HTTPException
from src.models.model import ParseResponse
from src.handler.parser import ParseHandler
from src.handler import persist

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/api/v1/parse", response_model=ParseResponse)
async def parse(file: UploadFile = File(...)):
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are allowed"
            )
        
        result = await ParseHandler.handle_parse(file)
        
        return ParseResponse(
            message=f"PDF file processed successfully.",
            data=result
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error while parsing the file:  ={e}")
        return ParseResponse(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            message="Failed to process file"
        )


@router.get("/api/v1/invoice", response_model=ParseResponse)
async def list_all():
    try :
        data = persist.PersistHandler.get_all()
        return ParseResponse(
            message="Retrieved all items",
            data={"items": data, "count": len(data)}
        )
    except Exception as e:
        logger.error(f"Error while listing all items: {e}")
        return ParseResponse(
            status="error",
            message="Failed to list items"
        )


@router.get("/api/v1/invoice/{id}", response_model=ParseResponse)
async def get_by_id(id: int):
    try :
        data = persist.PersistHandler.get_by_id(id)
        if data is None:
            raise HTTPException(status_code=404, detail="Not found")
        return ParseResponse(
            message=f"Retrieved item with id {id}",
            data=data
        )
    except Exception as e:
        logger.error(f"Error while getting item by id: {e}")
        return ParseResponse(
            status="error",
            message="Failed to get item by id"
        )