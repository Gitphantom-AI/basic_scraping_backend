from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status
from typing import Optional
import boto3
import os
from dotenv import load_dotenv
from server.database import MongoClient
import pandas as pd
import time
import json

load_dotenv()
 
ACCESS_KEY=os.environ['wasabi_access_key_id']
SECRET_KEY=os.environ['wasabi_secret_access_key']
AWS_REGION=os.environ['wasabi_aws-region']

class TwitterRequest(BaseModel):
    searchKey: Optional[str] = None
    sortKey: Optional[str] = None

router = APIRouter(
    prefix='/twitter',
    tags=['twitter']
)

@router.get("/get_latest_twitter", status_code=status.HTTP_200_OK)
async def get_latest_twitter(twitter_request: TwitterRequest, pageSize: int = Query(), pageNumber: int = Query(), sortKey: str = Query):
    start = time.time()
    scraping_collection = MongoClient['scraping']['scraping']
    last_record = 0
    sortKey = twitter_request.sortKey
    searchKey = twitter_request.searchKey
    # Async for doesn't parallelize the iteration, but using a async source to run
    if sortKey is not None and searchKey is not None:
        results = scraping_collection.find({"source_name":"twitter", "search_keys":[searchKey]}).sort(sortKey)
    elif sortKey is not None:
        results = scraping_collection.find({"source_name":"twitter"}).sort(sortKey)
    elif searchKey is not None:
        #print('sort by created at')
        results = scraping_collection.find({"source_name":"twitter", "search_keys":[searchKey]})
    else:
        results = scraping_collection.find({"source_name":"twitter"})
    
    lower_bound = (pageNumber - 1) * pageSize + 1
    upper_bound = lower_bound + pageSize - 1
    
    #print(str(lower_bound))
    #print(str(upper_bound))
    file_names = []
    
    async for cursor in results:

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
            print(cursor)
            file_names.append(cursor["file_name"])
    end1= time.time()
    
    df = get_csv_record(last_record, lower_bound, upper_bound, 'twitterscrapingbucket', file_names, pageNumber)
    data = json.loads(df.to_json(orient = "records"))
    end2 = time.time()
    return {"totalDuration": (start - end2), "mongodDuration": (start - end1), "data": data}

def get_csv_record(last_record: int, lower_bound : int, upper_bound: int, bucket_name, file_names, pageNumber):
    s3_client = boto3.client('s3',
                  endpoint_url='https://s3.us-central-1.wasabisys.com',
                  region_name='us-central-1',
                  aws_access_key_id=ACCESS_KEY,
                  aws_secret_access_key=SECRET_KEY)
    df = pd.DataFrame()
    for file_name in file_names:
        #print(file_name)
        obj = s3_client.get_object(Bucket=bucket_name, Key="twitter/"+file_name)
        initial_df = pd.read_csv(obj['Body'])
        df = pd.concat([df, initial_df], ignore_index=True)

    # Cutting rows that are outside page    
    total_length = len(df.index)
    cut_tail = last_record - upper_bound
    cut_start = total_length - (last_record - lower_bound) - 1
    print(last_record)
    print(total_length)
    df.drop(df.tail(cut_tail).index, inplace = True)
    print(len(df.index))
    df.drop(index=df.index[:cut_start], inplace=True)
    index_column = range(lower_bound, upper_bound + 1)
    
    # Add index column to first column
    print(len(df.index))
    df['index'] = index_column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]
    return df
    