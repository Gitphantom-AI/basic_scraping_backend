from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from datetime import datetime


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(64), unique=True)
    username = Column(String(32), unique=True)
    hashed_password = Column(String(64))
    activated = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(16))
    verification_code = Column(String(6), default="")
    verification_expires = Column(DateTime, default=datetime.now())
    login_type = Column(String(16))
    user_image = Column(String(128))

    created_date = Column(DateTime, default=datetime.now())
    plan = Column(String(4), default="free")
    plan_expires_date = Column(DateTime, default=datetime.now())

class APIKeys(Base):
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(32))
    owner_id = Column(Integer, ForeignKey("users.id"))
    charge = Column(Integer)

    key_renewal_date = Column(DateTime, default=datetime.now())