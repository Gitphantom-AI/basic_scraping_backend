import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
load_dotenv()


def sendVerificationEmail(verificationCode: str, email: str):
    aws_access_key_id = os.environ['aws_access_key_id']
    aws_secret_access_key = os.environ['aws_secret_access_key']
    
    SENDER = "anthonywong.hokhei@gmail.com"
    RECIPIENT = email
    AWS_REGION = "us-east-1"
    SUBJECT = "Activate Your Account"

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = ("Please open email to see the message."
                )
                
    # The HTML body of the email.
    BODY_HTML = '''
    <html>
        <head>
            <style type="text/css">
            body, p, div {{
                font-family: Helvetica, Arial, sans-serif;
                font-size: 14px;
            }}
            a {{
                text-decoration: none;
            }}
            </style>
            <title></title>
        </head>
        <body>
        <center>
            <p>
            Welcome to XXX. To verify your email, please click on the link below:
            </p>
            <p>
            The verification code is: <strong>{code}</strong>
            </p>
            <p>
            <a href="https://your-company.com/signup/email/verify?verificationCode={code}" 
                style="background-color:#ffbe00; color:#000000; display:inline-block; padding:12px 40px 12px 40px; text-align:center; text-decoration:none;" 
                target="_blank">Verify Email Now</a>
            </p>
        </center>
        </body>
    </html>
'''.format(code=verificationCode)     
    CHARSET = "UTF-8"
    client = boto3.client('ses',region_name=AWS_REGION,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

