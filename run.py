import os
import sys
import webbrowser

# 1. Sunucuda olmayan tarayıcıyı açma komutunu etkisiz hale getir
webbrowser.open = lambda x: None 

# 2. Port Ayarı (v5 zaten bunu içinden okuyor ama biz garantiye alıyoruz)
os.environ['PORT'] = os.environ.get('PORT', '8080')

# 3. v5.0 Kodunu İçe Aktar
try:
    import trading_bot_v5
except ImportError as e:
    print(f"Hata: 'trading_bot_v5.py' dosyası bulunamadı! Detay: {e}")
    sys.exit(1)

if __name__ == '__main__':
    print("🚀 Trading Bot v5.0 — Railway üzerinde başlatılıyor...")
    # Orijinal dosyadaki main() fonksiyonunu çağırıyoruz
    trading_bot_v5.main()
