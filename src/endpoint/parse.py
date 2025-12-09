from fastapi import APIRouter, File, UploadFile, HTTPException
from src.models.model import ParseResponse
from src.handler.parser import ParseHandler
from src.handler import persist

router = APIRouter()


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
            status="success",
            message=f"PDF file '{result['filename']}' processed successfully. Size: {result['size']} bytes"
        )
    except HTTPException:
        raise
    except Exception as e:
        return ParseResponse(
            status="error",
            
            error=str(e),
            message="Failed to process file"
        )


@router.get("/api/v1/parse", response_model=ParseResponse)
async def list_all():
    data = persist.PersistHandler.get_all()
    return ParseResponse(
        message="Retrieved all items",
        data={"items": data, "count": len(data)}
    )


@router.get("/api/v1/parse/{id}", response_model=ParseResponse)
async def get_by_id(id: int):
    data = persist.PersistHandler.get_by_id(id)
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    return ParseResponse(
        message=f"Retrieved item with id {id}",
        data=data
    )