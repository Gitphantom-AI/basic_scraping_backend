import json
import os
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from models import Users
from passlib.context import CryptContext
from starlette import status
from typing import Annotated
from sqlalchemy.orm import Session
from database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import timedelta, datetime
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail
from .utils import generateRandomCode, uploadImage
import google.oauth2.credentials
import google_auth_oauthlib.flow
import re

from googleapiclient.discovery import build


load_dotenv()

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

SECRET_KEY = os.environ['jwt_secret_key']
ALGORITHM = 'HS256'


oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')
bcrpyt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

class CreateUserRequest(BaseModel):
    username: str = Field(min_length=6)
    email: str
    password: str
    role: str
    image: str
    image_name: str

class GoogleLoginRequest(BaseModel):
    code: str
    redirect_uri: str

class UserData(BaseModel):
    id: int
    username: str
    email: str
    role: str
    activated: bool
    user_image: str
    login_type: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserData
    

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/")
async def get_user():
    return {'user':'authenticated'}

# Signup function
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Token)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):

    regex = re.search('^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])[a-zA-Z0-9!@#$%^&*]{8,}$',  create_user_request.password)
    if not regex:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Password must contain a number, a capital letter, and a small letter without space.')

    regex = re.search('^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$',  create_user_request.email)
    if not regex:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Please enter a valid email address.')

    user = db.query(Users).filter(Users.username == create_user_request.username).first()
    if user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This username has been used.')
    
    userEmail = db.query(Users).filter(Users.email == create_user_request.email).first()
    
    if userEmail:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This email has been registered.')
    
    
    
    
    otp = generateRandomCode()
    
    user_image = uploadImage(create_user_request.image_name, create_user_request.image)
    
    create_user_model = Users(
        email=create_user_request.email,
        username=create_user_request.username,
        role=create_user_request.role,
        hashed_password=bcrpyt_context.hash(create_user_request.password),
        is_active=True,
        activated=False,
        verification_code=otp,
        verification_expires=datetime.utcnow() + timedelta(minutes=20),
        login_type="password",
        user_image=user_image
    )
    db.add(create_user_model)
    db.commit()
    token = create_access_token(create_user_model.username, create_user_model.id, timedelta(minutes=20), create_user_model.activated, create_user_model.email)
    sendVerificationEmail(otp, create_user_request.email)
    
    return {
        'access_token': token, 
        'token_type':'bearer', 
        'user': {
            "id": create_user_model.id,
            "username":create_user_model.username,
            "email":create_user_model.email,
            "role":create_user_model.role,
            "activated": False,
            "user_image": create_user_model.user_image,
            "login_type": create_user_model.login_type
        }
    }
    

@router.post("/token", status_code=status.HTTP_200_OK, response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
    token = create_access_token(user.username, user.id, timedelta(minutes=20), user.activated, user.email)
    return {
            'access_token': token, 
            'token_type':'bearer', 
            'user': {
            "id":user.id,
            "username":user.username,
            "email":user.email,
            "role":user.role,
            "activated":user.activated,
            "user_image": user.user_image,
            "login_type": user.login_type
        }}

def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrpyt_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(username: str, user_id: int, expires_delta: timedelta, activated: bool, email: str):
    encode = {
        'sub': username,
        'id': user_id,
        'activated': activated,
        'email': email
    }
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp':expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

# Check jwt to validate user
async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        activated: bool = payload.get('activated')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        if not activated:
            raise HTTPException(status_code=status.HTTP_423_LOCKED,
                                detail='Please verify your email.')
        return {'username': username, 'id': user_id }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')

async def get_current_user_without_verification(token: Annotated[str, Depends(oauth2_bearer)]):    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'username': username, 'id': user_id }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
    
## Not useful until sendgrid account activated

