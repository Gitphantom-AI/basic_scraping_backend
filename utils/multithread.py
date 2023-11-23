from concurrent.futures import ThreadPoolExecutor


def parallel_multithreading(method, array):

    with ThreadPoolExecutor(max_workers=3) as executor:
        #future_to_key = {executor.submit(download_object, repeat(s3_client), key): key for key in file_names}
        results = executor.map(method, array)
        for result in results:
            yield result
