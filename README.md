# YFinance Bot 🤖💰

Maaşını, bütçeni ve yatırımlarını yöneten; **BIST + ABD + Kripto** piyasalarını
canlı takip edip kısa vadeli al/sat sinyalleri üreten kişisel Telegram botu.
Üstelik artık **otonom kişisel finans asistanı** olarak da çalışıyor: seni
yönlendirir, hatırlatır, sorular sorar ve yatırım bilgin olmasa bile sana yol
gösterir.

> ⚠️ **Önemli uyarı:** Bu bot **yatırım tavsiyesi vermez**. Ürettiği tüm
> sinyaller yalnızca matematiksel teknik göstergelerdir (RSI, MACD, Bollinger...).
> Kısa vadeli işlemler **yüksek risk** taşır; kararlarını her zaman kendin ver,
> kaybetmeyi göze alamayacağın parayla işlem yapma.

---

## 🤖 Asistan Modu (Yatırım bilgin olmadan kullanım)

Botu ilk kullandığında `/basla` yaz — 5 basit soruyla (maaş, gider, risk
anlayışın, hedef, maaş günü) sana özel otomatik plan kurulur:

- 💰 **Maaşını otomatik böler:** Zorunlu gider / isteğe bağlı / birikim (50/30/20 kuralı)
- 🛡️ **Acil durum fonu** hedefi belirler (6 aylık giderin)
- 📈 Risk profiline göre **sade dilde** yatırım dağılımı önerir
- 🌅 **Her sabah 09:00** hatırlatma + sade piyasa özeti + bilgi notu gönderir
- 🌙 **Her akşam 20:00** "Bugün harcama yaptın mı?" diye sorar (butonla cevapla)
- 🎉 **Maaş gününde** plana göre dağılımı hatırlatır
- 💡 Arada bir basit finans bilgisi öğretir

**Örnek konuşma:**
```
🌙 Akşam kontrolü
Bugün harcama yaptın mı?
[💸 Evet, harcama yaptım]  [✅ Hayır]

→ "Evet" dersen: "Tamam! 250 market şeklinde yaz, ben kaydedeyim."
→ "Hayır" dersen: "Harika! Bu ay kalan: 12.500 ₺"
```

---

## ✨ Özellikler

| Alan | Komutlar |
|------|----------|
| 🤖 **Asistan** | `/basla` (plan kur), `/asistan` (menü), `/durum` |
| 📊 **Canlı takip** | `/hisse THYAO`, `/analiz AAPL`, `/dolar` |
| 🖼️ **Grafikler** | `/grafik THYAO 6mo` — fiyat + SMA + Bollinger + RSI görseli |
| 💬 **Doğal dil** | "BTC ne durumda?", "THYAO alınır mı?", "Bu ay ne kadar harcadım?" |
| 🔔 **Takip listesi** | `/takip`, `/takipler`, `/silah` |
| 🎯 **Sinyal taraması** | `/sinyal` (otomatik saatlik tarama) |
| 🔔 **Fiyat alarmı** | `/alarm THYAO 300 ust` |
| ⚡ **Ani hareket alarmı** | %5+ günlük hareket → anında bildirim (otomatik) |
| 💼 **Portföy** | `/ekle`, `/sat`, `/portfoy`, `/islemler` (FIFO kar/zarar) |
| 💰 **Maaş & bütçe** | `/maas`, `/yatirim`, `/harcama`, `/butce`, `/rapor` |

**Otomatik görevler:**
| Saat | Görev |
|------|-------|
| 09:00 | 🌅 Sabah asistan mesajı (hatırlatma + özet + bilgi notu) |
| 09:30 | 🎉 Maaş günü dağılım hatırlatması (maaş gününde) |
| 10:05 | 🇹🇷 BIST açılış seansı — takip listesi hareketleri (hafta içi) |
| her 3 dk | 🔔 Fiyat alarmları + ⚡ ani hareket kontrolü |
| saatlik | 🎯 Sinyal taraması (güçlü sinyaller bildirilir) |
| 12:00 | 📈 Yatırım hedefi hatırlatması (ayın 15'i ve 28'i) |
| 18:30 | 📅 Gün sonu özeti (portföy + sinyaller + günün hareketleri) |
| 19:00 | 📑 Haftalık rapor (Pazar) |
| 20:00 | 🌙 Akşam harcama kontrolü (interaktif soru) |

