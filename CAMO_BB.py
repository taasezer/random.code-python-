"""
Kargo Paketleme Video Kayit ve Etiket Bilgi Cikarma Sistemi
- CAM adli kameradan video alir
- Paketleme islemini kaydeder
- Paket etiketinden isim, soyisim, adres bilgilerini OCR ile okur
- Video ve text bilgi dosyasini DATASERVICE klasorune kaydeder

Gereksinimler:
- Python 3.x
- OpenCV (cv2)
- pytesseract
- Tesseract OCR sistem PATH'de olmali

Kullanim:
- Script calistirilir
- CAM adiyle kamera acilir
- Kayda baslamak icin 'r' tusuna basilir
- Kaydi durdurup video + etiket bilgisi kaydetmek icin 'q' tusu kullanilir
- Cikmak icin ESC veya Ctrl+C

Not:
- CAMERA_ADI degiskenini kendi kamera ayarina gore ayarlayin
"""

import cv2
import pytesseract
import os
from datetime import datetime

# Ayarlar
KAMERA_ADI = "CAM"  # Kamera cihaz adi veya eslesen index stringi
VERIYERI_KLASOR = "DATASERVICE"
VIDEO_FPS = 20.0
VIDEO_KODEK = "XVID"
VIDEO_KAYIT_SURESI = 30  # saniye olarak susur (istediginiz gibi ayarlayabilirsiniz)

def kamera_index_bul(kamera_adi):
    """
    Kamera cihaz adi ile eslesen kameranin indexini bulmaya calisir
    OpenCV cihaz adini direkt saglamadigi icin bu yontem.
    Gerektiginde her isletim sistemine gore ozellestirilebilir.
    """
    print("Kamera aranıyor:", kamera_adi)
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"Kamera index {i} aktif")
                cap.release()
                return i
            cap.release()
    print("Kamera bulunamadi, varsayilan 0 kullaniliyor")
    return 0

def klasor_varsa_olustur(yol):
    if not os.path.exists(yol):
        os.makedirs(yol)

def bilgi_txt_kaydet(klasor_yolu, isim, soyisim, adres, tarih_str):
    dosya_adi = os.path.join(klasor_yolu, f"{isim}_{soyisim}_{tarih_str}.txt")
    with open(dosya_adi, 'w', encoding='utf-8') as f:
        f.write(f"Isim: {isim}\n")
        f.write(f"Soyisim: {soyisim}\n")
        f.write(f"Adres: {adres}\n")
        f.write(f"Tarih: {tarih_str}\n")
    print(f"Bilgi kaydedildi: {dosya_adi}")

def etiket_metni_coz(ocr_metin):
    """
    OCR'den gelen metni isleyip isim, soyisim, adres bilgilerini cekmeye calisir
    Basit kural tabanli ayristirma. Gercek etiket formati degisebilir, uyarlayin.
    """
    satirlar = [satir.strip() for satir in ocr_metin.split('\n') if satir.strip()]
    isim = soyisim = adres = "BILINMIYOR"
    for satir in satirlar:
        kucuk = satir.lower()
        if "isim" in kucuk and isim == "BILINMIYOR":
            isim = satir.split(":")[-1].strip()
        elif "soyisim" in kucuk and soyisim == "BILINMIYOR":
            soyisim = satir.split(":")[-1].strip()
        elif "adres" in kucuk and adres == "BILINMIYOR":
            adres = satir.split(":")[-1].strip()
    return isim, soyisim, adres

