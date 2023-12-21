import os
import boto3
import base64
import uuid
import io
import base64
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

load_dotenv()
 
ACCESS_KEY=os.environ['wasabi_access_key_id']
SECRET_KEY=os.environ['wasabi_secret_access_key']
AWS_REGION=os.environ['wasabi_aws-region']

session = boto3.session.Session()
s3_client = boto3.client("s3", 
                         endpoint_url='https://s3.us-central-1.wasabisys.com',
                         region_name=AWS_REGION, 
                         aws_access_key_id=ACCESS_KEY, 
                         aws_secret_access_key=SECRET_KEY)


# Http api to upload image to S3 and return link for display
def uploadImage(image_name, image_base64):
    
    # Compress Image
    image_base64 = image_base64[image_base64.find(",")+1:]

    # Get Extension
    split_tup = os.path.splitext(image_name)
    file_extension = split_tup[1].replace(".", "")

    #resized_base64_image = reduce_base64_image_size(image_base64, 256, file_extension)

    # Random string to avoid crash of object name
    randomString = str(uuid.uuid4())
    bucket_name = "imageStorage"
    
    decoded_file = io.BytesIO(base64.b64decode(image_base64))
    s3_client.upload_fileobj(decoded_file, bucket_name, randomString + image_name)
    

    #get object url after upload to s3
    image_name = randomString + image_name
    return image_name
    

# Http api to create a presigned url for images from exiting image link
def  get_url(image_name):
    bucket_name = "imageStorage"
    
    # Call the function to create presigned url
    pre_signed_url = create_presigned_url(bucket_name, image_name, 86400)
    return pre_signed_url

# Function to create a presigned url
def create_presigned_url(bucket_name, object_name, expiration=600):
    
    # Generate a presigned URL for the S3 object
    
    response = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_name}, ExpiresIn=expiration)
    print(response)
    # The response contains the presigned URL
    return response

def reduce_base64_image_size(base64_image, target_width, file_extension):
    # Decode base64-encoded image
    image_data = base64.b64decode(base64_image)

    # Open the image using Pillow (PIL)
    image = Image.open(BytesIO(image_data))

    # Get the original image size
    original_width, original_height = image.size

    # Calculate the aspect ratio
    aspect_ratio = original_width / original_height

    # Calculate the new height based on the target width and original aspect ratio
    new_height = int(target_width / aspect_ratio)

    # Resize the image while maintaining the original aspect ratio
    image = image.resize((target_width, new_height))
    # Convert the image to bytes
    with BytesIO() as output:
        image.save(output, format=file_extension)  # You can change the format if needed
        resized_image_data = output.getvalue()

    # Encode the resized data back to base64
    resized_base64 = base64.b64encode(resized_image_data).decode('utf-8')

    return resized_base64