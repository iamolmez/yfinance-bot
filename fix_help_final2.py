import re

with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the entire cmd_help function using regex
pattern = r'async def cmd_help\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):[\s\S]*?\nasync def send_quote'

new_func = '''async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Komut Rehberi</b>\\n\\n"
        "<b>🏠 Ana Menu</b>\\n"
        "/menu — Butonlarla tum islemler (nakit, portfoy, risk, hedefler, harcamalar, analiz)\\n\\n"
        "<b>📊 Piyasa</b>\\n"
        "/hisse SYMBOL — anlık fiyat + analiz (orn: THYAO, AAPL, BTC)\\n"
        "/analiz SYMBOL — detayli teknik analiz\\n"
        "/grafik SYMBOL [PERIYOT] — fiyat + SMA + Bollinger + RSI grafigi\\n"
        "/dolar — guncei doviz kurları\\n\\n"
        "<b>🔔 Takip & Sinyal</b>\\n"
        "/takip SYMBOL — takip listesine ekle\\n"
        "/takipler — takip listen\\n"
        "/silah SYMBOL — listeden cikar\\n"
        "/sinyal — tum listeni tara, sinyalleri goster\\n"
        "/alarm SYMBOL FIYAT [ust|alt] — fiyat alarmı\\n"
        "/alarmlar — alarmlarin\\n"
        "/alarmsil ID — alarmı sil\\n\\n"
        "<b>🤖 Otomatik & Gelismis</b>\\n"
        "/oner — Bot kendisi hisse secer (guvenli + riskli karisim)\\n"
        "/alarm2 SYMBOL TUR PARAM — gelismis alarm (RSI/MACD/BB/Hacim/Fiyat)\\n"
        "/alarm2lar — aktif gelismis alarmlar\\n"
        "/alarm2sil ID — gelismis alarm sil\\n\\n"
        "<b>💼 Portfoy</b>\\n"
        "/ekle SYMBOL ADET FIYAT — alim kaydet\\n"
        "/sat SYMBOL ADET FIYAT — satis kaydet\\n"
        "/portfoy — portfoy ozeti ve kar/zarar\\n"
        "/islemler — islem gecmisi\\n"
        "/karsilastir SYM1 SYM2 — iki hisse karsilastirma\\n\\n"
        "<b>📈 Analiz & Risk</b>\\n"
        "/analiz SYMBOL — detayli teknik analiz\\n"
        "/temel SYMBOL — temel analiz (F/K, P/B, ROE, marj, buyume)\\n"
        "/backtest SYMBOL [PERIYOT] — strateji gecmise testi\\n"
        "/riskmetrik [GUN] — Sharpe, Sortino, Calmar, Max DD, VaR\\n"
        "/montecarlo [YIL] [SIM] — Monte Carlo simulasyonu\\n"
        "/risk — portfoy risk analizi (korelasyon, HHI, DD)\\n"
        "/korelasyon [PERIYOT] — korelasyon matrisi + cesitlendirme\\n\\n"
        "<b>💰 Maaş & Butce</b>\\n"
        "/maas TUTAR — aylik maasini tanimla\\n"
        "/yatirim TUTAR — aylik yatirim hedefi\\n"
        "/harcama TUTAR KATEGORI — gider ekle\\n"
        "/butce — butce durumu\\n"
        "/rapor — aylik rapor\\n\\n"
        "<b>💰 Nakit & Temettü</b>\\n"
        "/nakit [TUTAR] — eldeki nakit goster/ayarla\\n"
        "/maasgunu GUN — maas gununu ayarla (orn: 8)\\n"
        "/temettutakip [YIL] — temettu ozeti + DRIP onerileri\\n\\n"
        "<b>📊 Performans & Takvim</b>\\n"
        "/performans — performans atfi (hangi karar ne kazandirdi)\\n"
        "/takvim [GUN] — kurumsal takvim (temettu, ceyrek, bolunme)\\n\\n"
        "<b>💾 Yedek & Veri</b>\\n"
        "/yedek — GitHub Gist'e sifreli tam yedek\\n"
        "/yedekal GIST_ID — yedekten restore\\n"
        "/csv [islemler|portfoy|temettu] [YIL] — CSV export\\n"
        "/vergiraporu [YIL] — GVKY raporu (satis kazanci, temettu vergisi)\\n\\n"
        "<b>📝 Notlar & Diger</b>\\n"
        "/not SYMBOL NOT — pozisyona not ekle\\n"
        "/notlar [SYMBOL] — notlari gor\\n"
        "/haber SYMBOL — son haber basliklari\\n"
        "/makro — doviz, emtia, endeksler paneli\\n\\n"
        "<b>⚙️ Kurulum</b>\\n"
        "/basla — 3 soruluk kurulum (maas, gun, risk)\\n"
        "/menu — Ana menu (butonlarla tum islemler)\\n\\n"
        "⚠️ <i>Sinyaller yatirim tavsiyesi degildir.</i>"
    )
    await update.message.reply_text(text)


async def send_quote'''

# Use re.DOTALL to match across newlines
new_content = re.sub(pattern, new_func, content, flags=re.DOTALL)

with open('bot/handlers.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Fixed cmd_help')