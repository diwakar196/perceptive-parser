from http import HTTPStatus
from pydantic import BaseModel, field_validator
from typing import Optional


class ParseRequest(BaseModel):
    filename: str
    content_type: str
    
    @field_validator("content_type")
    @classmethod
    def validate_pdf(cls, v: str) -> str:
        if "application/pdf" not in v:
            raise ValueError("Only PDF files are allowed")
        return v


class ParseResponse(BaseModel):
    status: HTTPStatus = HTTPStatus.OK
    message: str
    data: Optional[dict] = None