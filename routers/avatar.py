from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status
from server.database import SessionLocal
from utils.auth import get_current_user_without_verification, Users
from typing import Annotated
from utils.image import get_url

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AvatarModel(BaseModel):
    message: str
    avatar_link: str

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user_without_verification)]


@router.get("/avatar", status_code=status.HTTP_200_OK, response_model=AvatarModel)
async def get_avatar(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    if ".s3.amazonaws.com" in user_model.user_image:
        presigned_url = get_url(user_model.user_image)
        return {
            'message': 'success',
            'avatar_link':presigned_url
        }
    else:
        return {
            'message': 'success',
            'avatar_link':user_model.user_image
        }

