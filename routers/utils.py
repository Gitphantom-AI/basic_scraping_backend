import random
import math
import json
import os
import boto3
import base64
import uuid
import io
from dotenv import load_dotenv

load_dotenv()
 
ACCESS_KEY=os.environ['aws_access_key_id_s3']
SECRET_KEY=os.environ['aws_secret_access_key_s3']
AWS_REGION=os.environ['aws_region']

def generateRandomCode():
    ## storing strings in a list
    digits = [i for i in range(0, 10)]

    ## initializing a string
    random_str = ""

    ## we can generate any lenght of string we want
    for i in range(6):
    ## generating a random index
    ## if we multiply with 10 it will generate a number between 0 and 10 not including 10
    ## multiply the random.random() with length of your base list or str
        index = math.floor(random.random() * 10)

        random_str += str(digits[index])

    ## displaying the random string
    return random_str



# Http api to upload image to S3 and return link for display
def uploadImage(image_name, image_base64):

    try:
        # Random string to avoid crash of object name
        randomString = str(uuid.uuid4())
        bucket_name = os.environ['bucket_name']
       
        image_base64 = image_base64[image_base64.find(",")+1:]
        s3_client = boto3.client("s3", region_name=AWS_REGION, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
        decoded_file = io.BytesIO(base64.b64decode(image_base64))
        s3_client.upload_fileobj(decoded_file, bucket_name, randomString + image_name)
        

        #get object url after upload to s3
        object_url = "https://%s.s3.amazonaws.com/%s" % (bucket_name, randomString + image_name )
        return object_url
    
    except Exception as e: 
        print(e)
        response = {"statusCode": 400, "body": "Invalid Input."}
        return response

# Http api to create a presigned url for images from exiting image link
def getUrl(event, context):
    try:
        bucket_name = os.environ['bucket_name']
        image_obj = json.loads(event['body'])

        # Reform data into image name and bucket url
        bucket_url = "https://%s.s3.amazonaws.com/" % (bucket_name)
        image_name = image_obj['avatorURL'].split("?")[0].replace(bucket_url, "")
        
        # Call the function to create presigned url
        pre_signed_url = create_presigned_url(bucket_name, image_name, 86400)
        response = {"statusCode": 200, "body":  pre_signed_url}
        return response
    except:
        response = {"statusCode": 400, "body": "Invalid Input."}
        return response

# Function to create a presigned url
def create_presigned_url(bucket_name, object_name, expiration=600):
    
    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'), region_name=AWS_REGION, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
    
    response = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_name}, ExpiresIn=expiration)
    
    # The response contains the presigned URL
    return response