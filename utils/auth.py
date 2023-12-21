import os
from fastapi import  Depends, HTTPException
from server.models import Users
from starlette import status
from typing import Annotated
from jose import JWTError, jwt
from datetime import timedelta, datetime
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from server.database import SessionLocal
from sqlalchemy.orm import Session
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.environ['jwt_secret_key']
ALGORITHM = 'HS256'
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')
bcrpyt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        user = db.query(Users).filter(Users.email == username).first()
    if not user:
        return False
    if user.hashed_password == 'never correct':
        return False
    if not bcrpyt_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(username: str, user_id: int, expires_delta: timedelta, activated: bool, email: str):
    encode = {
        'username': username,
        'id': user_id,
        'activated': activated,
        'email': email
    }
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp':expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

# Check jwt to validate user
async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('username')
        user_id: int = payload.get('id')
        user = db.query(Users).filter(Users.id == user_id).first()
        activated: bool = user.activated
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
        username: str = payload.get('username')
        user_id: int = payload.get('id')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'username': username, 'id': user_id }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
    
def create_forget_password_token(user_id: int, expires_delta: timedelta, email: str):
    encode = {
        'id': user_id,
        'email': email,
        'forget_password': True
    }
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp':expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_forget_password_token(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        user_id: int = payload.get('id')
        # Prevent using change email token to reset password
        change_email: bool = payload.get('change_email')
        if change_email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Token is not for resetting password.')
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'id': user_id }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
    
def create_change_email_token(user_id: int, expires_delta: timedelta, email: str, new_email: str):
    encode = {
        'id': user_id,
        'email': email,
        'new_email': new_email,
        'change_email': True
    }
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp':expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_change_email_token(token: str):

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        change_email: bool = payload.get('change_email')
        new_email: str = payload.get('new_email')
        user_id: int = payload.get('id')
        if not change_email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Token is not for changing emails.')
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')
        return {'id': user_id, 'new_email': new_email }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user.')