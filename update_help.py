with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "?? <b>Komut Rehberi</b>\\n\\n"
        "<b>[GRAFIK] Piyasa</b>\\n"
        "/hisse SYMBOL ??anlık fiyat + analiz (örn: THYAO, AAPL, BTC)\\n"
        "/analiz SYMBOL ??detaylı teknik analiz\\n"
        "/dolar ??güncel döviz kurları\\n\\n"
        "<b>?? Takip & Sinyal</b>\\n"
        "/takip SYMBOL ??takip listesine ekle\\n"
        "/takipler ??takip listen\\n"
        "/silah SYMBOL ??listeden çıkar\\n"
        "/sinyal ??tüm listeni tara, sinyalleri göster\\n"
        "/alarm SYMBOL FIYAT [ust|alt] ??fiyat alarmı\\n"
        "/alarmlar ??alarmların\\n"
        "/alarmsil ID ??alarmı sil\\n\\n"
        "<b>?�� Portföy</b>\\n"
        "/ekle SYMBOL ADET FIYAT ??alım kaydet\\n"
        "/sat SYMBOL ADET FIYAT ??satı? kaydet\\n"
        "/portfoy ??portföy özeti ve kar/zarar\\n"
        "/islemler ??i?lem geçmi?i\\n\\n"
        "<b>[PARA] Maa? & Bütçe</b>\\n"
        "/maas TUTAR ??aylık maa?ını tanımla\\n"
        "/yatirim TUTAR ??aylık yatırım hedefi\\n"
        "/harcama TUTAR KATEGORİ ??gider ekle\\n"
        "/butce ??bütçe durumu\\n"
        "/rapor ??aylık rapor\\n\\n"
        "?��? <i>Sinyaller yatırım tavsiyesi de?ildir.</i>"
    )
    await update.message.reply_text(text)'''

new = '''async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(text)'''

if old in content:
    content = content.replace(old, new)
    with open('bot/handlers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated cmd_help')
else:
    print('Pattern not found exactly')
    # Show what we have
    idx = content.find('async def cmd_help')
    if idx >= 0:
        with open('debug_help.txt', 'w', encoding='utf-8') as out:
            out.write(content[idx:idx+600])
        print('Wrote debug file')