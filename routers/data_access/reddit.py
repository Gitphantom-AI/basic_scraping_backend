import time
import json
import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from starlette import status
from typing import  Annotated, Optional
from server.database import MongoClient, SessionLocal
from sqlalchemy.orm import Session

from utils import api_key_utils, data_access

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
api_key_dependency = Annotated[str, Depends(api_key_utils.get_api_key_header)]
# class RedditRequest(BaseModel):
#     searchKey: Optional[str] = None
#     sortKey: Optional[str] = None

router = APIRouter(
    prefix='/reddit',
    tags=['reddit']
)

class RedditData(BaseModel):
    index: int
    id: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
    likes: Optional[int] = None
    dataType: Optional[str] = None
    timestamp: Optional[str] = None
class RedditModel(BaseModel):
    total_csv_read: int
    total_duration: float
    reading_mongodb_duration: float
    reading_s3_duration: float
    data: list[RedditData]

@router.get("/get_latest_reddit", status_code=status.HTTP_200_OK, response_model=RedditModel)
async def get_latest_reddit(db: db_dependency, api_key: api_key_dependency, pageSize: int = Query(), pageNumber: int = Query(),  sortKey: str | None = Query(default=None), searchKey: str | None = Query(default=None), sortDirection: str| None = Query(default="asc")):
    try:
        
        lower_bound = (pageNumber - 1) * pageSize + 1
        upper_bound = lower_bound + pageSize - 1

        start = time.time()
        last_record, file_names = await data_access.get_files_name(sortKey, searchKey, sortDirection, pageNumber, pageSize, "reddit")
        end_of_getting_files_name= time.time()

        df = data_access.get_csv_record(last_record, lower_bound, upper_bound, 'redditscrapingbucket', file_names, pageNumber, "reddit/")
        data = json.loads(df.to_json(orient = "records"))
        end_of_getting_csv_files = time.time()
        await api_key_utils.consume_key(db, api_key)

        return {
                "total_csv_read":len(file_names), "total_duration": (end_of_getting_csv_files - start), "reading_mongodb_duration": (end_of_getting_files_name - start), "reading_s3_duration": (end_of_getting_csv_files - end_of_getting_files_name),
                "data": data
                }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=('Server Error, please try again. ' + str(e)))




