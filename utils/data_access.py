import os
import boto3
from pymongo.collation import Collation
import pandas as pd

from server.database import MongoClient
from sqlalchemy.orm import Session

from utils.multithread import parallel_multithreading
from utils.timer import timing

from dotenv import load_dotenv
load_dotenv()
 
ACCESS_KEY=os.environ['wasabi_access_key_id']
SECRET_KEY=os.environ['wasabi_secret_access_key']
AWS_REGION=os.environ['wasabi_aws-region']

session = boto3.session.Session()
s3_client = session.client('s3',
                endpoint_url='https://s3.us-central-1.wasabisys.com',
                region_name='us-central-1',
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY)

@timing
async def get_files_name(sortKey, searchKey, sortDirection, lower_bound, upper_bound, source_name, collection):
    try:
        mongo_collection = MongoClient['scraping'][collection]
        first_row_number_of_file = 0
        last_row_number_of_file = 0
        sortDir = 1
        if sortDirection == "desc":
            sortDir = -1
        # Filter and sort csv metadata to choose which appropriate csv to fetch
        if sortKey is not None and searchKey is not None:
            results = mongo_collection.find({"source_name":source_name, "search_keys":[searchKey]}).collation(Collation(locale='en_US', strength=1)).sort(sortKey, sortDir)
        elif sortKey is not None:
            results = mongo_collection.find({"source_name":source_name }).sort(sortKey, sortDir)
        elif searchKey is not None:
            results = mongo_collection.find({"source_name":source_name, "search_keys":[searchKey]}).collation(Collation(locale='en_US', strength=1))
        else:
            results = mongo_collection.find({"source_name":source_name }).sort("created_at", -1)
        
        # Get files name of required csv of selected page
        
        file_names = []
        file_names_with_no_rows = []

        # Async for doesn't parallelize the iteration, but using a async source to run

        async for cursor in results:
            #print(cursor)
            # skip small data files / 0 row files
            if int(cursor["row_count"]) == 0:
                file_names_with_no_rows.append(cursor["file_name"])
                continue
            if searchKey is None and int(cursor["row_count"]) <= 0:
                continue
            
            first_row_number_of_file = last_row_number_of_file + 1
            last_row_number_of_file = first_row_number_of_file + int(cursor["row_count"]) - 1
            if first_row_number_of_file > upper_bound:
                last_row_number_of_file = first_row_number_of_file - 1
                break
            if last_row_number_of_file < lower_bound:
                continue
            
            else:
                file_names.append(cursor["file_name"])
        #print(file_names)
        return last_row_number_of_file, file_names, file_names_with_no_rows
    except Exception as e:
        print("Error: fail to fetch data from Mongodb database.")
        print(e)
        raise Exception("Error: fail to fetch data from Mongodb database. Message: " + str(e))

@timing
async def get_csv_record(last_row_number_of_file: int, lower_bound : int, upper_bound: int, bucket_name, file_names, prefix):
    try:
        df = pd.DataFrame()
        
        # Define Method for each csv file
        def download_object(key):
            obj = s3_client.get_object(Bucket=bucket_name, Key=prefix + key)
            df = pd.read_csv(obj['Body'])
            
            df['csv_file'] = key
            return df
        
        for result in parallel_multithreading(download_object, file_names):
            df = pd.concat([df, result], ignore_index=True)
        
        # Get the length of duplicate in file only
        duplicates = df[df.duplicated(subset=["url"], keep='first')]
        duplicates_length = len(duplicates.index)
        

        # Cut the irrelevant rows for response
        total_length = len(df.index)
        cut_tail = max(last_row_number_of_file - upper_bound, 0)
        df.drop(df.tail(cut_tail).index, inplace = True)
        cut_start = max(total_length - (last_row_number_of_file - lower_bound) - 1, 0)
        df.drop(index=df.index[:cut_start], inplace=True)
        
        #df = add_index_column(df, lower_bound)
        return df, duplicates_length
    except Exception as e:
        print("Error: fail to get csv files from Wasabi bucket.")
        raise Exception("Error: fail to get csv files from Wasabi bucket. Message: " + str(e))

async def add_index_column(df, lower_bound):
    # Add index column to first column
    current_df_length = len(df.index)
    index_column = range(lower_bound, lower_bound + current_df_length)
    df['index'] = index_column

    # Change last column to first
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]
    return df

def duplicate_check(df:pd.DataFrame, subset: str):
    # Identify and drop duplicates, keeping the first occurrence
    
    duplicated_items = df[df.duplicated(subset=[subset], keep='first')]

    # Drop duplicates from the original DataFrame
    df = df.drop_duplicates(subset=[subset], keep='first')

    return df, duplicated_items

async def remove_duplicates_from_csv(file_name: str, bucket_name: str, prefix):
    # get file from s3
    obj = s3_client.get_object(Bucket=bucket_name, Key=prefix + file_name)
    df = pd.read_csv(obj['Body'])

    original_length = len(df)

    # Get unique data set from 
    df, duplicated_items = duplicate_check(df, "url")
    
    
    # If nothing changed, skip
    if(len(df) == original_length):
        print("skip updating csv since no rows changed.")
        return {"success": True, "row_count": len(df), "skip": True}
    try:
        print("write to csv")
        df.to_csv("tmp/" + file_name, index=False)
        s3_client.upload_file(Key=prefix + file_name, Bucket=bucket_name, Filename="tmp/" + file_name)
        await os.remove("tmp/" + file_name)
        return {"success": True, "row_count": len(df), "skip": False}
    except Exception as e:
        print(e)
        {"success": False, "msg": e}

async def update_meta_data(file_name,  row_count, media, collection):
    mongo_collection = MongoClient['scraping'][collection]
    try:
        mongo_collection.update_one({"file_name": file_name, "source_name": media}, { "$set": { "row_count": row_count } })
        return {"success": True }
    except Exception as e:
        print(e)
        {"success": False, "msg": e}

async def remove_csv(file_name: str, bucket_name: str, prefix):
    # get file from s3
    try:
        obj = s3_client.delete_object(Bucket=bucket_name, Key=prefix + file_name)
        return {"success": True }
    except Exception as e:
        print(e)
        {"success": False, "msg": e}

async def delete_meta_data(file_name, media, collection):
    mongo_collection = MongoClient['scraping'][collection]
    try:
        mongo_collection.delete_one({"file_name": file_name, "source_name": media})
        return {"success": True }
    except Exception as e:
        print(e)
        {"success": False, "msg": e}