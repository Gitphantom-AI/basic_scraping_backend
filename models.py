from database import Base
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



class Todos(Base):
    __tablename__ = 'todos'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(64))
    description = Column(String(64))
    priority = Column(Integer)
    complete = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"))