from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from .models.detection import Base, engine
from .utils.image_processor import process_image
from .utils.db_manager import get_db, init_db, get_all_detections
from sqlalchemy.orm import Session

init_db()

app = FastAPI(
    title="DroneVisionAI API",
    description="İHA'lar için görüntü işleme ve nesne tanıma API'si",
    version="0.1.0"
)

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        detections = process_image(contents)
        return {"status": "success", "detections": detections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/detections/")
async def read_detections(db: Session = Depends(get_db)):
    detections = get_all_detections(db)
    return {"detections": detections}
