import time
import json
import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from starlette import status
from typing import  Annotated, Optional
from server.database import MongoClient, SessionLocal
from sqlalchemy.orm import Session
import numpy as np

from utils import api_key_utils, data_access
class TwitterData(BaseModel):
    index: int
    id: Optional[int] = None
    url: Optional[str] = None
    text: Optional[str] = None
    likes: Optional[int] = None
    images: Optional[str] = None
    timestamp: Optional[str] = None

class TwitterModel(BaseModel):
    total_csv_read: int
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
async def get_latest_twitter(db: db_dependency, api_key: api_key_dependency, pageSize: int = Query(), pageNumber: int = Query(),  sortKey: str | None = Query(default=None), searchKey: str | None = Query(default=None), sortDirection: str| None = Query(default="asc")):
    try:
        print(searchKey)
        if searchKey == "" or sortKey == "":
            raise Exception("Invalid input of searchKey or sortKey, please do not enter nothing in query parameter or use URL encoded characters for special characters.")
        initial_lower_bound =  (pageNumber - 1) * pageSize + 1
        lower_bound = initial_lower_bound
        upper_bound = lower_bound + pageSize - 1
        loop = True
        duplicates = pd.DataFrame()
        df_sum  = pd.DataFrame()
        while loop:
            start = time.time()
            last_record, file_names = await data_access.get_files_name(sortKey, searchKey, sortDirection, lower_bound, upper_bound, "twitter")
            end_of_getting_files_name= time.time()
            df, duplicates_length = await data_access.get_csv_record(last_record, lower_bound, upper_bound, 'twitterscrapingbucket', file_names, "twitter/")
            df_sum = pd.concat([df_sum, df], ignore_index=True)
            
            # Identify and drop duplicates, keeping the first occurrence
            duplicated_items = df_sum[df_sum.duplicated(subset=["url"], keep='first')]

            # Drop duplicates from the original DataFrame
            df_sum = df_sum.drop_duplicates(subset=["url"], keep='first')

            if len(duplicated_items.index) == 0:
                loop = False
            else:
                duplicates = pd.concat([duplicates, duplicated_items], ignore_index=True)
                duplicates = duplicates.drop_duplicates(subset=["id"], keep='first')
                # When more than 100 duplicates, skip a large portion to reduce repetitive results
                if duplicates_length > 100:
                    lower_bound = upper_bound + duplicates_length + 1
                    upper_bound = upper_bound + duplicates_length + len(duplicated_items) 
                # If small number, just skip the number of rows of skipped items
                else:
                    lower_bound = upper_bound + 1
                    upper_bound = upper_bound + len(duplicated_items)
                
        # Returns a df with files name containing duplicates for further modification
        files_with_duplicates = duplicates.drop_duplicates(subset=["csv_file"], keep='first')
        print(files_with_duplicates)
        df_sum = await data_access.add_index_column(df_sum, initial_lower_bound)
        df_to_json = df_sum.to_json(orient = "records")
        data = json.loads(df_to_json)
        end_of_getting_csv_files = time.time()
        await api_key_utils.consume_key(db, api_key)

        return {
                "total_csv_read":len(file_names), "total_duration": (end_of_getting_csv_files - start), "reading_mongodb_duration": (end_of_getting_files_name - start), "reading_s3_duration": (end_of_getting_csv_files - end_of_getting_files_name),
                "data": data
                }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
