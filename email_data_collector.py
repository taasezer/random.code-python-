import argparse
import sys
import requests
import csv
import time
import random
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def format_phone_number(phone):
    """Standartlaştırılmış bir telefon numarası formatı oluşturur."""
    # Sadece sayıları tutuyoruz
    digits = ''.join(filter(str.isdigit, phone))
    
    # ABD formatı kontrol ediliyor
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Format uygun değilse orijinal değerini koruyoruz

def fetch_emails(base_url, email_addresses, headers, proxies, args):
    """Verilen e-posta adresleri için ek veri toplar."""
    all_data = []
    total_emails = len(email_addresses)
    
    print(f"\nE-posta adresleri için ek verileri alıyorum ({total_emails} e-posta)...")
    
    # İstek sayısını sınırla
    max_requests = min(args.max_requests, total_emails)
    emails_to_process = email_addresses[:max_requests]
    
    def fetch_single_email(email):
        # Rastgele gecikme ekleyerek rate limiti aşmayı önleyelim
        time.sleep(random.uniform(1.0, 3.0))
        
        email_url = f"{base_url}emails={email}"
        try:
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    response = requests.get(email_url, headers=headers, proxies=proxies, timeout=10)
                    response.raise_for_status()
                    
                    email_data = response.json()
                    
                    if 'records' in email_data and email_data['records']:
                        print(f"✓ {email} için veri alındı")
                        return email_data['records']
                    else:
                        print(f"✗ {email} için veri bulunamadı")
                        return []
                    
                except (requests.RequestException, json.JSONDecodeError) as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        print(f"⚠ {email} için hata. {wait_time} saniye sonra tekrar denenecek. Hata: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        print(f"✗ {email} için maksimum deneme sayısına ulaşıldı: {str(e)}")
                        return []
        except Exception as e:
            print(f"✗ {email} için beklenmeyen hata: {str(e)}")
            return []
    
    # Paralel isteklerle performansı artıralım
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_email = {executor.submit(fetch_single_email, email): email for email in emails_to_process}
        
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            try:
                data = future.result()
                all_data.extend(data)
            except Exception as e:
                print(f"✗ {email} işlenirken hata oluştu: {str(e)}")
    
    return all_data

def save_to_csv(data, filename):
    """Verileri CSV formatında kaydeder."""
    if not data:
        print("Kaydedilecek veri yok.")
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
                sanitized_record = {k: (v if v is not None else '') for k, v in record.items()}
                writer.writerow(sanitized_record)
        
        print(f"\n✓ Veriler başarıyla kaydedildi: {filename}")
        return True
    
    except Exception as e:
        print(f"\n✗ CSV dosyası kaydedilirken hata: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='İllicit Services kayıtlarını sorgulayan ve verileri toplayan gelişmiş bir araç.')
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
    parser.add_argument('--output_file', type=str, default='output.csv', help='Verilerin kaydedileceği CSV dosyası (varsayılan: output.csv)')
    parser.add_argument('--timeout', type=int, default=30, help='İstek zaman aşımı süresi (saniye, varsayılan: 30)')
    parser.add_argument('--detailed', action='store_true', help='Daha detaylı çıktılar göster')
    parser.add_argument('--no-progress', action='store_true', help='İlerleme çubuğunu gösterme')
    parser.add_argument('--json-output', type=str, help='Ham JSON verisini dosyaya kaydet')

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(1)

    print(f"🔍 İllicit Services Veri Toplama Aracı")
    print(f"======================================")

    # Telefon numarasını formatla
    if args.phone:
        args.phone = format_phone_number(args.phone)

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
            query_params.append(f'{arg_key_map[key]}={value}')
    
    query_string = '&'.join(query_params)

    # Parametre sayısını kontrol et
    num_params = len(query_params)
    if num_params > 5:
        print("⚠ Hata: Hedef URL 5'ten fazla GET parametresi desteklemiyor. Lütfen argüman sayısını azaltın.")
        sys.exit(1)
    
    if num_params == 0:
        print("⚠ Hata: En az bir arama parametresi gerekli.")
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

    try:
        print("\n🔄 Verileri alıyorum...")
        response = requests.get(target_url, headers=headers, proxies=proxies, timeout=args.timeout)
        response.raise_for_status()
        
        # JSON verisini işle
        data = response.json()
        
        if 'records' not in data or not data['records']:
            print("⚠ Hata: Veri bulunamadı veya yanıt formatı beklendiği gibi değil.")
            if args.detailed:
                print(f"Ham yanıt: {data}")
            sys.exit(1)
        
        records = data['records']
        print(f"✓ Toplam {len(records)} kayıt bulundu.")
        
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
        
        # Ek e-posta verileri topla
        additional_records = []
        if email_addresses:
            additional_records = fetch_emails(base_url, email_addresses, headers, proxies, args)
            
            # Tüm kayıtları birleştir
            all_records = records + additional_records
            
            # Tekrarlayan kayıtları kaldır (ID'lere göre)
            unique_records = {}
            for record in all_records:
                if 'id' in record:
                    unique_records[record['id']] = record
                else:
                    # ID yoksa tüm kayıt içeriğini anahtar olarak kullan
                    unique_records[str(sorted(record.items()))] = record
            
            all_records = list(unique_records.values())
            
            print(f"\n✓ Toplam benzersiz kayıt sayısı: {len(all_records)}")
