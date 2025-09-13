from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_upload_image():
    with open("tests/test.jpg", "rb") as f:
        response = client.post("/upload/", files={"file": f})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_get_detections():
    response = client.get("/detections/")
    assert response.status_code == 200
    assert isinstance(response.json()["detections"], list)
