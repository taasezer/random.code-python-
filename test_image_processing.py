import pytest
from src.utils.image_processor import process_image

def test_process_image_with_valid_image():
    with open("tests/test.jpg", "rb") as f:
        image_bytes = f.read()
    detections = process_image(image_bytes)
    assert isinstance(detections, list)
    assert len(detections) > 0
