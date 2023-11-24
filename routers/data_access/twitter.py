import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from starlette import status
from typing import  Annotated, Optional
from server.database import MongoClient, SessionLocal
from sqlalchemy.orm import Session
from .data_access import get_data

from utils import api_key_utils
class TwitterData(BaseModel):
    index: int
    id: Optional[int] = None
    url: Optional[str] = None
    text: Optional[str] = None
    likes: Optional[int] = None
    images: Optional[str] = None
    timestamp: Optional[str] = None

class TwitterModel(BaseModel):
    total_duration: float
    reading_mongodb_duration: float
    reading_s3_duration: float
    data: list[TwitterData]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
api_key_dependency = Annotated[str, Depends(api_key_utils.get_api_key_header)]

router = APIRouter(
    prefix='/twitter',
    tags=['twitter']
)

@router.get("/get_latest_twitter", status_code=status.HTTP_200_OK, response_model=TwitterModel)
async def get_latest_twitter(background_tasks: BackgroundTasks, db: db_dependency, api_key: api_key_dependency, pageSize: int = Query(), pageNumber: int = Query(),  sortKey: str | None = Query(default=None), searchKey: str | None = Query(default=None), sortDirection: str| None = Query(default="asc")):
    try:
        data, start, end_of_getting_csv_files, end_of_getting_files_name = await get_data(searchKey, sortKey, pageSize, pageNumber, sortDirection, "twitter", background_tasks)
        await api_key_utils.consume_key(db, api_key)

        return {
                "total_duration": (end_of_getting_csv_files - start), "reading_mongodb_duration": (end_of_getting_files_name - start), "reading_s3_duration": (end_of_getting_csv_files - end_of_getting_files_name),
                "data": data
                }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
