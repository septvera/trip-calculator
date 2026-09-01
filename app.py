import streamlit as st
import pandas as pd
from PIL import Image
import json, os, re, urllib.parse, requests
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
from google import genai

# ==========================================
# 🔑 1. API ANAHTARLARI
# ==========================================
DEFAULT_GEMINI_API_KEY = ""
DEFAULT_OWM_API_KEY = ""   # OpenWeatherMap — opsiyonel
DEFAULT_SEHIR = "Bodrum"

st.set_page_config(
    page_title="Akbük Tatil Hesaplayıcı",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 🎨 2. CSS & FONTS
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .stMarkdown, p, label,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
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
    .material-symbols-rounded, .material-symbols-sharp,
    .material-symbols-outlined, [class*="material-symbols"],
    [data-testid="stSidebarCollapseButton"] span,
    [data-testid="stIcon"],
    button span[class*="material-symbols"] {
        font-family: 'Material Symbols Rounded','Material Symbols Outlined','Material Icons' !important;
        font-style: normal !important; font-variant: normal !important;
        text-transform: none !important; line-height: 1 !important;
        display: inline-block !important;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
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
        box-shadow: 0 4px 12px rgba(0,131,143,0.25) !important;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 12px !important; overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
    }
    div[data-testid="stAlert"] {
        border-radius: 12px !important; font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌐 3. ORTAK VERİTABANI
# ==========================================
DB_FILE = "tatil_veritabani.json"
KATEGORILER = ["🛒 Market", "🍽️ Yemek / Restoran", "🍹 İçki / Eğlence",
               "🚗 Ulaşım", "🏠 Ev Giderleri", "💊 Diğer"]

def tarih_ser(obj):
    return obj.isoformat() if isinstance(obj, (date, datetime)) else obj

def tarih_oku(val, default):
    if not val: return default
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    if isinstance(val, str):
        try: return date.fromisoformat(val)
        except: return default
    if isinstance(val, int):
        return default + timedelta(days=max(0, val - 1))
    return default

def db_yukle():
    bugun = date.today()
    varsayilan = {
        "tatil_baslangic": bugun.isoformat(),
        "tatil_bitis": (bugun + timedelta(days=13)).isoformat(),
        "kisiler": [], "harcamalar": [],
        "sehir": DEFAULT_SEHIR
    }
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(varsayilan, f, ensure_ascii=False, indent=2)
        return varsayilan
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return varsayilan

def db_kaydet():
    kisiler_k = [{
        "İsim": k["İsim"],
        "Giriş": tarih_ser(k.get("Giriş", st.session_state.tatil_bas)),
        "Çıkış": tarih_ser(k.get("Çıkış", st.session_state.tatil_bit)),
        "Kalış Süresi": k.get("Kalış Süresi", "1 Gün")
    } for k in st.session_state.kisiler]

    harcamalar_k = [{
        "ID": h["ID"], "Açıklama": h["Açıklama"],
        "Tutar": float(h["Tutar"]), "Ödeyen": h["Ödeyen"],
        "Kategori": h.get("Kategori", "💊 Diğer"),
        "Dahil Olanlar": h.get("Dahil Olanlar", []),
        "Başlangıç": tarih_ser(h.get("Başlangıç", st.session_state.tatil_bas)),
        "Bitiş": tarih_ser(h.get("Bitiş", st.session_state.tatil_bit))
    } for h in st.session_state.harcamalar]

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "tatil_baslangic": tarih_ser(st.session_state.tatil_bas),
            "tatil_bitis": tarih_ser(st.session_state.tatil_bit),
            "kisiler": kisiler_k, "harcamalar": harcamalar_k,
            "sehir": st.session_state.get("sehir", DEFAULT_SEHIR)
        }, f, ensure_ascii=False, indent=2)

# ==========================================
# 🧠 4. SESSION STATE YÜKLEME
# ==========================================
db = db_yukle()
bugun_dt = date.today()
st.session_state.tatil_bas = tarih_oku(db.get("tatil_baslangic"), bugun_dt)
st.session_state.tatil_bit = tarih_oku(db.get("tatil_bitis"), bugun_dt + timedelta(days=13))
st.session_state.sehir = db.get("sehir", DEFAULT_SEHIR)

