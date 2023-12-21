from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status
from server.database import SessionLocal
from utils.auth import get_current_user
from typing import Annotated
import requests

router = APIRouter(
    prefix='/overview',
    tags=['overview']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.get("/reddit", status_code=status.HTTP_200_OK, )
async def proxy(user: user_dependency, db: db_dependency):
     if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
     res = requests.get("https://api.taopulse.io:8000/reddit/get_preview_reddit") 
     return {"data": res.text}
     

@router.get("/twitter", status_code=status.HTTP_200_OK)
async def proxy(user: user_dependency, db: db_dependency):
     if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
     res = requests.get("https://api.taopulse.io:8000/twitter/get_preview_twitter") 
     return {"data": res.text}