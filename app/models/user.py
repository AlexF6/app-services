from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    password = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    active = Column(Boolean, default=True)
