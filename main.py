from typing import Annotated
from fastapi import FastAPI, Depends
import models
from models import Todos
from database import engine, SessionLocal
from sqlalchemy.orm import Session
from routers import todos, auth, avatar
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#only run when db doesn't exist
models.Base.metadata.create_all(bind=engine)

app.include_router(todos.router)
app.include_router(auth.router)
app.include_router(avatar.router)