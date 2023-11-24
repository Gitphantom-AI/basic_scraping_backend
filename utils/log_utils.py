# Example for background tasks
def write_log(message: str, log_file: str):
    with open("log/" + log_file, mode="a") as log:
        log.write(message)