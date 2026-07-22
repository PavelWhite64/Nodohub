from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=True)  # новое поле, хранится с @
    pages = relationship("Page", back_populates="user")

class Page(Base):
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String, unique=True, nullable=False)
    role = Column(String, default="")
    bio = Column(Text, default="")
    links = Column(Text, default="[]")
    theme = Column(String, default="minimal")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="pages")