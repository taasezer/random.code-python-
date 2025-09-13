from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()
engine = create_engine("sqlite:///detection.db", echo=True)

class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    object_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    text = Column(Text, nullable=True)
    x1 = Column(Integer)
    y1 = Column(Integer)
    x2 = Column(Integer)
    y2 = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)