# def sendVerificationEmail():
#     message = Mail(
#     from_email='anthonywong.hokhei@gmail.com',
#     to_emails='wong95216@gmail.com',
#     subject='Sending with Twilio SendGrid is Fun',
#     html_content='<html> <head> <style type="text/css"> body, p, div { font-family: Helvetica, Arial, sans-serif; font-size: 14px; } a { text-decoration: none; } </style> <title></title> </head> <body> <center> <p> Example 1 - just the code (no localization in the message): </p> <p> The verification code is: <strong>{{twilio_code}}</strong> </p> <p> Example 2 - use the code in a clickable link to trigger a verification check: </p> <p> <a href="https://your-company.com/signup/email/verify?token={{twilio_code}}" style="background-color:#ffbe00; color:#000000; display:inline-block; padding:12px 40px 12px 40px; text-align:center; text-decoration:none;" target="_blank">Verify Email Now</a> </p> <p> Example 3 - entire localized message and code: </p> <p> <strong>{{twilio_message}}</strong> </p> <p><a href="https://sendgrid.com/blog/open-source-transactional-email-templates/">Check out more templates</a></p> <span style="font-size: 10px;"><a href=".">Email preferences</a></span> </center> </body></html>')
#     try:
#         sg = SendGridAPIClient("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")
#         response = sg.send(message)
#         print(response.status_code)
#         print(response.body)
#         print(response.headers)
#     except Exception as e:
#         return e

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


user_dependency = Annotated[dict, Depends(get_current_user_without_verification)]

@router.post("/verify", status_code=status.HTTP_200_OK)
async def verifyCode(user: user_dependency, db: db_dependency, verificationCode: str = Query(min_length=6, max_length=100)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    if user_model.activated:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='User has been activated.')
    if not user_model.verification_code == verificationCode:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Verification Code is not correct.')
    if not user_model.verification_expires > datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='Verification Code Expires.')
    
    user_model.activated = True
    user_model.verification_code = ""
    db.add(user_model)
    db.commit()
    return { 'message': 'success', 'details':'Your account has be activated.'}
    
@router.post("/resend", status_code=status.HTTP_200_OK)
async def verifyCode(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    if user_model.activated:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='User has been activated.')
    
    if not datetime.utcnow() - (user_model.verification_expires - timedelta(minutes=20)) > timedelta(seconds=60):
        raise HTTPException(status_code=status.HTTP_425_TOO_EARLY, detail='Please wait 60s to get a new code')

    otp = generateRandomCode()
    user_model.verification_code = otp
    user_model.verification_expires=datetime.utcnow() + timedelta(minutes=20)
    db.add(user_model)
    db.commit()
    sendVerificationEmail(otp, user_model.email)

@router.post("/register-google", response_model=Token)
async def googleLogin(request_code: GoogleLoginRequest, db: db_dependency):

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    os.path.dirname(__file__) + '/client_secret.json',
    scopes=['openid', "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"],
    redirect_uri=request_code.redirect_uri)

    # Get token with provided code
    flow.fetch_token(code=request_code.code)
    credentials = flow.credentials
    
    # Use google client to get user profile and email
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    response = user_info_service.userinfo().get().execute()
    print(response)
    userEmail = response["email"]

    # Get user from database with provided email
    user = db.query(Users).filter(Users.email == userEmail).first()
    
    # If not user is found, register a new one
    if user is None:

        otp = generateRandomCode()


        create_user_model = Users(
        email=userEmail,
        username=userEmail,
        role="user",
        hashed_password="never correct",
        is_active=True,
        activated=False,
        verification_code=otp,
        verification_expires=datetime.utcnow() + timedelta(minutes=20),
        login_type="google",
        user_image=response['picture']
        )
        db.add(create_user_model)
        db.commit()
        token = create_access_token(create_user_model.username, create_user_model.id, timedelta(minutes=20), create_user_model.activated, userEmail)
        sendVerificationEmail(otp, create_user_model.email)
        return {
                'access_token': token, 
                'token_type':'bearer', 
                'user': {
                "id": create_user_model.id,
                "username":create_user_model.username,
                "email":create_user_model.email,
                "role":create_user_model.role,
                "activated":create_user_model.activated,
                "user_image": create_user_model.user_image,
                "login_type":create_user_model.login_type,
            }}
    
    # If login type is google, login user with jwt token
    if user.login_type == "google":
        # Create jwt token
        token = create_access_token(user.username, user.id, timedelta(minutes=20), user.activated, userEmail)
        return {
                'access_token': token, 
                'token_type':'bearer', 
                'user': {
                "id": user.id,
                "username":user.username,
                "email":user.email,
                "role":user.role,
                "activated":user.activated,
                "user_image": user.user_image,
                "login_type": user.login_type
            }}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='This user is not registered with Google login.')