st.session_state.kisiler = []
for k in db.get("kisiler", []):
    g = tarih_oku(k.get("Giriş") or k.get("Geliş"), st.session_state.tatil_bas)
    c = tarih_oku(k.get("Çıkış") or k.get("Gidiş"), st.session_state.tatil_bit)
    st.session_state.kisiler.append({
        "İsim": k["İsim"], "Giriş": g, "Çıkış": c,
        "Kalış Süresi": f"{(c-g).days+1} Gün"
    })

st.session_state.harcamalar = []
for h in db.get("harcamalar", []):
    hb = tarih_oku(h.get("Başlangıç"), st.session_state.tatil_bas)
    hs = tarih_oku(h.get("Bitiş"), st.session_state.tatil_bit)
    st.session_state.harcamalar.append({
        "ID": h.get("ID", len(st.session_state.harcamalar)+1),
        "Açıklama": h["Açıklama"], "Tutar": float(h["Tutar"]),
        "Ödeyen": h["Ödeyen"],
        "Kategori": h.get("Kategori", "💊 Diğer"),
        "Dahil Olanlar": h.get("Dahil Olanlar", []),
        "Başlangıç": hb, "Bitiş": hs
    })

if "fisten_okunanlar" not in st.session_state:
    st.session_state.fisten_okunanlar = []
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = (
        st.secrets.get("GEMINI_API_KEY", DEFAULT_GEMINI_API_KEY)
        if hasattr(st, "secrets") else DEFAULT_GEMINI_API_KEY
    )
if "owm_api_key" not in st.session_state:
    st.session_state.owm_api_key = (
        st.secrets.get("OWM_API_KEY", DEFAULT_OWM_API_KEY)
        if hasattr(st, "secrets") else DEFAULT_OWM_API_KEY
    )

def get_gunler():
    bas, bit = st.session_state.tatil_bas, st.session_state.tatil_bit
    if bit < bas: bit = bas
    return [bas + timedelta(days=i) for i in range((bit-bas).days+1)]

# ==========================================
# 🤖 5. GEMINI FİŞ OKUMA
# ==========================================
def fis_oku(gorsel):
    api_key = st.session_state.gemini_api_key.strip()
    if not api_key:
        st.error("⚠️ Gemini API Anahtarı girilmemiş! Ayarlar menüsünden ekleyin.")
        return []
    try:
        client = genai.Client(api_key=api_key)
        prompt = """
        Görseldeki alışveriş fişindeki ürün/hizmet kalemlerini ve KDV dahil tutarlarını çıkar.
        TOPLAM, KDV, ARA TOPLAM, NAKİT, KREDİ KARTI satırlarını DAHİL ETME.
        Sadece ürün kalemlerini JSON listesi olarak döndür:
        [{"Açıklama": "Ürün Adı", "Tutar": 25.0}]
        """
        resp = client.models.generate_content(
            model="gemini-2.5-flash", contents=[gorsel, prompt])
        yanit = resp.text.strip()
        m = re.search(r'\[.*\]', yanit, re.DOTALL)
        raw = m.group(0) if m else yanit.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        st.error(f"Fiş okunurken hata: {e}")
        return []

# ==========================================
# 🌤️ 6. HAVA DURUMU
# ==========================================
def hava_durumu_getir(sehir, api_key):
    if not api_key or not api_key.strip():
        return None
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={sehir}&appid={api_key}&units=metric&lang=tr"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ==========================================
# 📊 7. BAKİYE HESAPLAMA (merkezi fonksiyon)
# ==========================================
def hesapla_bakiyeler():
    kisiler_dict = {k["İsim"]: k for k in st.session_state.kisiler}
    bakiyeler = {k: 0.0 for k in kisiler_dict}
    harcanan = {k: 0.0 for k in kisiler_dict}
    kullanim = {k: 0.0 for k in kisiler_dict}

    for h in st.session_state.harcamalar:
        odeyen = h["Ödeyen"]
        if odeyen not in bakiyeler:
            st.warning(f"⚠️ '{odeyen}' kişi listesinde bulunamadı — '{h['Açıklama']}' harcaması atlandı.")
            continue

        bakiyeler[odeyen] += h["Tutar"]
        harcanan[odeyen] += h["Tutar"]

        hb = h.get("Başlangıç", st.session_state.tatil_bas)
        hs = h.get("Bitiş", st.session_state.tatil_bit)
        gunler = [hb + timedelta(days=i) for i in range((hs-hb).days+1)]

        gecerli = []
        for gun in gunler:
            evde = [k for k, v in kisiler_dict.items()
                    if v.get("Giriş", st.session_state.tatil_bas) <= gun
                    <= v.get("Çıkış", st.session_state.tatil_bit)]
            odeyecek = [k for k in evde if k in h["Dahil Olanlar"]] if h.get("Dahil Olanlar") else evde
            if odeyecek:
                gecerli.append((gun, odeyecek))

        if not gecerli:
            hedef = h["Dahil Olanlar"] if h.get("Dahil Olanlar") else list(kisiler_dict.keys())
            hedef = [k for k in hedef if k in bakiyeler]
            if hedef:
                pay = h["Tutar"] / len(hedef)
                for k in hedef:
                    bakiyeler[k] -= pay
                    kullanim[k] += pay
        else:
            gunluk = h["Tutar"] / len(gecerli)
            for gun, odeyecek in gecerli:
                pay = gunluk / len(odeyecek)
                for k in odeyecek:
                    if k in bakiyeler:
                        bakiyeler[k] -= pay
                        kullanim[k] += pay

    return bakiyeler, harcanan, kullanim

