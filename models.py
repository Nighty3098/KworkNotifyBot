from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProcessedProject(Base):
    __tablename__ = "processed_projects"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(100), unique=True, nullable=False)
    title = Column(String(500))
    price = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MonitoringSettings(Base):
    __tablename__ = "monitoring_settings"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    is_active = Column(Boolean, default=False)
    last_check = Column(DateTime(timezone=True))
    check_interval = Column(Integer, default=120)  # seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
