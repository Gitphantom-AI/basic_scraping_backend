from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import motor.motor_asyncio
import os
from dotenv import load_dotenv



load_dotenv()

SQLALCHEMY_DATABASE_URL = os.environ['database_string']

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

## Motor setup
MONGO_STRING = os.environ['mongodb_string']

MongoClient = motor.motor_asyncio.AsyncIOMotorClient(MONGO_STRING)