# ==========================================
# 📱 8. ARAYÜZ
# ==========================================
st.title("🏖️ Tatil Harcama & Ev Takvimi")

col_s1, col_s2 = st.columns([3, 1])
with col_s1:
    st.caption("🟢 **Canlı Ortak Havuz Aktif** — Herkesin eklediği veriler anında senkronize olur.")
with col_s2:
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()

# ---- Sidebar Hava Durumu ----
owm_key = st.session_state.owm_api_key.strip()
if owm_key:
    hava = hava_durumu_getir(st.session_state.sehir, owm_key)
    if hava:
        desc = hava["weather"][0]["description"].capitalize()
        temp = hava["main"]["temp"]
        nem  = hava["main"]["humidity"]
        ruz  = hava["wind"]["speed"]
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"### 🌤️ {st.session_state.sehir} Hava Durumu")
        st.sidebar.markdown(f"**{desc}** — 🌡️ **{temp:.0f}°C**")
        st.sidebar.markdown(f"💧 Nem: %{nem} &nbsp;&nbsp; 💨 Rüzgar: {ruz} m/s")
        st.sidebar.markdown("---")

menu = st.sidebar.radio("Menü", [
    "📅 Ev Takvimi & Doluluk",
    "👥 Kişileri Yönet",
    "💸 Manuel Harcama Ekle",
    "📸 Fişten Yapay Zeka ile Ekle",
    "📊 Hesaplaşma & WhatsApp",
    "📈 Harcama Grafikleri",
    "⚙️ Ayarlar & Yedekleme"
])

gunler = get_gunler()

