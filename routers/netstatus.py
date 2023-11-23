from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status
from server.database import SessionLocal
from utils.auth import get_current_user
from typing import Annotated
import requests

router = APIRouter(
    prefix='/netstatus',
    tags=['netstatus']
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class NetStatusTableModel(BaseModel):
    data: str

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.get("/", status_code=status.HTTP_200_OK, response_model=NetStatusTableModel)
async def proxy(user: user_dependency, db: db_dependency):
     if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
     res = requests.get("http://139.180.214.224:8000/metagraph/3") 
     return {"data": res.text}
     