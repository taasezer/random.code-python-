from ultralytics import YOLO
import easyocr
import cv2
import numpy as np
from datetime import datetime
from ..models.detection import SessionLocal
from .db_manager import add_detection

model = YOLO("yolov8n.pt")
reader = easyocr.Reader(['en'])

def process_image(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    results = model(img)
    detections = []

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            label = model.names[cls]

            detection_data = {
                "object_name": label,
                "confidence": conf,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "timestamp": datetime.now()
            }
            detections.append(detection_data)

    ocr_results = reader.readtext(img)
    for (bbox, text, prob) in ocr_results:
        (top_left, _, bottom_right, _) = bbox
        top_left = tuple(map(int, top_left))
        bottom_right = tuple(map(int, bottom_right))

        detection_data = {
            "text": text,
            "x1": top_left[0],
            "y1": top_left[1],
            "x2": bottom_right[0],
            "y2": bottom_right[1],
            "timestamp": datetime.now()
        }
        detections.append(detection_data)

    db = SessionLocal()
    for detection in detections:
        add_detection(db, detection)
    db.close()

    return detections