# -------------------------------------------------------------------
# MENÜ 1: TAKVİM
# -------------------------------------------------------------------
if menu == "📅 Ev Takvimi & Doluluk":
    st.header("📅 Kim Hangi Gün Evde?")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.info(f"🗓️ **Tatil:** {st.session_state.tatil_bas.strftime('%d.%m.%Y')} — {st.session_state.tatil_bit.strftime('%d.%m.%Y')} ({len(gunler)} Gün)")
    with c2:
        st.metric("Kayıtlı Kişi", len(st.session_state.kisiler))

    if not st.session_state.kisiler:
        st.warning("Henüz kişi eklenmedi. '👥 Kişileri Yönet' menüsünden başlayın.")
    else:
        gun_bas = [g.strftime("%d %b\n(%a)") for g in gunler]
        matris = {}
        for k in st.session_state.kisiler:
            g_in  = k.get("Giriş", st.session_state.tatil_bas)
            g_out = k.get("Çıkış", st.session_state.tatil_bit)
            satir = []
            for g in gunler:
                if g == g_in and g == g_out: satir.append("📥📤 Tek Gün")
                elif g == g_in:              satir.append("📥 Giriş")
                elif g == g_out:             satir.append("📤 Çıkış")
                elif g_in < g < g_out:       satir.append("✅ Tam Gün")
                else:                        satir.append("—")
            matris[k["İsim"]] = satir

        df_t = pd.DataFrame(matris, index=gun_bas).T
        df_t.loc["👥 TOPLAM"] = [
            f"{sum(1 for k in st.session_state.kisiler if k.get('Giriş', st.session_state.tatil_bas) <= g <= k.get('Çıkış', st.session_state.tatil_bit))} Kişi"
            for g in gunler
        ]
        st.dataframe(df_t, use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 Güne Göre Evdekileri Gör")
        sec_gun = st.date_input("Tarih Seçin:",
            value=st.session_state.tatil_bas,
            min_value=st.session_state.tatil_bas,
            max_value=st.session_state.tatil_bit)
        evde = [k["İsim"] for k in st.session_state.kisiler
                if k.get("Giriş", st.session_state.tatil_bas) <= sec_gun <= k.get("Çıkış", st.session_state.tatil_bit)]
        if evde:
            st.success(f"**{sec_gun.strftime('%d.%m.%Y %A')}** — Evde: **{', '.join(evde)}** ({len(evde)} kişi)")
        else:
            st.warning(f"**{sec_gun.strftime('%d.%m.%Y')}** günü evde kimse görünmüyor.")

# -------------------------------------------------------------------
# MENÜ 2: KİŞİLERİ YÖNET
# -------------------------------------------------------------------
elif menu == "👥 Kişileri Yönet":
    st.header("👥 Kişi Ekle & Takvim Tarihlerini Seç")
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("kisi_form", clear_on_submit=True):
            isim = st.text_input("Kişi Adı", placeholder="Baran, Bahar, Ali...").strip()
            st.markdown("**🗓️ Giriş ve Çıkış Tarihi:**")
            aralik = st.date_input("Tarih Aralığı",
                value=(st.session_state.tatil_bas, st.session_state.tatil_bit),
                min_value=st.session_state.tatil_bas - timedelta(days=60),
                max_value=st.session_state.tatil_bit + timedelta(days=60))
            ekle = st.form_submit_button("➕ Kişiyi Ekle", use_container_width=True)
            if ekle:
                if not isim:
                    st.error("İsim boş olamaz!")
                elif isim.lower() in [k["İsim"].lower() for k in st.session_state.kisiler]:
                    st.warning(f"'{isim}' zaten ekli!")
                elif isinstance(aralik, (list,tuple)) and len(aralik)==2:
                    g, c = aralik
                    st.session_state.kisiler.append({
                        "İsim": isim, "Giriş": g, "Çıkış": c,
                        "Kalış Süresi": f"{(c-g).days+1} Gün"
                    })
                    db_kaydet()
                    st.success(f"✅ {isim} ({g.strftime('%d.%m')} – {c.strftime('%d.%m')}) eklendi!")
                    st.rerun()
                else:
                    st.error("Lütfen hem giriş hem çıkış tarihini seçin!")

    with col2:
        st.subheader("📋 Kayıtlı Kişiler")
        if st.session_state.kisiler:
            df_k = pd.DataFrame([{
                "İsim": k["İsim"],
                "Giriş": k["Giriş"].strftime("%d.%m.%Y"),
                "Çıkış": k["Çıkış"].strftime("%d.%m.%Y"),
                "Kalış": k.get("Kalış Süresi","")
            } for k in st.session_state.kisiler])
            st.dataframe(df_k, use_container_width=True)
            sil_k = st.selectbox("🗑️ Silinecek Kişi:", [k["İsim"] for k in st.session_state.kisiler])
            if st.button("❌ Seçili Kişiyi Sil"):
                st.session_state.kisiler = [k for k in st.session_state.kisiler if k["İsim"] != sil_k]
                st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["Ödeyen"] != sil_k]
                db_kaydet()
                st.rerun()
        else:
            st.info("Henüz kişi eklenmedi.")

