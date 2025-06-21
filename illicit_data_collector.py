import argparse
import sys
import requests
import csv
import time
import random
import json
import sqlite3
import urllib.parse
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# Veritabanı bağlantısı ve tablo oluşturma
def setup_database(db_path="illicit_data.db"):
    """Veritabanı bağlantısını kurarak gerekli tabloları oluşturur."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ana kayıtlar tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email TEXT,
        username TEXT,
        phone TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        source TEXT,
        created_date TEXT,
        raw_data TEXT
    )
    ''')

    # E-posta adresleri tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        email TEXT PRIMARY KEY,
        domain TEXT,
        first_seen TEXT,
        last_checked TEXT,
        valid INTEGER DEFAULT 1
    )
    ''')

    # Arama geçmişi tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        search_date TEXT,
        results_count INTEGER,
        successful INTEGER
    )
    ''')

    conn.commit()
    return conn


def format_phone_number(phone):
    """Standartlaştırılmış bir telefon numarası formatı oluşturur."""
    if not phone:
        return None

    # Sadece sayıları tutuyoruz
    digits = ''.join(filter(str.isdigit, phone))

    # ABD formatı kontrol ediliyor
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Format uygun değilse orijinal değerini koruyoruz


def safe_request(url, headers, proxies=None, timeout=30, max_retries=3):
    """Hata yönetimi ve yeniden deneme mekanizması ile HTTP istekleri yapar."""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt  # Exponential backoff
                print(f"⚠ İstek hatası: {str(e)}. {sleep_time} saniye sonra tekrar deneniyor...")
                time.sleep(sleep_time)
            else:
                print(f"✗ Maksimum deneme sayısına ulaşıldı. Son hata: {str(e)}")
                return None
        except json.JSONDecodeError:
            print(f"✗ API geçersiz JSON yanıtı döndürdü: {url}")
            return None
    return None


def fetch_emails(base_url, email_addresses, headers, proxies, args, conn):
    """Verilen e-posta adresleri için ek veri toplar ve veritabanına kaydeder."""
    all_records = []
    total_emails = len(email_addresses)
    cursor = conn.cursor()

    print(f"\n🔍 E-posta adresleri için ek verileri araştırıyorum ({total_emails} e-posta)...")

    # İstek sayısını sınırla
    max_requests = min(args.max_requests, total_emails)
    emails_to_process = email_addresses[:max_requests]

    if args.detailed:
        print(f"Toplam {len(emails_to_process)}/{total_emails} e-posta işlenecek (max-requests: {args.max_requests})")

    def fetch_single_email(email):
        # E-posta adresini veritabanına kaydet
        try:
            domain = email.split('@')[-1] if '@' in email else ''
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                "INSERT OR IGNORE INTO emails (email, domain, first_seen, last_checked) VALUES (?, ?, ?, ?)",
                (email, domain, now, now)
            )

            cursor.execute(
                "UPDATE emails SET last_checked = ? WHERE email = ?",
                (now, email)
            )
            conn.commit()
        except sqlite3.Error as e:
            if args.detailed:
                print(f"⚠ Veritabanı hatası (e-posta kaydedilirken): {str(e)}")

        # Rate limiti aşmayı önlemek için gecikme
        time.sleep(random.uniform(1.5, 3.5))

        # URL kodlama
        encoded_email = urllib.parse.quote(email)
        email_url = f"{base_url}emails={encoded_email}"

        email_data = safe_request(
            email_url,
            headers,
            proxies,
            args.timeout,
            max_retries=2
        )

        if email_data and 'records' in email_data and email_data['records']:
            records = email_data['records']
            if args.detailed:
                print(f"✓ {email} için {len(records)} kayıt bulundu")

            # Kayıtları veritabanına ekle
            for record in records:
                try:
                    if 'id' in record:
                        record_id = record.get('id', '')

                        cursor.execute(
                            "INSERT OR IGNORE INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                record_id,
                                record.get('firstName', ''),
                                record.get('lastName', ''),
                                email,
                                record.get('username', ''),
                                record.get('phoneNumber', ''),
                                record.get('address', ''),
                                record.get('city', ''),
                                record.get('state', ''),
                                record.get('zipCode', ''),
                                'illicit.services',
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                json.dumps(record)
                            )
                        )
                        conn.commit()
                except sqlite3.Error as e:
                    if args.detailed:
                        print(f"⚠ Veritabanı hatası (kayıt eklenirken): {str(e)}")

            return records
        else:
            if args.detailed and not email_data:
                print(f"✗ {email} için veri alınamadı")
            elif args.detailed:
                print(f"✗ {email} için kayıt bulunamadı")
            return []

    # Paralel isteklerle performansı artıralım
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_email = {executor.submit(fetch_single_email, email): email for email in emails_to_process}

        completed = 0
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            completed += 1

            if not args.no_progress:
                progress = int((completed / len(emails_to_process)) * 20)
                sys.stdout.write('\r')
                sys.stdout.write(
                    f"İlerleme: [{'#' * progress}{' ' * (20 - progress)}] {completed}/{len(emails_to_process)}")
                sys.stdout.flush()

            try:
                data = future.result()
                all_records.extend(data)
            except Exception as e:
                if args.detailed:
                    print(f"\n✗ {email} işlenirken hata: {str(e)}")

    if not args.no_progress:
        print()  # İlerleme çubuğu sonrası yeni satır

    return all_records


def save_to_csv(data, filename):
    """Verileri CSV formatında kaydeder."""
    if not data:
        print("⚠ Kaydedilecek veri bulunamadı.")
        return False

    try:
        # CSV'ye eklenecek alanları belirleyelim
        fields = set()
        for record in data:
            fields.update(record.keys())

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fields))
            writer.writeheader()

            for record in data:
                # None değerleri boş stringlerle değiştirelim
                sanitized_record = {k: ('' if v is None else v) for k, v in record.items()}
                writer.writerow(sanitized_record)

        print(f"✓ Veriler başarıyla CSV'ye kaydedildi: {filename}")
        return True
    except Exception as e:
        print(f"✗ CSV dosyası oluşturulurken hata: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description='İllicit Services veritabanı araştırma ve veri toplama aracı.')
    parser.add_argument('--first-name', help='İsim')
    parser.add_argument('--last-name', help='Soyisim')
    parser.add_argument('--email', help='E-posta adresi')
    parser.add_argument('--username', help='Kullanıcı adı')
    parser.add_argument('--phone', help='Telefon numarası')
    parser.add_argument('--address', help='Adres')
    parser.add_argument('--license-plate', help='Plaka numarası')
    parser.add_argument('--vin', help='VIN')
    parser.add_argument('--city', help='Şehir')
    parser.add_argument('--state', help='Eyalet/Bölge')
    parser.add_argument('--zip', help='Posta kodu')
    parser.add_argument('--max-requests', type=int, default=10, help='Maksimum istek sayısı (varsayılan: 10)')
    parser.add_argument('--proxy', help='Proxy URL (örn: http://proxy.example.com:8080)')
    parser.add_argument('--email_domain', type=str, help='E-postaları domain\'e göre filtrele')
    parser.add_argument('--output_file', type=str, help='Verilerin kaydedileceği CSV dosyası')
    parser.add_argument('--timeout', type=int, default=30, help='İstek zaman aşımı süresi (saniye, varsayılan: 30)')
    parser.add_argument('--detailed', action='store_true', help='Daha detaylı çıktılar göster')
    parser.add_argument('--no-progress', action='store_true', help='İlerleme çubuğunu gösterme')
    parser.add_argument('--json-output', type=str, help='Ham JSON verisini dosyaya kaydet')
    parser.add_argument('--db-file', type=str, default='illicit_data.db',
                        help='Veritabanı dosya yolu (varsayılan: illicit_data.db)')

    args = parser.parse_args()

    # Argüman kontrolü
    valid_args = False
    for arg_name, arg_value in vars(args).items():
        if arg_name in ['first_name', 'last_name', 'email', 'username', 'phone', 'address',
                        'license_plate', 'vin', 'city', 'state', 'zip'] and arg_value:
            valid_args = True
            break

    if not valid_args:
        parser.print_help()
        print("\n⚠ Hata: En az bir arama parametresi belirtmelisiniz.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"  🔍 İLLİCİT SERVİCES VERİ TOPLAMA ARACI")
    print("=" * 50)

    # Veritabanı bağlantısını kur
    try:
        conn = setup_database(args.db_file)
        print(f"✓ Veritabanı bağlantısı kuruldu: {args.db_file}")
    except sqlite3.Error as e:
        print(f"✗ Veritabanı hatası: {str(e)}")
        sys.exit(1)

    # Telefon numarasını formatla
    if args.phone:
        args.phone = format_phone_number(args.phone)

    # Sabit API URL'si
    base_url = 'https://search.illicit.services/records?wt=json&'

    arg_key_map = {
        'first_name': 'firstName',
        'last_name': 'lastName',
        'email': 'emails',
        'username': 'usernames',
        'phone': 'phoneNumbers',
        'address': 'address',
        'license_plate': 'VRN',
        'vin': 'vin',
        'city': 'city',
        'state': 'state',
        'zip': 'zipCode'
    }

    # URL parametrelerini oluştur
    query_params = []
    for key, value in vars(args).items():
        if key in arg_key_map and value:
            encoded_value = urllib.parse.quote(value)
            query_params.append(f'{arg_key_map[key]}={encoded_value}')

    query_string = '&'.join(query_params)

    # Parametre sayısını kontrol et
    num_params = len(query_params)
    if num_params > 5:
        print("⚠ Hata: Hedef URL 5'ten fazla GET parametresi desteklemiyor. Lütfen argüman sayısını azaltın.")
        sys.exit(1)

    target_url = f'{base_url}{query_string}'
    print(f'\n🌐 Oluşturulan URL: {target_url}')

    # HTTP isteği için ayarlar
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,tr;q=0.8',
        'Referer': 'https://search.illicit.services/',
        'DNT': '1',
        'Connection': 'keep-alive'
    }

    proxies = {'http': args.proxy, 'https': args.proxy} if args.proxy else None

    # Arama geçmişine kaydet
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO search_history (query, search_date, results_count, successful) VALUES (?, ?, ?, ?)",
            (query_string, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0)
        )
        search_id = cursor.lastrowid
        conn.commit()
    except sqlite3.Error as e:
        if args.detailed:
            print(f"⚠ Arama geçmişi kaydedilirken veritabanı hatası: {str(e)}")
        search_id = None

    try:
        print("\n🔄 Verileri alıyorum...")
        # Ana sorguyu yap
        data = safe_request(target_url, headers, proxies, args.timeout)

        if not data or 'records' not in data or not data['records']:
            print("⚠ Hata: Veri bulunamadı veya yanıt formatı beklendiği gibi değil.")
            if args.detailed and data:
                print(f"Ham yanıt: {data}")

            # Arama geçmişini güncelle
            if search_id:
                try:
                    cursor.execute(
                        "UPDATE search_history SET successful = 0 WHERE id = ?",
                        (search_id,)
                    )
                    conn.commit()
                except sqlite3.Error:
                    pass

            sys.exit(1)

        records = data['records']
        record_count = len(records)
        print(f"✓ Toplam {record_count} kayıt bulundu.")

        # Arama geçmişini güncelle
        if search_id:
            try:
                cursor.execute(
                    "UPDATE search_history SET results_count = ?, successful = 1 WHERE id = ?",
                    (record_count, search_id)
                )
                conn.commit()
            except sqlite3.Error:
                pass

        # Kayıtları veritabanına ekle
        for record in records:
            try:
                if 'id' in record:
                    record_id = record.get('id', '')

                    # E-posta adreslerini al
                    emails = record.get('emails', [])
                    email = emails[0] if emails and isinstance(emails, list) else ''

                    # Telefon numaralarını al
                    phones = record.get('phoneNumbers', [])
                    phone = phones[0] if phones and isinstance(phones, list) else ''

                    cursor.execute(
                        "INSERT OR IGNORE INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            record_id,
                            record.get('firstName', ''),
                            record.get('lastName', ''),
                            email,
                            record.get('username', ''),
                            phone,
                            record.get('address', ''),
                            record.get('city', ''),
                            record.get('state', ''),
                            record.get('zipCode', ''),
                            'illicit.services',
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            json.dumps(record)
                        )
                    )
                    conn.commit()
            except sqlite3.Error as e:
                if args.detailed:
                    print(f"⚠ Veritabanı hatası (kayıt eklenirken): {str(e)}")

        # E-posta adreslerini topla
        email_addresses = []
        for record in records:
            if 'emails' in record and record['emails']:
                for email in record['emails']:
                    if email and isinstance(email, str):
                        email_addresses.append(email)

        email_addresses = list(set(email_addresses))  # Tekrarları kaldır

        # Domain filtresini uygula
        if args.email_domain:
            email_addresses = [email for email in email_addresses if email.split('@')[-1] == args.email_domain]

        print(f"✓ {len(email_addresses)} benzersiz e-posta adresi bulundu.")

        # Ek e-posta verileri topla
        additional_records = []
        if email_addresses:
            additional_records = fetch_emails(base_url, email_addresses, headers, proxies, args, conn)

            if additional_records:
                print(f"✓ E-posta sorguları ile ek {len(additional_records)} kayıt elde edildi.")

            # CSV çıktı için tüm kayıtları birleştir
            all_records = records + additional_records

            # Tekrarlayan kayıtları kaldır (ID'lere göre)
            unique_records = {}
            for record in all_records:
                if 'id' in record:
                    unique_records[record['id']] = record
                else:
                    # ID yoksa tüm kayıt içeriğini anahtar olarak kullan
                    record_hash = hash(json.dumps(record, sort_keys=True))
                    unique_records[record_hash] = record

            all_records = list(unique_records.values())

            print(f"\n✓ Toplam benzersiz kayıt sayısı: {len(all_records)}")

            # Veritabanı istatistikleri
            try:
                cursor.execute("SELECT COUNT(*) FROM records")
                total_db_records = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM emails")
                total_emails = cursor.fetchone()[0]

                print(f"\n📊 Veritabanı istatistikleri:")
                print(f"   - Toplam kayıt sayısı: {total_db_records}")
                print(f"   - Toplam e-posta adresi: {total_emails}")
            except sqlite3.Error:
                pass

            # CSV dosyasına kaydet
            if args.output_file:
                save_to_csv(all_records, args.output_file)

            # Ham JSON verisini kaydet
            if args.json_output:
                try:
                    with open(args.json_output, 'w', encoding='utf-8') as f:
                        json.dump(all_records, f, indent=2)
                    print(f"✓ Ham JSON verisi kaydedildi: {args.json_output}")
                except Exception as e:
                    print(f"✗ JSON dosyası kaydedilirken hata: {str(e)}")
        else:
            print("⚠ Hiç e-posta adresi bulunamadı.")

    except KeyboardInterrupt:
        print("\n\n🛑 İşlem kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"\n⚠ Beklenmeyen hata: {str(e)}")
        if args.detailed:
            import traceback
            traceback.print_exc()
    finally:
        # Veritabanı bağlantısını kapat
        if conn:
            conn.close()
            print("✓ Veritabanı bağlantısı kapatıldı.")


if __name__ == "__main__":
    try:
        main()
        print("\n✅ İşlem başarıyla tamamlandı.")
    except KeyboardInterrupt:
        print("\n\n🛑 İşlem kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"\n⚠️ Kritik hata: {str(e)}")
        sys.exit(1)