## 💬 Doğal Dil Örnekleri

Komut ezberlemene gerek yok — sadece yaz:
- "BTC ne durumda?" → fiyat + teknik özet
- "THYAO alınır mı?" → fiyat + sade dilde yorum
- "Bu ay ne kadar harcadım?" → bütçe durumu
- "Portföyüm nasıl?" → portföy özeti
- "Ne almalıyım?" → takip listesi sinyalleri
- "Bana bir şey öğret" → günün bilgi notu
- "Planımı göster" → kişisel planın

---

## 🚀 Kurulum

### 1. Gerekli paketler
```bash
pip install -r requirements.txt
```

### 2. Telegram botunu oluştur
1. Telegram'da [@BotFather](https://t.me/BotFather)'a yaz
2. `/newbot` komutuyla bot oluştur, **token**'ı kopyala

### 3. `.env` dosyasını hazırla
```bash
copy .env.example .env
```
`.env` dosyasını düzenle:
```
BOT_TOKEN=BotFather'dan_aldığın_token
ALLOWED_USER_IDS=
```
- `ALLOWED_USER_IDS`'i boş bırak, botu çalıştır ve Telegram'da botuna `/start` yaz.
- Bot sana user ID'ni gösterir; bu ID'yi `.env`'e ekleyip botu yeniden başlat.

### 4. Çalıştır
```bash
python main.py
```

---

## 📖 Komut Rehberi

### Piyasa
- `/hisse SYMBOL` — anlık fiyat + teknik özet. Örn: `/hisse THYAO`, `/hisse AAPL`, `/hisse BTC`
- `/analiz SYMBOL` — detaylı analiz (RSI, MACD, SMA, Bollinger, destek/direnç, ATR)
- `/dolar` — USD/TRY, EUR/TRY, EUR/USD, altın

### Sembol formatları
| Piyasa | Örnek |
|--------|-------|
| BIST | `THYAO` veya `THYAO.IS` (otomatik algılanır) |
| ABD | `AAPL`, `TSLA`, `NVDA` |
| Kripto | `BTC`, `ETH`, `SOL` |
| Döviz | `USD`, `EUR` |

### Portföy (FIFO maliyet bazlı)
- `/ekle THYAO 100 250` — 100 lot THYAO'yu 250₺'den aldın
- `/sat THYAO 50 275` — 50 lotu 275₺'den sattın
- `/portfoy` — tüm pozisyonlar, gerçekleşen + gerçekleşmemiş kar/zarar

> Not: `/ekle` kayıtları aynı zamanda aylık **yatırım hedefi** ilerlemeni besler.

### Maaş & bütçe
- `/maas 50000` — aylık maaşını tanımla
- `/yatirim 10000` — aylık yatırım hedefi belirle
- `/harcama 1500 market` — gider ekle (kategori serbest)
- `/butce` — bütçe durumu (kalan, tasarruf oranı)
- `/rapor` — aylık rapor (harcama kategorileri + yatırım ilerlemesi + portföy)

> 💡 Akşam kontrolünde "harcama yaptım" dersen, sadece `250 market` yazarak
> kaydedebilirsin — `/harcama` yazmana gerek yok.

---

## ☁️ Buluta Taşıma (7/24 Kesintisiz — Ücretsiz)

**Seçilen yol: Render (ücretsiz) + Neon Postgres + UptimeRobot ping.**

- 🚀 **Render** — GitHub'dan ücretsiz deploy (kart gerekmez), 750 saat/ay kotası
  (24/7 çalışan bot ~720 saat kullanır, sığar).
- 🔋 **UptimeRobot** — ücretsiz, 5 dk'da bir sağlık adresine ping atar; Render
  ücretsiz katmanı 15 dk sessizlikte uyuttuğu için bu ping botu uyanık tutar.
- 🗄️ **Neon** — ücretsiz Postgres (0.5 GB). Render ücretsiz katmanda kalıcı disk
  desteklemediği için veriler bulut veritabanında saklanır. `DATABASE_URL` set
  edildiğinde bot otomatik Postgres kullanır (kod değişmez).