# -------------------------------------------------------------------
# MENÜ 3: MANUEL HARCAMA
# -------------------------------------------------------------------
elif menu == "💸 Manuel Harcama Ekle":
    st.header("💸 Manuel Harcama Ekle")
    if not st.session_state.kisiler:
        st.warning("⚠️ Önce '👥 Kişileri Yönet' menüsünden kişileri ekleyin!")
    else:
        isimler = [k["İsim"] for k in st.session_state.kisiler]
        with st.form("harcama_form", clear_on_submit=True):
            aciklama = st.text_input("Neye Harcandı?", placeholder="Market, Akşam Yemeği, Tekila...").strip()
            col_t, col_k = st.columns([1, 1])
            with col_t:
                tutar = st.number_input("Tutar (₺)", min_value=0.0, step=10.0, format="%.2f")
            with col_k:
                kategori = st.selectbox("Kategori", KATEGORILER)
            odeyen = st.selectbox("Parayı Kim Ödedi?", isimler)

            st.markdown("**🎯 Kimler dahil? (Boşsa evdeki herkes)**")
            dahil = st.multiselect("Dahil Olan Kişiler (Opsiyonel)", options=isimler)
            st.markdown("**📅 Hangi tarih aralığını kapsıyor?**")
            tar = st.date_input("Tarih Aralığı",
                value=(st.session_state.tatil_bas, st.session_state.tatil_bit),
                min_value=st.session_state.tatil_bas - timedelta(days=60),
                max_value=st.session_state.tatil_bit + timedelta(days=60))
            kaydet = st.form_submit_button("💾 Ortak Havuza Kaydet", use_container_width=True)
            if kaydet:
                if not aciklama or tutar <= 0:
                    st.error("Açıklama ve geçerli bir tutar giriniz!")
                else:
                    hb, hs = (tar if isinstance(tar,(list,tuple)) and len(tar)==2
                               else (tar[0], tar[0]) if isinstance(tar,(list,tuple)) else (tar, tar))
                    st.session_state.harcamalar.append({
                        "ID": len(st.session_state.harcamalar)+1,
                        "Açıklama": aciklama, "Tutar": tutar,
                        "Ödeyen": odeyen, "Kategori": kategori,
                        "Dahil Olanlar": dahil, "Başlangıç": hb, "Bitiş": hs
                    })
                    db_kaydet()
                    st.success(f"✅ '{aciklama}' ({tutar:.2f} ₺) kaydedildi!")
                    st.rerun()

        if st.session_state.harcamalar:
            st.markdown("---")
            st.subheader("📋 Kayıtlı Harcamalar")
            ozet = []
            for h in st.session_state.harcamalar:
                hb = h.get("Başlangıç", st.session_state.tatil_bas)
                hs = h.get("Bitiş", st.session_state.tatil_bit)
                tar_str = f"{hb.strftime('%d.%m')} – {hs.strftime('%d.%m')}" if isinstance(hb, (date,datetime)) else f"{hb}–{hs}"
                ozet.append({
                    "ID": h["ID"], "Açıklama": h["Açıklama"],
                    "Tutar (₺)": f"{h['Tutar']:,.2f} ₺",
                    "Kategori": h.get("Kategori","—"),
                    "Ödeyen": h["Ödeyen"],
                    "Kapsam": ", ".join(h["Dahil Olanlar"]) if h.get("Dahil Olanlar") else "Evdekiler",
                    "Tarihler": tar_str
                })
            st.dataframe(pd.DataFrame(ozet), use_container_width=True)
            st.metric("Toplam Harcama", f"{sum(h['Tutar'] for h in st.session_state.harcamalar):,.2f} ₺")
            sil_h = st.selectbox("🗑️ Silinecek Harcama:",
                [f"#{h['ID']} – {h['Açıklama']} ({h['Tutar']:.2f} ₺)" for h in st.session_state.harcamalar])
            if st.button("❌ Seçili Harcamayı Sil"):
                sid = int(sil_h.split(" – ")[0].replace("#",""))
                st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["ID"] != sid]
                db_kaydet()
                st.rerun()