def main():
    klasor_varsa_olustur(VERIYERI_KLASOR)

    kamera_indeks = kamera_index_bul(KAMERA_ADI)
    cap = cv2.VideoCapture(kamera_indeks)
    if not cap.isOpened():
        print("Kamera acilamadi. Cikis yapiliyor.")
        return

    print("Kayida baslamak icin 'r' tusuna basiniz.")
    print("Kaydi durdurup kaydetmek icin 'q' tusuna basiniz.")
    print("Cikmak icin ESC'e basin veya Ctrl+C yapin.")

    kayit_yapiliyor = False
    video_cikisi = None
    baslangic_zamani = None
    kaydedilen_kare_sayisi = 0
    max_kare_sayisi = int(VIDEO_FPS * VIDEO_KAYIT_SURESI)
    son_kare = None

    while True:
        ret, kare = cap.read()
        if not ret:
            print("Kare alinamadi.")
            break

        # Canli goruntu gosterimi
        cv2.imshow("Paketleme Kamerasi - Kayit icin r basin", kare)

        tus = cv2.waitKey(1) & 0xFF

        if tus == 27:  # ESC tusu
            print("Cikis yapiliyor...")
            break

        if not kayit_yapiliyor and tus == ord('r'):
            # Kayit baslat
            tarih_saat = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_dosya = os.path.join(VERIYERI_KLASOR, f"paketleme_{tarih_saat}.avi")
            fourcc = cv2.VideoWriter_fourcc(*VIDEO_KODEK)
            yukseklik, genislik = kare.shape[:2]
            video_cikisi = cv2.VideoWriter(video_dosya, fourcc, VIDEO_FPS, (genislik, yukseklik))
            kayit_yapiliyor = True
            baslangic_zamani = datetime.now()
            kaydedilen_kare_sayisi = 0
            print(f"Kayit basladi: {video_dosya}")

        if kayit_yapiliyor:
            video_cikisi.write(kare)
            kaydedilen_kare_sayisi += 1
            son_kare = kare.copy()

            if kaydedilen_kare_sayisi >= max_kare_sayisi:
                print("Maks sure doldu, kayit durduruluyor...")
                kayit_yapiliyor = False
                video_cikisi.release()
                video_cikisi = None

                if son_kare is not None:
                    print("Etiket bilgisi cikartiliyor...")
                    gri = cv2.cvtColor(son_kare, cv2.COLOR_BGR2GRAY)
                    _, esik = cv2.threshold(gri, 150, 255, cv2.THRESH_BINARY)
                    ocr_metin = pytesseract.image_to_string(esik, lang='tur')  # dil 'tur' olabilir

                    print("OCR Metin:")
                    print(ocr_metin)

                    isim, soyisim, adres = etiket_metni_coz(ocr_metin)

                    tarih_str = baslangic_zamani.strftime("%Y%m%d_%H%M%S")
                    yeni_video_adi = os.path.join(VERIYERI_KLASOR, f"{isim}_{soyisim}_{tarih_str}.avi")
                    os.rename(video_dosya, yeni_video_adi)
                    print(f"Video kaydedildi: {yeni_video_adi}")

                    bilgi_txt_kaydet(VERIYERI_KLASOR, isim, soyisim, adres, tarih_str)

        if kayit_yapiliyor and tus == ord('q'):
            print("Kayit elle durduruldu.")
            kayit_yapiliyor = False
            video_cikisi.release()
            video_cikisi = None

            if son_kare is not None:
                print("Etiket bilgisi cikartiliyor...")
                gri = cv2.cvtColor(son_kare, cv2.COLOR_BGR2GRAY)
                _, esik = cv2.threshold(gri, 150, 255, cv2.THRESH_BINARY)
                ocr_metin = pytesseract.image_to_string(esik, lang='tur')

                print("OCR Metin:")
                print(ocr_metin)

                isim, soyisim, adres = etiket_metni_coz(ocr_metin)

                tarih_str = baslangic_zamani.strftime("%Y%m%d_%H%M%S")
                yeni_video_adi = os.path.join(VERIYERI_KLASOR, f"{isim}_{soyisim}_{tarih_str}.avi")
                os.rename(video_dosya, yeni_video_adi)
                print(f"Video kaydedildi: {yeni_video_adi}")

                bilgi_txt_kaydet(VERIYERI_KLASOR, isim, soyisim, adres, tarih_str)

    cap.release()
    if video_cikisi is not None:
        video_cikisi.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

