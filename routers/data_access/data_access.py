import time
import json
import pandas as pd
from fastapi import BackgroundTasks


from utils import data_access, log_utils

# dev/scraping
COLLECTION_NAME="scraping"

async def get_data(searchKey, sortKey, pageSize, pageNumber, sortDirection, media: str, background_tasks: BackgroundTasks):
    print(searchKey)
    if searchKey == "" or sortKey == "":
        raise Exception("Invalid input of searchKey or sortKey, please do not enter nothing in query parameter or use URL encoded characters for special characters.")
    initial_lower_bound =  (pageNumber - 1) * pageSize + 1
    lower_bound = initial_lower_bound
    upper_bound = lower_bound + pageSize - 1
    loop = True
    duplicates_df = pd.DataFrame()
    df_sum  = pd.DataFrame()
    start_time = time.time()
    end_of_getting_files_name = time.time()
    while loop:
        
        start_get_file = time.time()
        last_record, file_names, file_names_with_no_rows = await data_access.get_files_name(sortKey, searchKey, sortDirection, lower_bound, upper_bound, media, COLLECTION_NAME)
        end_get_file = time.time()
        end_of_getting_files_name += end_get_file - start_get_file
        df, duplicates_length = await data_access.get_csv_record(last_record, lower_bound, upper_bound, media + 'scrapingbucket', file_names, media + "/")
        df_sum = pd.concat([df_sum, df], ignore_index=True)

        # Identify and drop duplicates_df, keeping the first occurrence
        df_sum, duplicated_items = data_access.duplicate_check(df_sum, "url")

        if len(duplicated_items.index) == 0:
            loop = False
        else:
            # If duplicated rows found, save it to duplicates_df
            duplicates_df = pd.concat([duplicates_df, duplicated_items], ignore_index=True)
            
            # When more than 100 duplicates_df, skip a large portion to reduce repetitive results
            if duplicates_length > 100:
                lower_bound = upper_bound + duplicates_length + 1
                upper_bound = upper_bound + duplicates_length + len(duplicated_items) 
            # If small number, just skip the number of rows of skipped items
            else:
                lower_bound = upper_bound + 1
                upper_bound = upper_bound + len(duplicated_items)
            
    # Returns a df with files name containing duplicates_df for further modification
    files_with_duplicates = duplicates_df.drop_duplicates(subset=["csv_file"], keep='first')
    
    df_sum = await data_access.add_index_column(df_sum, initial_lower_bound)
    df_to_json = df_sum.to_json(orient = "records")
    data = json.loads(df_to_json)

    
    background_tasks.add_task(delete_file_with_no_rows, file_names_with_no_rows, media)
    background_tasks.add_task(remove_duplicates, files_with_duplicates, media)
    end_time = time.time()
    return data, start_time, end_time, end_of_getting_files_name

async def remove_duplicates(df: pd.DataFrame, media: str):
    for index, row in df.iterrows():
        file_name = row['csv_file']
        # Remove S3 file
        response = await data_access.remove_duplicates_from_csv(file_name, media + 'scrapingbucket', media + "/")
        # If success, change metadata
        if response["success"] and not response["skip"]:
            row_count = response["row_count"]

             # If updating metadata is unsuccessful, try for 5 times and update error log
            success = False
            failure_count = 0
            while not success:
                print("Modifying csv files...")
                response = await data_access.update_meta_data(file_name, row_count, media, COLLECTION_NAME)
                success = response["success"]
                if failure_count > 5 and not success:
                    log_utils.write_log("Update csv file while failing to update metadata with error: " +  str(response["msg"]) + ". File name: " + str(file_name) + "\n", "error_log.txt")
                    break
                failure_count += 1
            await log_utils.write_log("Successfully updated csv file with meta data, file name: " + str(file_name)+ "\n", "log.txt")
        elif not response["skip"]:
            log_utils.write_log("Failed to upload modified csv file with error: " +  str(response["msg"]) + ". File name: " + str(file_name) + "\n", "error_log.txt")

async def delete_file_with_no_rows(file_names_with_no_rows: [str], media: str):
    for file_name in file_names_with_no_rows:
        response = await data_access.remove_csv(file_name, media + 'scrapingbucket', media + "/")
        # If success, change metadata
        if response["success"]:
             # If updating metadata is unsuccessful, try for 5 times and update error log
            success = False
            failure_count = 0
            while not success:
                print("Deleting zero rows csv files...")
                response = await data_access.delete_meta_data(file_name, media, COLLECTION_NAME)
                success = response["success"]
                if failure_count > 5 and not success:
                    log_utils.write_log("Deleted csv file while failing to update metadata with error: " +  str(response["msg"]) + ". File name: " + str(file_name) + "\n", "error_log.txt")
                    break
                failure_count += 1
            await log_utils.write_log("Successfully deleted csv file and its meta data, file name: " + str(file_name)+ "\n", "log.txt")
        else:
            log_utils.write_log("Failed to delete csv file with error: " +  str(response["msg"]) + ". File name: " + str(file_name) + "\n", "error_log.txt")