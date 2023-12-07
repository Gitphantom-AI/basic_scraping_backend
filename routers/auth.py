import os
from fastapi import APIRouter, Depends, HTTPException, Query, security
from pydantic import BaseModel, Field
from server.models import Users, APIKeys
from server.database import SessionLocal
from passlib.context import CryptContext
from starlette import status
from typing import Annotated
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import google.oauth2.credentials
import google_auth_oauthlib.flow

from utils import regex, auth, email, api_key_utils, random_generator, image

from googleapiclient.discovery import build

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

bcrpyt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
user_dependency_without_verification = Annotated[dict, Depends(auth.get_current_user_without_verification)]
user_dependency = Annotated[dict, Depends(auth.get_current_user)]
forget_password_dependency = Annotated[dict, Depends(auth.verify_forget_password_token)]
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

class SavedKey(BaseModel):
    api_key: str

class ResetPasswordRequest(BaseModel):
    username: str
    password: str
    new_password: str

class NewPasswordRequest(BaseModel):
    new_password: str
    
class ForgetPasswordRequest(BaseModel):
    email: str

class NewUsernameRequest(BaseModel):
    new_username: str

class NewEmailRequest(BaseModel):
    new_email: str

class NewAvatarRequest(BaseModel):
    image: str
    image_name: str

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
    
    if not regex.verify_password_schema(create_user_request.password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Password must contain a number, a capital letter, and a small letter without space.')
   
    if not regex.verify_email_schema(create_user_request.email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Please enter a valid email address.')

    user = db.query(Users).filter(Users.username == create_user_request.username).first()
    if user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This username has been used.')
    
    userEmail = db.query(Users).filter(Users.email == create_user_request.email).first()
    
    if userEmail:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This email has been registered.')
    
    otp = random_generator.generateRandomCode()
    
    user_image = image.uploadImage(create_user_request.image_name, create_user_request.image)
    
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
    await get_new_api_key(db, create_user_model)
    token = auth.create_access_token(create_user_model.username, create_user_model.id, timedelta(minutes=180), create_user_model.activated, create_user_model.email)
    email.sendVerificationEmail(otp, create_user_request.email)
    
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
async def login_for_access_token(form_data: Annotated[security.OAuth2PasswordRequestForm, Depends()],
                                 db: db_dependency):
    user = auth.authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
    token = auth.create_access_token(user.username, user.id, timedelta(minutes=180), user.activated, user.email)
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

@router.post("/verify", status_code=status.HTTP_200_OK)
async def verifyCode(user: user_dependency_without_verification, db: db_dependency, verificationCode: str = Query(min_length=6, max_length=100)):
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
async def verifyCode(user: user_dependency_without_verification, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    if user_model.activated:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail='User has been activated.')
    
    if not datetime.utcnow() - (user_model.verification_expires - timedelta(minutes=20)) > timedelta(seconds=60):
        raise HTTPException(status_code=status.HTTP_425_TOO_EARLY, detail='Please wait 60s to get a new code')

    otp = random_generator.generateRandomCode()
    user_model.verification_code = otp
    user_model.verification_expires=datetime.utcnow() + timedelta(minutes=20)
    db.add(user_model)
    db.commit()
    email.sendVerificationEmail(otp, user_model.email)

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
    #print(response)
    userEmail = response["email"]

    # Get user from database with provided email
    user = db.query(Users).filter(Users.email == userEmail).first()
    
    # If not user is found, register a new one
    if user is None:

        otp = random_generator.generateRandomCode()


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
        await get_new_api_key(db, create_user_model)
        token = auth.create_access_token(create_user_model.username, create_user_model.id, timedelta(minutes=180), create_user_model.activated, userEmail)
        email.sendVerificationEmail(otp, create_user_model.email)
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
        token = auth.create_access_token(user.username, user.id, timedelta(minutes=180), user.activated, userEmail)
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

#Disable create API key
#@router.post("/key", response_model=SavedKey)
async def get_new_api_key(db: db_dependency, user: Users):
    length=32
    new_key = random_generator.generateRandomKey(length)
    charge = 1000
    response = await api_key_utils.save_api_key(db, new_key, charge, user)
    #print(response)
    if response["success"]:
        return {
        "api_key": new_key
        }
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Failed to create api key.')
    
@router.put("/reset_password", status_code=status.HTTP_200_OK)
async def reset_password(reset_password_request: ResetPasswordRequest, db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    if user.get('username') != reset_password_request.username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    auth_user = auth.authenticate_user(reset_password_request.username, reset_password_request.password, db)
    if not auth_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    if not regex.verify_password_schema(reset_password_request.new_password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Password must contain a number, a capital letter, and a small letter without space.')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    user_model.hashed_password = bcrpyt_context.hash(reset_password_request.new_password)
    db.add(user_model)
    db.commit()
    return{
        "message": "Success"
    }

@router.post("/forget_password", status_code=status.HTTP_200_OK)
async def forget_password(db: db_dependency, forget_password_request: ForgetPasswordRequest):
    user_email = forget_password_request.email
    print(user_email)
    user_model = db.query(Users).filter(Users.email ==  user_email).first()
    if user_model is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='No user found with this email.')
    if user_model.login_type == 'google':
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail='This email is not registered with a password.')
    client_domain = os.environ['client_domain']
    token = auth.create_forget_password_token(user_model.id, timedelta(minutes=20), user_model.email)
    email.sendResetPasswordEmail(token, user_model.email, client_domain)
    return{
        "message": "Success"
    }

@router.put("/forget_password", status_code=status.HTTP_200_OK)
async def forget_password(db: db_dependency, token: forget_password_dependency, new_password_request: NewPasswordRequest):
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    if not regex.verify_password_schema(new_password_request.new_password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Password must contain a number, a capital letter, and a small letter without space.')
    user_model = db.query(Users).filter(Users.id == token.get('id')).first()
    auth_user = auth.authenticate_user(user_model.username, new_password_request.new_password, db)
    if auth_user:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='New password must not be the same as previous.') 
    user_model.hashed_password = bcrpyt_context.hash(new_password_request.new_password)
    db.add(user_model)
    db.commit()
    return{
        "message": "Success"
    }

@router.put("/username", status_code=status.HTTP_200_OK)
async def change_username(new_username_request: NewUsernameRequest, db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if user_model.username == new_username_request.new_username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='New username must not be the same as previous.') 
    existing_username = db.query(Users).filter(Users.username == new_username_request.new_username).first()
    if existing_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This username has been used.')
    user_model.username = new_username_request.new_username
    db.add(user_model)
    db.commit()
    return{
        "message": "Success"
    }

@router.post("/change_email", status_code=status.HTTP_200_OK)
async def change_email(new_email_request: NewEmailRequest, db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.email == new_email_request.new_email).first()
    if user_model is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='This email has been used.')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    server_domain = os.environ['server_domain']
    token = auth.create_change_email_token(user_model.id, timedelta(minutes=20), user_model.email, new_email_request.new_email)
    email.sendChangeEmailEmail(token, new_email_request.new_email, server_domain)
    return{
        "message": "Success, please verify your new email in 20 minutes."
    }

@router.get("/change_email", status_code=status.HTTP_200_OK)
async def change_email(db: db_dependency, token: str = Query()):
    user = await auth.verify_change_email_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    new_email = user.get('new_email')
    user_model.email = new_email
    db.add(user_model)
    db.commit()
    return{
        "message": "Success"
    }

@router.put("/change_avatar", status_code=status.HTTP_200_OK)
async def change_avatar(db: db_dependency, user: user_dependency, update_avatar_request: NewAvatarRequest):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    user_image = image.uploadImage(update_avatar_request.image_name, update_avatar_request.image)
    user_model.user_image = user_image
    db.add(user_model)
    db.commit()
    return{
        "message": "Success",
        "user_image": user_image
    }

@router.put("/renew_api_key", status_code=status.HTTP_200_OK)
async def renew_api_key(db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    api_key_model = db.query(APIKeys).filter(APIKeys.owner_id == user.get('id')).first()
    if api_key_model is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No API Key Found.')
    length=32
    new_key = random_generator.generateRandomKey(length)
    api_key_model.key = new_key
    db.add(api_key_model)
    db.commit()
    return{
        "message": "Success",
        "api_key": new_key
    }

@router.get("/get_api_key", status_code=status.HTTP_200_OK)
async def get_api_key(db: db_dependency, user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    print(user.get('id'))
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    api_key_model = db.query(APIKeys).filter(APIKeys.owner_id == user.get('id')).first()
    if api_key_model is None:
        await get_new_api_key(db, user_model)
        api_key_model = db.query(APIKeys).filter(APIKeys.owner_id == user.get('id')).first()
    return{
        "message": "Success",
        "api_key": api_key_model.key,
        "charge": api_key_model.charge,
        "renew_date": api_key_model.key_renewal_date,
        "plan": user_model.plan
    }