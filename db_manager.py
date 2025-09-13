from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models.detection import Base, Detection

engine = create_engine("sqlite:///detection.db", echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_detection(db, detection_data):
    detection = Detection(**detection_data)
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection

def get_all_detections(db):
    return db.query(Detection).all()