# -------------------------------------------------------------------
# MENÜ 4: FİŞTEN AI İLE EKLE
# -------------------------------------------------------------------
elif menu == "📸 Fişten Yapay Zeka ile Ekle":
    st.header("📸 Fiş Fotoğrafından Otomatik Oku")
    st.info("Market, restoran veya tekel fişinizin fotoğrafını yükleyin. Gemini AI kalemleri otomatik ayıracaktır.")
    if not st.session_state.kisiler:
        st.warning("⚠️ Önce '👥 Kişileri Yönet' menüsünden kişileri ekleyin!")
    else:
        isimler = [k["İsim"] for k in st.session_state.kisiler]
        yuklenen = st.file_uploader("Fiş Görseli Seç veya Çek", type=["jpg","jpeg","png"])
        if yuklenen:
            gorsel = Image.open(yuklenen)
            st.image(gorsel, caption="Yüklenen Fiş", use_container_width=True)
            if st.button("🔍 Fişi Yapay Zeka ile Tara", type="primary", use_container_width=True):
                with st.spinner("Gemini fişi inceliyor..."):
                    okunan = fis_oku(gorsel)
                    if okunan:
                        st.session_state.fisten_okunanlar = okunan
                        st.success(f"🎉 {len(okunan)} kalem okundu!")
                    else:
                        st.warning("Okunabilir kalem bulunamadı.")

        if st.session_state.fisten_okunanlar:
            st.markdown("---")
            st.subheader("🛒 Okunan Kalemleri Düzenle & Kaydet")
            for i, kalem in enumerate(list(st.session_state.fisten_okunanlar)):
                with st.expander(f"📌 {kalem.get('Açıklama','Ürün')} — {kalem.get('Tutar',0.0):.2f} ₺", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        adi   = st.text_input("Ürün Adı", value=kalem.get("Açıklama",""), key=f"a{i}")
                        tutar = st.number_input("Tutar (₺)", value=float(kalem.get("Tutar",0)), format="%.2f", key=f"t{i}")
                        odeyen_f = st.selectbox("Parayı Kim Ödedi?", isimler, key=f"o{i}")
                    with c2:
                        kat_f  = st.selectbox("Kategori", KATEGORILER, key=f"k{i}")
                        dahil_f = st.multiselect("Kimlere? (Boşsa Herkes)", isimler, key=f"d{i}")
                        tar_f  = st.date_input("Tarih Aralığı",
                            value=(st.session_state.tatil_bas, st.session_state.tatil_bit), key=f"tr{i}")
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("✅ Ekle", key=f"e{i}", use_container_width=True):
                            hb, hs = (tar_f if isinstance(tar_f,(list,tuple)) and len(tar_f)==2
                                       else (tar_f[0], tar_f[0]) if isinstance(tar_f,(list,tuple)) else (tar_f, tar_f))
                            st.session_state.harcamalar.append({
                                "ID": len(st.session_state.harcamalar)+1,
                                "Açıklama": adi, "Tutar": tutar,
                                "Ödeyen": odeyen_f, "Kategori": kat_f,
                                "Dahil Olanlar": dahil_f, "Başlangıç": hb, "Bitiş": hs
                            })
                            st.session_state.fisten_okunanlar.pop(i)
                            db_kaydet()
                            st.rerun()
                    with cb2:
                        if st.button("🗑️ Yoksay", key=f"y{i}", use_container_width=True):
                            st.session_state.fisten_okunanlar.pop(i)
                            st.rerun()

# -------------------------------------------------------------------
# MENÜ 5: HESAPLAŞMA & WHATSAPP
# -------------------------------------------------------------------
elif menu == "📊 Hesaplaşma & WhatsApp":
    st.header("📊 Kim Kime Ne Kadar Ödemeli?")
    if not st.session_state.kisiler or not st.session_state.harcamalar:
        st.info("En az bir kişi ve bir harcama girmelisiniz.")
    else:
        bakiyeler, harcanan, kullanim = hesapla_bakiyeler()

        tablo = []
        for k in st.session_state.kisiler:
            isim = k["İsim"]
            net  = bakiyeler.get(isim, 0)
            durum = "🟢 Alacaklı" if net > 0.01 else ("🔴 Borçlu" if net < -0.01 else "⚪ Ödeşti")
            tablo.append({
                "Kişi": isim,
                "Ödediği (₺)": f"{harcanan.get(isim,0):,.2f} ₺",
                "Kullanım Payı (₺)": f"{kullanim.get(isim,0):,.2f} ₺",
                "Net Bakiye (₺)": f"{net:+,.2f} ₺",
                "Durum": durum
            })
        st.subheader("💰 Kişi Bazlı Bakiye")
        st.dataframe(pd.DataFrame(tablo), use_container_width=True)

        # Transfer Algoritması
        st.markdown("---")
        st.subheader("🤝 Transfer Listesi")
        borclular   = [{"k": k, "t": -b} for k, b in bakiyeler.items() if b < -0.01]
        alacaklilar = [{"k": k, "t":  b} for k, b in bakiyeler.items() if b >  0.01]
        i = j = 0
        transferler = []
        while i < len(borclular) and j < len(alacaklilar):
            ode = min(borclular[i]["t"], alacaklilar[j]["t"])
            if ode > 0.01:
                transferler.append((borclular[i]["k"], alacaklilar[j]["k"], ode))
            borclular[i]["t"]   -= ode
            alacaklilar[j]["t"] -= ode
            if borclular[i]["t"]   < 0.01: i += 1
            if alacaklilar[j]["t"] < 0.01: j += 1

        if transferler:
            for b, a, t in transferler:
                st.info(f"👉 **{b}** ➡️ **{a}** kişisine **{t:,.2f} ₺** gönderecek.")
        else:
            st.success("🎉 Herkes ödeşmiş!")

        # WhatsApp
        st.markdown("---")
        st.subheader("📲 WhatsApp Tatil Grubu Özeti")
        toplam = sum(h["Tutar"] for h in st.session_state.harcamalar)
        wp  = f"🏖️ *TATİL HESAPLAŞMA DÖKÜMÜ*\n"
        wp += f"📅 {st.session_state.tatil_bas.strftime('%d.%m')} – {st.session_state.tatil_bit.strftime('%d.%m.%Y')}\n"
        wp += f"💰 *Toplam Harcama:* {toplam:,.2f} TL\n\n"
        wp += "📊 *Kişi Bazlı Durum:*\n"
        for k in st.session_state.kisiler:
            n = bakiyeler.get(k["İsim"], 0)
            wp += f"• {k['İsim']}: {n:+,.2f} TL ({'Alacaklı' if n>0.01 else 'Borçlu' if n<-0.01 else 'Ödeşti'})\n"
        wp += "\n🤝 *Transfer Planı:*\n"
        if transferler:
            for b, a, t in transferler:
                wp += f"👉 {b} ➔ {a}: *{t:,.2f} TL*\n"
        else:
            wp += "Tüm hesaplar sıfırlandı! 🎉\n"
        st.text_area("Kopyalanabilir Özet:", value=wp, height=200)
        enc = urllib.parse.quote(wp)
        st.markdown(
            f'<a href="https://api.whatsapp.com/send?text={enc}" target="_blank">'
            f'<button style="width:100%;padding:12px;background:#25D366;color:white;border:none;'
            f'border-radius:10px;font-weight:bold;font-size:16px;cursor:pointer;">'
            f'📲 WhatsApp Grubuna Gönder</button></a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# MENÜ 6: GRAFİKLER (YENİ)
# -------------------------------------------------------------------
elif menu == "📈 Harcama Grafikleri":
    st.header("📈 Harcama Analizi & Grafikler")
    if not st.session_state.kisiler or not st.session_state.harcamalar:
        st.info("Grafik görmek için kişi ve harcama girmelisiniz.")
    else:
        bakiyeler, harcanan, kullanim = hesapla_bakiyeler()

        # 1. Kişi Bazlı Çubuk Grafik
        st.subheader("👤 Kişi Bazlı Ödedi vs. Kullandı")
        isimler = [k["İsim"] for k in st.session_state.kisiler]
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Cebinden Ödedi",
            x=isimler,
            y=[harcanan.get(i, 0) for i in isimler],
            marker_color="#00ACC1",
            text=[f"{harcanan.get(i,0):,.0f} ₺" for i in isimler],
            textposition="outside"
        ))
        fig_bar.add_trace(go.Bar(
            name="Hakkı / Kullandığı",
            x=isimler,
            y=[kullanim.get(i, 0) for i in isimler],
            marker_color="#FF7043",
            text=[f"{kullanim.get(i,0):,.0f} ₺" for i in isimler],
            textposition="outside"
        ))
        fig_bar.update_layout(
            barmode="group", template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis_title="Tutar (₺)", font=dict(family="Plus Jakarta Sans"),
            margin=dict(t=40, b=20)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # 2. Kategoriye Göre Pasta Grafik
        st.markdown("---")
        st.subheader("🗂️ Kategoriye Göre Harcama Dağılımı")
        kat_toplamlar = {}
        for h in st.session_state.harcamalar:
            kat = h.get("Kategori", "💊 Diğer")
            kat_toplamlar[kat] = kat_toplamlar.get(kat, 0) + h["Tutar"]

        if kat_toplamlar:
            fig_pie = px.pie(
                values=list(kat_toplamlar.values()),
                names=list(kat_toplamlar.keys()),
                color_discrete_sequence=px.colors.qualitative.Set3,
                hole=0.35
            )
            fig_pie.update_traces(
                textposition="inside", textinfo="percent+label",
                textfont_size=13
            )
            fig_pie.update_layout(
                font=dict(family="Plus Jakarta Sans"),
                legend=dict(orientation="h"),
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # 3. Günlük Harcama Trendi
        st.markdown("---")
        st.subheader("📅 Günlük Toplam Harcama Trendi")
        gun_toplamlar = {}
        for h in st.session_state.harcamalar:
            hb = h.get("Başlangıç", st.session_state.tatil_bas)
            hs = h.get("Bitiş", st.session_state.tatil_bit)
            if isinstance(hb, (date, datetime)) and isinstance(hs, (date, datetime)):
                n_gun = (hs - hb).days + 1
                gunluk = h["Tutar"] / n_gun
                for i in range(n_gun):
                    g = hb + timedelta(days=i)
                    g_str = g.strftime("%d.%m")
                    gun_toplamlar[g_str] = gun_toplamlar.get(g_str, 0) + gunluk

        if gun_toplamlar:
            gun_df = pd.DataFrame(
                sorted(gun_toplamlar.items(), key=lambda x: x[0]),
                columns=["Tarih", "Toplam (₺)"]
            )
            fig_line = px.line(
                gun_df, x="Tarih", y="Toplam (₺)",
                markers=True,
                line_shape="spline",
                color_discrete_sequence=["#00838F"]
            )
            fig_line.update_traces(
                line_width=3, marker_size=8,
                fill="tozeroy", fillcolor="rgba(0,131,143,0.08)"
            )
            fig_line.update_layout(
                template="plotly_white",
                font=dict(family="Plus Jakarta Sans"),
                yaxis_title="Tutar (₺)", xaxis_title="Gün",
                margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig_line, use_container_width=True)

# -------------------------------------------------------------------
# MENÜ 7: AYARLAR & YEDEKLEME
# -------------------------------------------------------------------
elif menu == "⚙️ Ayarlar & Yedekleme":
    st.header("⚙️ Ayarlar & Yedekleme")

    st.subheader("🗓️ Tatil Tarih Aralığı")
    yeni_tar = st.date_input("Başlangıç ve Bitiş:",
        value=(st.session_state.tatil_bas, st.session_state.tatil_bit))
    if st.button("Tarihleri Güncelle"):
        if isinstance(yeni_tar, (list, tuple)) and len(yeni_tar) == 2:
            st.session_state.tatil_bas, st.session_state.tatil_bit = yeni_tar
            db_kaydet()
            st.success("Tatil tarihleri kaydedildi!")
            st.rerun()

    st.markdown("---")
    st.subheader("🌤️ Hava Durumu Ayarı")
    yeni_sehir = st.text_input("Şehir Adı (Hava Durumu için):", value=st.session_state.sehir)
    yeni_owm   = st.text_input("OpenWeatherMap API Key (opsiyonel):",
        value=st.session_state.owm_api_key, type="password",
        help="https://openweathermap.org/api adresinden ücretsiz alabilirsiniz.")
    if st.button("Hava Durumu Ayarlarını Kaydet"):
        st.session_state.sehir = yeni_sehir
        st.session_state.owm_api_key = yeni_owm
        db_kaydet()
        st.success("Kaydedildi!")
        st.rerun()

    st.markdown("---")
    st.subheader("🔑 Gemini API Anahtarı")
    yeni_gem = st.text_input("Gemini API Key:", value=st.session_state.gemini_api_key, type="password")
    if st.button("Gemini Key Kaydet"):
        st.session_state.gemini_api_key = yeni_gem
        st.success("Kaydedildi!")

    st.markdown("---")
    st.subheader("💾 Veri Yedekleme")
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            json_data = f.read()
        st.download_button("📥 Tüm Verileri İndir (JSON)", data=json_data,
            file_name="tatil_yedek.json", mime="application/json")

    st.markdown("---")
    st.subheader("⚠️ Tüm Verileri Sıfırla")
    st.error("🚨 Bu işlem **GERİ ALINAMAZ** ve tüm kişi/harcama verilerini herkes için siler!")
    onay = st.text_input("Onaylamak için tam olarak **ONAYLA** yazın:")
    if st.button("🗑️ Tüm Verileri Sıfırla", type="primary"):
        if onay.strip() == "ONAYLA":
            st.session_state.kisiler = []
            st.session_state.harcamalar = []
            st.session_state.fisten_okunanlar = []
            db_kaydet()
            st.success("✅ Tüm veriler sıfırlandı.")
            st.rerun()
        else:
            st.error("❌ 'ONAYLA' yazmadan sıfırlama yapılamaz!")
