import cv2
import pytesseract
import pyodbc
from datetime import datetime
import logging

# Logging yapılandırma
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kamera bağlantısı
def initialize_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Kamera açılamadı!")
        raise IOError("Kamera açılamadı!")
    return cap

# SQL Server bağlantı dizesi
def get_db_connection():
    conn_str = (
        "Driver={SQL Server};"
        "Server=your_server_name;"
        "Database=CargoTracking;"
        "UID=your_username;"
        "PWD=your_password;"
    )
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        logger.error(f"Veri tabanı bağlantı hatası: {e}")
        raise

def save_person_info_db(name, surname, address):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO PersonInfo (Name, Surname, Address, Timestamp) VALUES (?, ?, ?, ?)"
        cursor.execute(query, (name, surname, address, datetime.now()))
        conn.commit()
        logger.info("Kişi bilgileri veri tabanına kaydedildi.")
    except Exception as e:
        logger.error(f"Veri tabanına kaydetme hatası: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def read_label_info(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray)
    return text

def main():
    try:
        cap = initialize_camera()
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Kamera görüntüsü alınamadı!")
                break

            cv2.imshow('Kamera Görüntüsü', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                label_info = read_label_info(frame)
                name, surname, address = "Ad", "Soyad", "Adres"
                save_person_info_db(name, surname, address)
                break
    except Exception as e:
        logger.error(f"Ana işlem hatası: {e}")
    finally:
        if 'cap' in locals():
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
