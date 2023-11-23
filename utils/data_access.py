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
async def get_files_name(sortKey, searchKey, sortDirection, lower_bound, upper_bound, source_name):
    try:
        scraping_collection = MongoClient['scraping']['scraping']
        first_row_number_of_file = 0
        last_row_number_of_file = 0
        sortDir = 1
        if sortDirection == "desc":
            sortDir = -1
        # Filter and sort csv metadata to choose which appropriate csv to fetch
        if sortKey is not None and searchKey is not None:
            results = scraping_collection.find({"source_name":source_name, "search_keys":[searchKey]}).collation(Collation(locale='en_US', strength=1)).sort(sortKey, sortDir)
        elif sortKey is not None:
            results = scraping_collection.find({"source_name":source_name }).sort(sortKey, sortDir)
        elif searchKey is not None:
            results = scraping_collection.find({"source_name":source_name, "search_keys":[searchKey]}).collation(Collation(locale='en_US', strength=1))
        else:
            results = scraping_collection.find({"source_name":source_name }).sort("created_at", -1)
        
        # Get files name of required csv of selected page
        
        file_names = []

        # Async for doesn't parallelize the iteration, but using a async source to run

        async for cursor in results:
            #print(cursor)
            # skip small data files
            if searchKey is None and cursor["row_count"] < 10:
                continue
            
            first_row_number_of_file = last_row_number_of_file + 1
            last_row_number_of_file = first_row_number_of_file + int(cursor["row_count"]) - 1
            if first_row_number_of_file > upper_bound:
                last_row_number_of_file = first_row_number_of_file - 1
                break
            if last_row_number_of_file < lower_bound or int(cursor["row_count"]) == 0:
                continue
            
            else:
                file_names.append(cursor["file_name"])
        return last_row_number_of_file, file_names
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

        # Identify and drop duplicates, keeping the first occurrence
        duplicates = df[df.duplicated(subset=["url"], keep='first')]
        duplicates_length = len(duplicates.index)
        total_length = len(df.index)
        cut_tail = last_row_number_of_file - upper_bound
        cut_start = total_length - (last_row_number_of_file - lower_bound) - 1
        df.drop(df.tail(cut_tail).index, inplace = True)
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