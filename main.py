from typing import Annotated
from fastapi import FastAPI, Depends
import server.models as models
from server.database import engine
from routers import auth, avatar, netstatus, data_access
import routers as router
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

app.include_router(router.router)
app.include_router(auth.router)
app.include_router(avatar.router)
app.include_router(netstatus.router)
app.include_router(data_access.redditRouter)
app.include_router(data_access.twitterRouter)