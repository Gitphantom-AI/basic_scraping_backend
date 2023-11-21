from typing import Annotated
from fastapi import FastAPI, Depends
import server.models as models
from server.models import Todos
from server.database import engine, SessionLocal
from sqlalchemy.orm import Session
from routers import todos, auth, avatar, netstatus
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.data_access import reddit, twitter

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
app.include_router(netstatus.router)
app.include_router(reddit.router)
app.include_router(twitter.router)