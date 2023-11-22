import os
import boto3
import time
import json
import pandas as pd

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from starlette import status
from typing import Optional, Annotated
from server.database import MongoClient, SessionLocal
from sqlalchemy.orm import Session

from ..api_key import consume_key, get_api_key_header

from dotenv import load_dotenv
load_dotenv()
 
ACCESS_KEY=os.environ['wasabi_access_key_id']
SECRET_KEY=os.environ['wasabi_secret_access_key']
AWS_REGION=os.environ['wasabi_aws-region']

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
api_key_dependency = Annotated[str, Depends(get_api_key_header)]
# class RedditRequest(BaseModel):
#     searchKey: Optional[str] = None
#     sortKey: Optional[str] = None

router = APIRouter(
    prefix='/reddit',
    tags=['reddit']
)

@router.get("/get_latest_reddit", status_code=status.HTTP_200_OK)
async def get_latest_reddit(db: db_dependency, api_key: api_key_dependency, pageSize: int = Query(), pageNumber: int = Query(),  sortKey: str | None = Query(default=None), searchKey: str | None = Query(default=None), sortDirection: str| None = Query(default="asc")):
    
    start = time.time()
    scraping_collection = MongoClient['scraping']['scraping']
    last_record = 0
    sortDir = 1
    if sortDirection == "desc":
        sortDir = -1
    
    # Filter and sort csv metadata to choose which appropriate csv to fetch
    if sortKey is not None and searchKey is not None:
        results = scraping_collection.find({"source_name":"reddit", "search_keys":[searchKey]}).sort(sortKey, sortDir)
    elif sortKey is not None:
        results = scraping_collection.find({"source_name":"reddit"}).sort(sortKey, sortDir)
    elif searchKey is not None:
        results = scraping_collection.find({"source_name":"reddit", "search_keys":[searchKey]})
    else:
        results = scraping_collection.find({"source_name":"reddit"}).sort("created_at", -1)
    
    # Get files name of required csv of selected page
    lower_bound = (pageNumber - 1) * pageSize + 1
    upper_bound = lower_bound + pageSize - 1
    file_names = []

    # Async for doesn't parallelize the iteration, but using a async source to run

    async for cursor in results:
        print(cursor)
        # skip small data files
        if searchKey is None and cursor["row_count"] < 10:
            continue
        
        first_record = last_record + 1
        last_record = first_record + cursor["row_count"] - 1
        if first_record > upper_bound:
            last_record = first_record - 1
            break
        if last_record < lower_bound or cursor["row_count"] == 0:
            continue
        
        else:
            file_names.append(cursor["file_name"])
    
    end_of_getting_files_name= time.time()
    
    df = get_csv_record(last_record, lower_bound, upper_bound, 'redditscrapingbucket', file_names, pageNumber)
    data = json.loads(df.to_json(orient = "records"))
    end_of_getting_csv_files = time.time()
    await consume_key(db, api_key)
    return {"totalDuration": (end_of_getting_csv_files - start), "mongodDuration": (end_of_getting_files_name - start), "data": data}

def get_csv_record(last_record: int, lower_bound : int, upper_bound: int, bucket_name, file_names, pageNumber):
    s3_client = boto3.client('s3',
                  endpoint_url='https://s3.us-central-1.wasabisys.com',
                  region_name='us-central-1',
                  aws_access_key_id=ACCESS_KEY,
                  aws_secret_access_key=SECRET_KEY)
    
    df = pd.DataFrame()
    for file_name in file_names:
        obj = s3_client.get_object(Bucket=bucket_name, Key="reddit/"+file_name)
        initial_df = pd.read_csv(obj['Body'])
        df = pd.concat([df, initial_df], ignore_index=True)

    # Cutting rows that are outside page    
    total_length = len(df.index)
    cut_tail = last_record - upper_bound
    cut_start = total_length - (last_record - lower_bound) - 1
    df.drop(df.tail(cut_tail).index, inplace = True)
    df.drop(index=df.index[:cut_start], inplace=True)
    index_column = range(lower_bound, upper_bound + 1)
    
    # Add index column to first column
    df['index'] = index_column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]
    return df
    