### 1. Neon: ücretsiz Postgres oluştur
1. [neon.tech](https://neon.tech) → GitHub ile üye ol → **Create a project**
   (region: Europe) → veritabanı oluşur.
2. **Connection string**'i kopyala: `postgresql://user:pass@host/db?sslmode=require`
   (buna `DATABASE_URL` diyeceğiz).

### 2. Render: botu deploy et
1. [render.com](https://render.com) → GitHub ile üye ol (kart gerekmez).
2. **New → Blueprint** → `iamolmez/yfinance-bot` repoyu seç. `render.yaml`
   otomatik yapılandırır.
3. Deploy başlar; **Environment** ayarlarından şu değişkenleri gir:
   ```
   BOT_TOKEN=BotFather'dan_aldığın_token
   ALLOWED_USER_IDS=user_id'n
   DATABASE_URL=neon'dan_kopyaladığın_adres
   ```
4. Deploy bitince loglarda `Application started` gör. Bot aktif!

### 3. UptimeRobot: botu uyanık tut
1. [uptimerobot.com](https://uptimerobot.com) → ücretsiz üye ol.
2. **Add New Monitor** → **HTTP(s)** → URL'ye Render servis adresini gir:
   `https://yfinance-bot.onrender.com/`
3. **Monitoring Interval: 5 minutes** → **Create Monitor**.

Bitti! 🎉 Artık bilgisayarın kapalıyken de bot 7/24 çalışır ve verilerin
Neon'da güvende.

### 🔄 Güncellemeler
`git push` yaptığında Render otomatik yeniden dağıtır. Veriler Neon'da
olduğu için korunur.

### 🐞 Hata ayıklama
- **Render logları:** Dashboard → Service → Logs
- `BOT_TOKEN bos!` → env değişkeni set edilmemiş
- `401 Unauthorized` → token yanlış / yenilenmiş
- Veritabanı hatası → `DATABASE_URL` doğru mu, `?sslmode=require` ekli mi
- Servis uyuyor mu → UptimeRobot monitor çalışıyor mu, 5 dk aralık mı

### Alarmlar
- `/alarm THYAO 300 ust` — fiyat 300'ü geçince bildir
- `/alarm BTC 75000 alt` — fiyat 75.000'in altına inince bildir
- `/alarmlar`, `/alarmsil ID`

---

## 🧪 Test

Bot token'ı olmadan çekirdek mantığı test eder (canlı piyasa verisi kullanır):
```bash
python smoke_test.py
```

---

## 📂 Proje Yapısı
```
main.py              # Giriş noktası
config.py            # .env ayarları
database.py          # SQLite katmanı
services/
  market_data.py     # Fiyat çekme, sembol çözümleme, önbellek
  indicators.py      # RSI, MACD, SMA, Bollinger, ATR...
  signals.py         # Sinyal motoru (puanlama + gerekçeler)
  charts.py          # 🖼️ matplotlib grafik üretici
  nlp.py             # 💬 Doğal dil komut çözümleyici
  portfolio.py       # FIFO portföy hesabı
  budget.py          # Maaş/bütçe raporu
  alerts.py          # Fiyat alarmı + ⚡ ani hareket alarmı
  assistant.py       # 🤖 Maaş bölme planı, sade dil mesajları, bilgi notları
bot/
  handlers.py        # Telegram komutları + asistan butonları + NLP yönlendirme
  onboarding.py      # 🧭 /basla 5 soruluk kurulum akışı
  jobs.py            # Otomatik görevler (alarm, seans, sabah/akşam/maaş günü)
```

## ⚙️ Yapılandırma (.env)
| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `BOT_TOKEN` | — | BotFather token'ı (zorunlu) |
| `ALLOWED_USER_IDS` | — | Yetkili kullanıcı id'leri, virgülle ayrılır |
| `BASE_CURRENCY` | `TRY` | Portföy toplamının gösterileceği para birimi |
| `HISTORY_PERIOD` | `6mo` | Sinyal hesabında kullanılan veri derinliği |
| `SCAN_MINUTES` | `60` | Sinyal tarama sıklığı (dakika) |
| `ALERT_CHECK_SECONDS` | `180` | Alarm kontrol sıklığı (saniye) |
| `BIG_MOVE_PCT` | `5.0` | Ani hareket alarmı eşiği (günlük % değişim) |

---

## 🛡️ Sorumluluk Reddi
Bu proje eğitim ve kişisel takip amaçlıdır. Sinyaller, geçmiş fiyat verilerinden
türetilen istatistiksel göstergelerdir; gelecekteki fiyat hareketlerini garanti
etmez. Yatırım kararların ve sonuçlarından sen sorumlusun.
