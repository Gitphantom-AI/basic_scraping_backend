import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from starlette import status
from typing import  Annotated, Optional
from server.database import SessionLocal
from sqlalchemy.orm import Session

from utils import api_key_utils

api_key_dependency = Annotated[str, Depends(api_key_utils.get_api_key_header)]

router = APIRouter(
    prefix='/api_key',
    tags=['api_key']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/verify_key", status_code=status.HTTP_200_OK)
async def get_latest_twitter(db: db_dependency, api_key: api_key_dependency):
    try:
        
        await api_key_utils.consume_key(db, api_key)
        return {
                "response": "ok"
                }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
