import time
import json
import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from starlette import status
from typing import  Annotated
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

@router.get("/get_latest_reddit", status_code=status.HTTP_200_OK)
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
                "total csv read":len(file_names), "total duration": (end_of_getting_csv_files - start), "reading mongodb duration": (end_of_getting_files_name - start), "reading S3 duration": (end_of_getting_csv_files - end_of_getting_files_name),
                "data": data
                }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Server Error, please try again.')




