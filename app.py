import streamlit as st
import pandas as pd
from PIL import Image
import json
import os
import re
import urllib.parse
from datetime import datetime, date, timedelta
from google import genai
from google.genai import types

# ==========================================
# 🔑 1. API ANAHTARI VE YAPILANDIRMA
# ==========================================
DEFAULT_GEMINI_API_KEY = ""

st.set_page_config(
    page_title="Akbük Tatil Hesaplayıcı & Takvim", 
    page_icon="🏖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 🎨 2. ÖZEL TEMA, YAZI TİPİ VE İKON KORUMALI CSS
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .stMarkdown, p, label, .stTextInput > div > div > input, .stNumberInput > div > div > input {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    h1 {
        background: linear-gradient(135deg, #00838F 0%, #00ACC1 50%, #FF7043 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem !important;
        padding-bottom: 0.2rem;
    }

    [data-testid="stIconMaterial"], 
    .material-symbols-rounded, 
    .material-symbols-sharp, 
    .material-symbols-outlined, 
    [class*="material-symbols"], 
    [data-testid="stSidebarCollapseButton"] span,
    [data-testid="stIcon"],
    button span[class*="material-symbols"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
        font-style: normal !important;
        font-variant: normal !important;
        text-transform: none !important;
        line-height: 1 !important;
        display: inline-block !important;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
        margin-bottom: 12px !important;
    }

    div.stButton > button {
        border-radius: 10px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 131, 143, 0.25) !important;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
    }

    div[data-testid="stAlert"] {
        border-radius: 12px !important;
        font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌐 3. ORTAK CANLI VERİTABANI SİSTEMİ (TÜM KULLANICILAR İÇİN)
# ==========================================
DB_FILE = "tatil_veritabani.json"

def tarih_serilestir(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def tarih_ayikla(val, default_date):
    if not val:
        return default_date
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    if isinstance(val, str):
        try:
            return date.fromisoformat(val)
        except Exception:
            return default_date
    if isinstance(val, int):
        return default_date + timedelta(days=max(0, val - 1))
    return default_date

def ortak_verileri_yukle():
    bugun = date.today()
    varsayilan = {
        "tatil_baslangic": bugun.isoformat(),
        "tatil_bitis": (bugun + timedelta(days=13)).isoformat(),
        "kisiler": [],
        "harcamalar": []
    }
    
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(varsayilan, f, ensure_ascii=False, indent=2)
        return varsayilan
    
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            veri = json.load(f)
            return veri
    except Exception:
        return varsayilan

def ortak_verileri_kaydet(kisiler, harcamalar, tatil_bas, tatil_bit):
    # Tarihleri string (ISO) formatına çevirerek diske yaz
    kisiler_kayit = []
    for k in kisiler:
        kisiler_kayit.append({
            "İsim": k["İsim"],
            "Giriş": tarih_serilestir(k.get("Giriş", tatil_bas)),
            "Çıkış": tarih_serilestir(k.get("Çıkış", tatil_bit)),
            "Kalış Süresi": k.get("Kalış Süresi", "1 Gün")
        })
        
    harcamalar_kayit = []
    for h in harcamalar:
        harcamalar_kayit.append({
            "ID": h["ID"],
            "Açıklama": h["Açıklama"],
            "Tutar": float(h["Tutar"]),
            "Ödeyen": h["Ödeyen"],
            "Dahil Olanlar": h.get("Dahil Olanlar", []),
            "Başlangıç": tarih_serilestir(h.get("Başlangıç", tatil_bas)),
            "Bitiş": tarih_serilestir(h.get("Bitiş", tatil_bit))
        })
        
    veri_paketi = {
        "tatil_baslangic": tarih_serilestir(tatil_bas),
        "tatil_bitis": tarih_serilestir(tatil_bit),
        "kisiler": kisiler_kayit,
        "harcamalar": harcamalar_kayit
    }
    
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(veri_paketi, f, ensure_ascii=False, indent=2)

# Oturum Başında Ortak Veritabanını Yükle
veri_db = ortak_verileri_yukle()
bugun_dt = date.today()
st.session_state.tatil_baslangic = tarih_ayikla(veri_db.get("tatil_baslangic"), bugun_dt)
st.session_state.tatil_bitis = tarih_ayikla(veri_db.get("tatil_bitis"), bugun_dt + timedelta(days=13))

# Kişileri Session'a aktar
st.session_state.kisiler = []
for k in veri_db.get("kisiler", []):
    g = tarih_ayikla(k.get("Giriş") or k.get("Geliş"), st.session_state.tatil_baslangic)
    c = tarih_ayikla(k.get("Çıkış") or k.get("Gidiş"), st.session_state.tatil_bitis)
    st.session_state.kisiler.append({
        "İsim": k["İsim"],
        "Giriş": g,
        "Çıkış": c,
        "Kalış Süresi": f"{(c - g).days + 1} Gün"
    })

# Harcamaları Session'a aktar
st.session_state.harcamalar = []
for h in veri_db.get("harcamalar", []):
    hb = tarih_ayikla(h.get("Başlangıç"), st.session_state.tatil_baslangic)
    hs = tarih_ayikla(h.get("Bitiş"), st.session_state.tatil_bitis)
    st.session_state.harcamalar.append({
        "ID": h.get("ID", len(st.session_state.harcamalar) + 1),
        "Açıklama": h["Açıklama"],
        "Tutar": float(h["Tutar"]),
        "Ödeyen": h["Ödeyen"],
        "Dahil Olanlar": h.get("Dahil Olanlar", []),
        "Başlangıç": hb,
        "Bitiş": hs
    })

if 'fisten_okunanlar' not in st.session_state:
    st.session_state.fisten_okunanlar = []

if 'gemini_api_key' not in st.session_state:
    if "GEMINI_API_KEY" in st.secrets:
        st.session_state.gemini_api_key = st.secrets["GEMINI_API_KEY"]
    else:
        st.session_state.gemini_api_key = DEFAULT_GEMINI_API_KEY

def get_tatil_gunleri():
    bas = st.session_state.tatil_baslangic
    bit = st.session_state.tatil_bitis
    if bit < bas:
        bit = bas
    gun_sayisi = (bit - bas).days + 1
    return [bas + timedelta(days=i) for i in range(gun_sayisi)]

# ==========================================
# 🤖 4. GEMINI VISION İLE FİŞ OKUMA
# ==========================================
def gemini_ile_fis_oku(gorsel):
    api_key = st.session_state.gemini_api_key.strip()
    if not api_key:
        st.error("⚠️ Lütfen geçerli bir Gemini API Anahtarı giriniz! (Yan menüdeki Ayarlar'dan ekleyebilirsiniz.)")
        return []
    
    try:
        client = genai.Client(api_key=api_key)
        prompt = """
        Sen uzman bir fiş/fatura okuma asistanısın.
        Görseldeki alışveriş fişini incele. Satın alınan ürün/hizmet kalemlerini ve KDV dahil net tutarlarını çıkar.
        Kurallar:
        1. "TOPLAM", "KDV", "ARA TOPLAM", "NAKİT", "KREDİ KARTI" gibi genel toplam satırlarını DAHİL ETME.
        2. Sadece münferit ürün veya hizmet kalemlerini listele.
        3. Tutar rakamını float olarak yaz (Örn: 45.50).
        4. Çıktı sadece geçerli bir JSON listesi olmalıdır:
        [
            {"Açıklama": "Ekmek 2 Adet", "Tutar": 25.0},
            {"Açıklama": "Beyaz Peynir", "Tutar": 140.75}
        ]
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[gorsel, prompt]
        )
        yanit = response.text.strip()
        json_eslesme = re.search(r'\[.*\]', yanit, re.DOTALL)
        if json_eslesme:
            return json.loads(json_eslesme.group(0))
        else:
            temiz = yanit.replace("```json", "").replace("```", "").strip()
            return json.loads(temiz)
    except Exception as e:
        st.error(f"Fiş okunurken hata oluştu: {str(e)}")
        return []

# ==========================================
# 📱 5. ARAYÜZ VE MENÜ
# ==========================================
st.title("🏖️ Tatil Harcama & Ev Takvimi")

# Canlı Senkronizasyon Butonu (Üst Çubuk)
col_sync1, col_sync2 = st.columns([3, 1])
with col_sync1:
    st.caption("🟢 **Canlı Ortak Havuz Aktif:** Arkadaşlarınızın eklediği harcamalar ve kişiler otomatik senkronize olur.")
with col_sync2:
    if st.button("🔄 Canlı Verileri Yenile", use_container_width=True):
        st.rerun()

menu = st.sidebar.radio(
    "Menü", 
    [
        "📅 Ev Takvimi & Doluluk", 
        "👥 Kişileri Yönet", 
        "💸 Manuel Harcama Ekle", 
        "📸 Fişten Yapay Zeka ile Ekle", 
        "📊 Hesaplaşma & WhatsApp", 
        "⚙️ Ayarlar & Yedekleme"
    ]
)

gunler_listesi = get_tatil_gunleri()

# -------------------------------------------------------------------
# MENÜ 1: EV TAKVİMİ & DOLULUK ÇİZELGESİ
# -------------------------------------------------------------------
if menu == "📅 Ev Takvimi & Doluluk":
    st.header("📅 Kim Hangi Gün Evde? (Doluluk Çizelgesi)")
    
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.info(f"🗓️ **Tatil Aralığı:** {st.session_state.tatil_baslangic.strftime('%d.%m.%Y')} — {st.session_state.tatil_bitis.strftime('%d.%m.%Y')} (Toplam **{len(gunler_listesi)} Gün**)")
    with col_t2:
        st.metric("Evdeki Toplam Kayıtlı Kişi", len(st.session_state.kisiler))
    
    if not st.session_state.kisiler:
        st.warning("Henüz kişi eklenmedi. Lütfen '👥 Kişileri Yönet' menüsünden evde kalacak kişileri ekleyin.")
    else:
        matris_data = {}
        gun_basliklari = [g.strftime("%d %b\n(%a)") for g in gunler_listesi]
        
        for k in st.session_state.kisiler:
            kisi_adi = k["İsim"]
            k_giris = k.get("Giriş", st.session_state.tatil_baslangic)
            k_cikis = k.get("Çıkış", st.session_state.tatil_bitis)
            
            satir = []
            for g in gunler_listesi:
                if k_giris <= g <= k_cikis:
                    satir.append("🟢 Evde")
                else:
                    satir.append("—")
            matris_data[kisi_adi] = satir
            
        df_takvim = pd.DataFrame(matris_data, index=gun_basliklari).T
        
        gunluk_sayilar = []
        for g in gunler_listesi:
            sayi = sum(1 for k in st.session_state.kisiler if k.get("Giriş", st.session_state.tatil_baslangic) <= g <= k.get("Çıkış", st.session_state.tatil_bitis))
            gunluk_sayilar.append(f"{sayi} Kişi")
        
        df_takvim.loc["👥 TOPLAM KİŞİ"] = gunluk_sayilar
        
        st.subheader("📊 Gün Gün Evde Olanlar Matrisi")
        st.dataframe(df_takvim, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🔍 Güne Göre Evdekileri Gör")
        secili_gun = st.date_input(
            "Tarih Seçin:", 
            value=st.session_state.tatil_baslangic,
            min_value=st.session_state.tatil_baslangic,
            max_value=st.session_state.tatil_bitis
        )
        
        o_gun_evde = [k["İsim"] for k in st.session_state.kisiler if k.get("Giriş", st.session_state.tatil_baslangic) <= secili_gun <= k.get("Çıkış", st.session_state.tatil_bitis)]
        if o_gun_evde:
            st.success(f"**{secili_gun.strftime('%d.%m.%Y %A')}** günü evde olanlar (**{len(o_gun_evde)} Kişi**): " + ", ".join([f"**{isim}**" for isim in o_gun_evde]))
        else:
            st.warning(f"**{secili_gun.strftime('%d.%m.%Y')}** günü evde kimse görünmüyor.")

# -------------------------------------------------------------------
# MENÜ 2: KİŞİLERİ YÖNET
# -------------------------------------------------------------------
elif menu == "👥 Kişileri Yönet":
    st.header("👥 Kişi Ekle & Takvim Tarihlerini Seç")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("kisi_ekle_takvim_form", clear_on_submit=True):
            isim = st.text_input("Kişi Adı (Örn: Baran, Bahar, Ali)").strip()
            
            st.markdown("**🗓️ Eve Giriş ve Çıkış Tarihi:**")
            tarih_araligi = st.date_input(
                "Tarih Aralığı Seçin",
                value=(st.session_state.tatil_baslangic, st.session_state.tatil_bitis),
                min_value=st.session_state.tatil_baslangic - timedelta(days=60),
                max_value=st.session_state.tatil_bitis + timedelta(days=60)
            )
            
            submit_kisi = st.form_submit_button("➕ Kişiyi Takvime Ekle", use_container_width=True)
            
            if submit_kisi:
                if not isim:
                    st.error("Lütfen bir isim yazın!")
                elif isinstance(tarih_araligi, (list, tuple)) and len(tarih_araligi) == 2:
                    k_giris, k_cikis = tarih_araligi
                    mevcutlar = [k["İsim"].lower() for k in st.session_state.kisiler]
                    if isim.lower() in mevcutlar:
                        st.warning(f"'{isim}' zaten ekli!")
                    else:
                        st.session_state.kisiler.append({
                            "İsim": isim, 
                            "Giriş": k_giris, 
                            "Çıkış": k_cikis,
                            "Kalış Süresi": f"{(k_cikis - k_giris).days + 1} Gün"
                        })
                        ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                        st.success(f"✅ {isim} ortak havuza kaydedildi!")
                        st.rerun()
                elif isinstance(tarih_araligi, (list, tuple)) and len(tarih_araligi) == 1:
                    k_giris = k_cikis = tarih_araligi[0]
                    st.session_state.kisiler.append({
                        "İsim": isim, 
                        "Giriş": k_giris, 
                        "Çıkış": k_cikis,
                        "Kalış Süresi": "1 Gün"
                    })
                    ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                    st.success(f"✅ {isim} ortak havuza kaydedildi!")
                    st.rerun()
                else:
                    st.error("Lütfen hem giriş hem çıkış tarihini seçiniz!")

    with col2:
        st.subheader("📋 Kayıtlı Kişiler (Ortak Liste)")
        if st.session_state.kisiler:
            df_goster = []
            for k in st.session_state.kisiler:
                giris_val = k.get("Giriş", st.session_state.tatil_baslangic)
                cikis_val = k.get("Çıkış", st.session_state.tatil_bitis)
                df_goster.append({
                    "İsim": k["İsim"],
                    "Giriş Tarihi": giris_val.strftime("%d.%m.%Y") if isinstance(giris_val, (date, datetime)) else str(giris_val),
                    "Çıkış Tarihi": cikis_val.strftime("%d.%m.%Y") if isinstance(cikis_val, (date, datetime)) else str(cikis_val),
                    "Kalış Süresi": k.get("Kalış Süresi", "1 Gün")
                })
            st.dataframe(pd.DataFrame(df_goster), use_container_width=True)
            
            kisi_sil = st.selectbox("🗑️ Silinecek Kişi:", [k["İsim"] for k in st.session_state.kisiler])
            if st.button("❌ Seçili Kişiyi Sil"):
                st.session_state.kisiler = [k for k in st.session_state.kisiler if k["İsim"] != kisi_sil]
                st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["Ödeyen"] != kisi_sil]
                ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                st.rerun()
        else:
            st.info("Henüz kişi eklenmedi.")

# -------------------------------------------------------------------
# MENÜ 3: MANUEL HARCAMA EKLE
# -------------------------------------------------------------------
elif menu == "💸 Manuel Harcama Ekle":
    st.header("💸 Manuel Harcama Ekle")
    
    if not st.session_state.kisiler:
        st.warning("⚠️ Önce 'Kişileri Yönet' menüsünden kişileri ekleyin!")
    else:
        kisi_isimleri = [k["İsim"] for k in st.session_state.kisiler]
        
        with st.form("manuel_harcama_form", clear_on_submit=True):
            aciklama = st.text_input("Neye Harcandı?", placeholder="Örn: Akşam Yemeği, Su, Tekila, Kahvaltılık").strip()
            tutar = st.number_input("Tutar (₺)", min_value=0.0, step=10.0, format="%.2f")
            odeyen = st.selectbox("Parayı Kim Ödedi?", kisi_isimleri)
            
            st.markdown("**🎯 Bu harcama KİMLERİ kapsıyor?**")
            st.caption("Boş bırakırsanız seçilen tarihlerde evde olan herkese bölünür. Özel harcamalar için sadece tüketenleri seçin.")
            dahil_olanlar = st.multiselect("Dahil Olan Kişiler (Opsiyonel)", options=kisi_isimleri)
            
            st.markdown("**📅 Harcamanın Geçerli Olduğu Tarih Aralığı:**")
            harcama_tarihleri = st.date_input(
                "Tarih Aralığı (Tek gün için aynı tarihi iki kez seçin)",
                value=(st.session_state.tatil_baslangic, st.session_state.tatil_bitis),
                min_value=st.session_state.tatil_baslangic - timedelta(days=60),
                max_value=st.session_state.tatil_bitis + timedelta(days=60)
            )
            
            submit_h = st.form_submit_button("💾 Harcamayı Ortak Havuza Kaydet", use_container_width=True)
            if submit_h:
                if not aciklama or tutar <= 0:
                    st.error("Lütfen açıklama ve geçerli bir tutar girin!")
                else:
                    if isinstance(harcama_tarihleri, (list, tuple)) and len(harcama_tarihleri) == 2:
                        h_bas, h_bit = harcama_tarihleri
                    elif isinstance(harcama_tarihleri, (list, tuple)) and len(harcama_tarihleri) == 1:
                        h_bas = h_bit = harcama_tarihleri[0]
                    else:
                        h_bas = h_bit = harcama_tarihleri

                    st.session_state.harcamalar.append({
                        "ID": len(st.session_state.harcamalar) + 1,
                        "Açıklama": aciklama,
                        "Tutar": tutar,
                        "Ödeyen": odeyen,
                        "Dahil Olanlar": dahil_olanlar,
                        "Başlangıç": h_bas,
                        "Bitiş": h_bit
                    })
                    ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                    st.success(f"✅ '{aciklama}' ({tutar:.2f} ₺) ortak havuza kaydedildi!")
                    st.rerun()

        if st.session_state.harcamalar:
            st.markdown("---")
            st.subheader("📋 Kayıtlı Harcamalar (Ortak Liste)")
            ozet_h = []
            for h in st.session_state.harcamalar:
                h_b = h.get("Başlangıç", st.session_state.tatil_baslangic)
                h_s = h.get("Bitiş", st.session_state.tatil_bitis)
                tarih_str = f"{h_b.strftime('%d.%m')} - {h_s.strftime('%d.%m')}" if isinstance(h_b, (date, datetime)) else f"{h_b}-{h_s}"
                ozet_h.append({
                    "ID": h["ID"],
                    "Açıklama": h["Açıklama"],
                    "Tutar (₺)": f"{h['Tutar']:,.2f} ₺",
                    "Ödeyen": h["Ödeyen"],
                    "Kapsam": ", ".join(h["Dahil Olanlar"]) if h.get("Dahil Olanlar") else "Evdekiler",
                    "Tarihler": tarih_str
                })
            st.dataframe(pd.DataFrame(ozet_h), use_container_width=True)
            
            harcama_sil_id = st.selectbox(
                "🗑️ Silinecek Harcama:", 
                [f"#{h['ID']} - {h['Açıklama']} ({h['Tutar']:.2f} ₺)" for h in st.session_state.harcamalar]
            )
            if st.button("❌ Seçili Harcamayı Sil"):
                secili_id = int(harcama_sil_id.split(" - ")[0].replace("#", ""))
                st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["ID"] != secili_id]
                ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                st.rerun()

# -------------------------------------------------------------------
# MENÜ 4: FİŞTEN YAPAY ZEKA İLE EKLE
# -------------------------------------------------------------------
elif menu == "📸 Fişten Yapay Zeka ile Ekle":
    st.header("📸 Fiş Fotoğrafından Otomatik Oku")
    st.info("Market, restoran veya tekel fişinizin fotoğrafını yükleyin. Gemini AI kalemleri otomatik ayıracaktır.")
    
    if not st.session_state.kisiler:
        st.warning("⚠️ Lütfen önce 'Kişileri Yönet' menüsünden kişileri ekleyin!")
    else:
        kisi_isimleri = [k["İsim"] for k in st.session_state.kisiler]
        yuklenen_fis = st.file_uploader("Fiş Görseli Seç veya Çek", type=["jpg", "jpeg", "png"])
        
        if yuklenen_fis is not None:
            gorsel = Image.open(yuklenen_fis)
            st.image(gorsel, caption="Yüklenen Fiş", use_container_width=True)
            
            if st.button("🔍 Fişi Yapay Zeka ile Tara", type="primary", use_container_width=True):
                with st.spinner("Gemini Yapay Zeka fişi inceliyor ve kalemleri ayırıyor..."):
                    okunan_veriler = gemini_ile_fis_oku(gorsel)
                    if okunan_veriler:
                        st.session_state.fisten_okunanlar = okunan_veriler
                        st.success(f"🎉 {len(okunan_veriler)} adet harcama kalemi başarıyla okundu!")
                    else:
                        st.warning("Fişte okunabilir kalem bulunamadı.")

        if st.session_state.fisten_okunanlar:
            st.markdown("---")
            st.subheader("🛒 Okunan Kalemleri Özelleştir ve Kaydet")
            
            for i, kalem in enumerate(list(st.session_state.fisten_okunanlar)):
                with st.expander(f"📌 {kalem.get('Açıklama', 'Ürün')} — {kalem.get('Tutar', 0.0):.2f} ₺", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        kalem_adi = st.text_input("Ürün Adı", value=kalem.get('Açıklama', ''), key=f"ad_{i}")
                        kalem_tutar = st.number_input("Tutar (₺)", value=float(kalem.get('Tutar', 0.0)), format="%.2f", key=f"tut_{i}")
                        odeyen_fis = st.selectbox("Parayı Kim Ödedi?", kisi_isimleri, key=f"odeyen_{i}")
                    with col2:
                        dahiller_fis = st.multiselect("Kimlere Bölünsün? (Boşsa Herkes)", kisi_isimleri, key=f"dahil_{i}")
                        tarih_fis = st.date_input(
                            "Kullanım Tarihleri", 
                            value=(st.session_state.tatil_baslangic, st.session_state.tatil_bitis),
                            key=f"tarih_{i}"
                        )
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button(f"✅ Harcamalara Ekle", key=f"ekle_{i}", use_container_width=True):
                            if isinstance(tarih_fis, (list, tuple)) and len(tarih_fis) == 2:
                                h_b, h_s = tarih_fis
                            elif isinstance(tarih_fis, (list, tuple)) and len(tarih_fis) == 1:
                                h_b = h_s = tarih_fis[0]
                            else:
                                h_b = h_s = tarih_fis

                            st.session_state.harcamalar.append({
                                "ID": len(st.session_state.harcamalar) + 1,
                                "Açıklama": kalem_adi,
                                "Tutar": kalem_tutar,
                                "Ödeyen": odeyen_fis,
                                "Dahil Olanlar": dahiller_fis,
                                "Başlangıç": h_b,
                                "Bitiş": h_s
                            })
                            st.session_state.fisten_okunanlar.pop(i)
                            ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
                            st.rerun()
                    with col_b2:
                        if st.button(f"🗑️ Yoksay", key=f"sil_{i}", use_container_width=True):
                            st.session_state.fisten_okunanlar.pop(i)
                            st.rerun()

# -------------------------------------------------------------------
# MENÜ 5: HESAPLAŞMA & WHATSAPP
# -------------------------------------------------------------------
elif menu == "📊 Hesaplaşma & WhatsApp":
    st.header("📊 Kim Kime Ne Kadar Ödemeli?")
    
    if not st.session_state.kisiler or not st.session_state.harcamalar:
        st.info("Hesaplama yapabilmek için en az bir kişi ve bir harcama girmelisiniz.")
    else:
        bakiyeler = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        toplam_harcanan = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        kisi_kullanim_payi = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        
        for h in st.session_state.harcamalar:
            bakiyeler[h["Ödeyen"]] += h["Tutar"]
            toplam_harcanan[h["Ödeyen"]] += h["Tutar"]
            
            h_bas = h.get("Başlangıç", st.session_state.tatil_baslangic)
            h_bit = h.get("Bitiş", st.session_state.tatil_bitis)
            if isinstance(h_bas, (date, datetime)) and isinstance(h_bit, (date, datetime)):
                h_gun_sayisi = (h_bit - h_bas).days + 1
                h_gunler = [h_bas + timedelta(days=i) for i in range(h_gun_sayisi)]
            else:
                h_gunler = get_tatil_gunleri()
            
            gecerli_gunler = []
            for gun in h_gunler:
                o_gun_evdekiler = [k["İsim"] for k in st.session_state.kisiler if k.get("Giriş", st.session_state.tatil_baslangic) <= gun <= k.get("Çıkış", st.session_state.tatil_bitis)]
                odeyecekler = [k for k in o_gun_evdekiler if k in h["Dahil Olanlar"]] if h.get("Dahil Olanlar") else o_gun_evdekiler
                if odeyecekler:
                    gecerli_gunler.append((gun, odeyecekler))
            
            if not gecerli_gunler:
                hedef = h["Dahil Olanlar"] if h.get("Dahil Olanlar") else [k["İsim"] for k in st.session_state.kisiler]
                kisi_basi = h["Tutar"] / len(hedef)
                for k in hedef:
                    bakiyeler[k] -= kisi_basi
                    kisi_kullanim_payi[k] += kisi_basi
            else:
                gunluk_maliyet = h["Tutar"] / len(gecerli_gunler)
                for gun, odeyecekler in gecerli_gunler:
                    kisi_basi = gunluk_maliyet / len(odeyecekler)
                    for k in odeyecekler:
                        bakiyeler[k] -= kisi_basi
                        kisi_kullanim_payi[k] += kisi_basi

        # Net Durum Tablosu
        tablo_data = []
        for k in st.session_state.kisiler:
            isim = k["İsim"]
            net = bakiyeler[isim]
            durum = "🟢 Alacaklı" if net > 0.01 else ("🔴 Borçlu" if net < -0.01 else "⚪ Ödeşti")
            tablo_data.append({
                "Kişi": isim,
                "Ödediği (₺)": f"{toplam_harcanan[isim]:,.2f} ₺",
                "Kullanım Payı (₺)": f"{kisi_kullanim_payi[isim]:,.2f} ₺",
                "Net Bakiye (₺)": f"{net:+,.2f} ₺",
                "Durum": durum
            })
            
        st.subheader("💰 Kişi Bazlı Bakiye Tablosu")
        st.dataframe(pd.DataFrame(tablo_data), use_container_width=True)
        
        # Minimum Para Transferi Algoritması
        st.markdown("---")
        st.subheader("🤝 Kolay Hesaplaşma (Transfer Listesi)")
        borclular = [{"kisi": k, "tutar": -b} for k, b in bakiyeler.items() if b < -0.01]
        alacaklilar = [{"kisi": k, "tutar": b} for k, b in bakiyeler.items() if b > 0.01]
        
        i, j = 0, 0
        transferler = []
        while i < len(borclular) and j < len(alacaklilar):
            odenecek = min(borclular[i]["tutar"], alacaklilar[j]["tutar"])
            if odenecek > 0.01:
                transferler.append({
                    "borclu": borclular[i]["kisi"],
                    "alacakli": alacaklilar[j]["kisi"],
                    "tutar": odenecek
                })
            borclular[i]["tutar"] -= odenecek
            alacaklilar[j]["tutar"] -= odenecek
            if borclular[i]["tutar"] < 0.01: i += 1
            if alacaklilar[j]["tutar"] < 0.01: j += 1
            
        if transferler:
            for t in transferler:
                st.info(f"👉 **{t['borclu']}** ➡️ **{t['alacakli']}** kişisine **{t['tutar']:,.2f} ₺** gönderecek.")
        else:
            st.success("🎉 Herkes ödeşmiş durumda! Transfer gerekmiyor.")

        # WhatsApp Özeti
        st.markdown("---")
        st.subheader("📲 WhatsApp Tatil Grubu Özeti")
        toplam_grup_harcamasi = sum(h["Tutar"] for h in st.session_state.harcamalar)
        
        wp_metin = f"🏖️ *TATİL HESAPLAŞMA DÖKÜMÜ*\n"
        wp_metin += f"📅 *Tarih:* {st.session_state.tatil_baslangic.strftime('%d.%m')} - {st.session_state.tatil_bitis.strftime('%d.%m.%Y')}\n"
        wp_metin += f"💰 *Toplam Harcama:* {toplam_grup_harcamasi:,.2f} TL\n\n"
        wp_metin += "📊 *Kişi Bazlı Durum:*\n"
        for k in st.session_state.kisiler:
            isim = k["İsim"]
            net = bakiyeler[isim]
            if net > 0.01:
                wp_metin += f"• {isim}: +{net:,.2f} TL (Alacaklı)\n"
            elif net < -0.01:
                wp_metin += f"• {isim}: {net:,.2f} TL (Borçlu)\n"
            else:
                wp_metin += f"• {isim}: 0.00 TL (Ödeşti)\n"
                
        wp_metin += "\n🤝 *Ödeme / Transfer Planı:*\n"
        if transferler:
            for t in transferler:
                wp_metin += f"👉 {t['borclu']} ➔ {t['alacakli']}: *{t['tutar']:,.2f} TL*\n"
        else:
            wp_metin += "Tüm hesaplar sıfırlandı! 🎉\n"
            
        st.text_area("Kopyalanabilir Özet:", value=wp_metin, height=180)
        encoded_wp = urllib.parse.quote(wp_metin)
        whatsapp_link = f"https://api.whatsapp.com/send?text={encoded_wp}"
        st.markdown(f'<a href="{whatsapp_link}" target="_blank"><button style="width:100%; padding:12px; background-color:#25D366; color:white; border:none; border-radius:10px; font-weight:bold; font-size:16px; cursor:pointer;">📲 WhatsApp Grubuna Gönder</button></a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# MENÜ 6: AYARLAR & YEDEKLEME
# -------------------------------------------------------------------
elif menu == "⚙️ Ayarlar & Yedekleme":
    st.header("⚙️ Genel Tatil & Ortak Havuz Ayarları")
    
    st.subheader("🗓️ Genel Tatil Tarih Aralığı")
    yeni_tarihler = st.date_input(
        "Tatil Başlangıç ve Bitiş Tarihi:",
        value=(st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
    )
    if st.button("Tarih Aralığını Güncelle"):
        if isinstance(yeni_tarihler, (list, tuple)) and len(yeni_tarihler) == 2:
            st.session_state.tatil_baslangic, st.session_state.tatil_bitis = yeni_tarihler
            ortak_verileri_kaydet(st.session_state.kisiler, st.session_state.harcamalar, st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
            st.success("Tatil tarihleri ortak havuza kaydedildi!")
            st.rerun()

    st.markdown("---")
    st.subheader("💾 Verileri İndir / Yedek Al")
    st.caption("Tatil verilerinizi tek tıkla telefonunuza veya bilgisayarınıza JSON formatında indirebilirsiniz.")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        db_json_data = f.read()
    st.download_button(
        label="📥 Tüm Tatil Verilerini İndir (JSON Yedek)",
        data=db_json_data,
        file_name="tatil_verileri_yedek.json",
        mime="application/json"
    )

    st.markdown("---")
    st.subheader("🔑 Gemini API Anahtarı")
    yeni_key = st.text_input("Gemini API Key:", value=st.session_state.gemini_api_key, type="password")
    if st.button("API Key Kaydet"):
        st.session_state.gemini_api_key = yeni_key
        st.success("API Anahtarı kaydedildi!")

    st.markdown("---")
    st.subheader("⚠️ Ortak Havuzu Sıfırla")
    st.caption("Dikkat: Bu işlem ortak veritabanındaki tüm kişileri ve harcamaları herkes için sıfırlar.")
    if st.button("🗑️ Tüm Verileri Sıfırla (Herkes İçin)", type="primary"):
        st.session_state.kisiler = []
        st.session_state.harcamalar = []
        st.session_state.fisten_okunanlar = []
        ortak_verileri_kaydet([], [], st.session_state.tatil_baslangic, st.session_state.tatil_bitis)
        st.rerun()
