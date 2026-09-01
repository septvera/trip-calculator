import streamlit as st
import pandas as pd
from PIL import Image
import json
import re
import urllib.parse
from google import genai
from google.genai import types

# ==========================================
# 🔑 1. API ANAHTARI VE YAPILANDIRMA
# ==========================================
# Google AI Studio'dan aldığınız API Key'i buraya yapıştırabilirsiniz:
# https://aistudio.google.com/app/apikey (Ücretsizdir)
DEFAULT_GEMINI_API_KEY = ""

# Sayfa Yapılandırması (Mobil uyumlu)
st.set_page_config(
    page_title="Akbük Tatil Hesaplayıcı", 
    page_icon="🏖️", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==========================================
# 🧠 2. SESSION STATE (BELLEK) YÖNETİMİ
# ==========================================
if 'kisiler' not in st.session_state:
    st.session_state.kisiler = []
if 'harcamalar' not in st.session_state:
    st.session_state.harcamalar = []
if 'fisten_okunanlar' not in st.session_state:
    st.session_state.fisten_okunanlar = []
if 'toplam_gun' not in st.session_state:
    st.session_state.toplam_gun = 14
if 'gemini_api_key' not in st.session_state:
    # Öncelik sırası: Secrets -> Kod içi değişken -> Boş
    if "GEMINI_API_KEY" in st.secrets:
        st.session_state.gemini_api_key = st.secrets["GEMINI_API_KEY"]
    else:
        st.session_state.gemini_api_key = DEFAULT_GEMINI_API_KEY

# ==========================================
# 🤖 3. GEMINI VISION İLE FİŞ OKUMA FONKSİYONU
# ==========================================
def gemini_ile_fis_oku(gorsel):
    api_key = st.session_state.gemini_api_key.strip()
    if not api_key:
        st.error("⚠️ Lütfen geçerli bir Gemini API Anahtarı giriniz! (Yan menüdeki Ayarlar'dan veya kodun başından ekleyebilirsiniz.)")
        return []
    
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = """
        Sen uzman bir fiş ve fatura okuma asistanısın.
        Görseldeki alışveriş fişini incele. Satın alınan ürün/hizmet kalemlerini ve KDV dahil net tutarlarını çıkar.
        
        Kurallar:
        1. "TOPLAM", "KDV", "ARA TOPLAM", "NAKİT", "KREDİ KARTI", "FİŞ NO" gibi genel toplam satırlarını DAHİL ETME.
        2. Sadece satılan münferit ürün veya hizmet kalemlerini listele.
        3. Tutar rakamını float (ondalıklı sayı) olarak yaz (Örn: 45.50).
        4. Çıktı sadece ve sadece aşağıdaki geçerli JSON formatında bir liste olmalıdır:
        
        [
            {"Açıklama": "Ekmek 2 Adet", "Tutar": 25.0},
            {"Açıklama": "Beyaz Peynir", "Tutar": 140.75}
        ]
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[gorsel, prompt]
        )
        
        yanit_metni = response.text.strip()
        json_eslesme = re.search(r'\[.*\]', yanit_metni, re.DOTALL)
        if json_eslesme:
            veriler = json.loads(json_eslesme.group(0))
            return veriler
        else:
            temiz = yanit_metni.replace("```json", "").replace("```", "").strip()
            return json.loads(temiz)
            
    except Exception as e:
        st.error(f"Fiş okunurken bir hata oluştu: {str(e)}")
        return []

# ==========================================
# 📱 4. ARAYÜZ VE MENÜ
# ==========================================
st.title("🏖️ Tatil Harcama Bölüştürücü")
st.caption("Kimin hangi gün evde olduğunu ve harcama detaylarını hesaba katan adil hesaplaşma aracı.")

# Yan Menü
menu = st.sidebar.radio(
    "Menü", 
    ["👥 Kişileri Yönet", "💸 Manuel Harcama Ekle", "📸 Fişten Yapay Zeka ile Ekle", "📊 Hesaplaşma & WhatsApp", "⚙️ Ayarlar"]
)

# -------------------------------------------------------------------
# MENÜ 1: KİŞİLERİ YÖNET
# -------------------------------------------------------------------
if menu == "👥 Kişileri Yönet":
    st.header("👥 Kim, Hangi Günler Evde?")
    
    with st.form("kisi_ekle_form", clear_on_submit=True):
        isim = st.text_input("Kişi Adı (Örn: Baran, Bahar, Ali)").strip()
        gun_araligi = st.slider(
            "Evde Kalacağı Günler", 
            min_value=1, 
            max_value=st.session_state.toplam_gun, 
            value=(1, st.session_state.toplam_gun)
        )
        submit_kisi = st.form_submit_button("➕ Kişiyi Kaydet", use_container_width=True)
        
        if submit_kisi:
            mevcutlar = [k["İsim"].lower() for k in st.session_state.kisiler]
            if not isim:
                st.error("Lütfen bir isim yazın!")
            elif isim.lower() in mevcutlar:
                st.warning(f"'{isim}' zaten listede ekli!")
            else:
                st.session_state.kisiler.append({
                    "İsim": isim, 
                    "Geliş": gun_araligi[0], 
                    "Gidiş": gun_araligi[1],
                    "Gün Sayısı": gun_araligi[1] - gun_araligi[0] + 1
                })
                st.success(f"✅ {isim} ({gun_araligi[0]}. - {gun_araligi[1]}. gün) başarıyla eklendi!")

    if st.session_state.kisiler:
        st.subheader("📋 Kayıtlı Kişiler")
        df_k = pd.DataFrame(st.session_state.kisiler)
        st.dataframe(df_k, use_container_width=True)
        
        # Kişi Silme
        st.markdown("---")
        kisi_sil = st.selectbox("🗑️ Silmek İstediğiniz Kişi:", [k["İsim"] for k in st.session_state.kisiler])
        if st.button("❌ Seçili Kişiyi Sil", type="secondary"):
            st.session_state.kisiler = [k for k in st.session_state.kisiler if k["İsim"] != kisi_sil]
            st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["Ödeyen"] != kisi_sil]
            st.rerun()

# -------------------------------------------------------------------
# MENÜ 2: MANUEL HARCAMA EKLE
# -------------------------------------------------------------------
elif menu == "💸 Manuel Harcama Ekle":
    st.header("💸 Manuel Harcama Ekle")
    
    if not st.session_state.kisiler:
        st.warning("⚠️ Önce 'Kişileri Yönet' menüsünden kişileri ekleyin!")
    else:
        kisi_isimleri = [k["İsim"] for k in st.session_state.kisiler]
        
        with st.form("manuel_harcama_form", clear_on_submit=True):
            aciklama = st.text_input("Neye Harcandı?", placeholder="Örn: Akşam Yemeği, Su, Kahvaltılık").strip()
            tutar = st.number_input("Tutar (₺)", min_value=0.0, step=10.0, format="%.2f")
            odeyen = st.selectbox("Parayı Kim Ödedi?", kisi_isimleri)
            
            st.markdown("**🎯 Bu harcama KİMLERİ kapsıyor?**")
            st.caption("Boş bırakırsanız o günlerde evde olan herkese bölünür. Özel harcamalar (içki vb.) için sadece tüketenleri seçin.")
            dahil_olanlar = st.multiselect("Dahil Olan Kişiler (Opsiyonel)", options=kisi_isimleri)
            
            st.markdown("**📅 Hangi günleri kapsıyor?**")
            kullanim_araligi = st.slider(
                "Kullanım Günleri", 
                1, st.session_state.toplam_gun, 
                (1, st.session_state.toplam_gun)
            )
            
            submit_h = st.form_submit_button("💾 Harcamayı Kaydet", use_container_width=True)
            if submit_h:
                if not aciklama or tutar <= 0:
                    st.error("Lütfen açıklama ve geçerli bir tutar girin!")
                else:
                    st.session_state.harcamalar.append({
                        "ID": len(st.session_state.harcamalar) + 1,
                        "Açıklama": aciklama,
                        "Tutar": tutar,
                        "Ödeyen": odeyen,
                        "Dahil Olanlar": dahil_olanlar,
                        "Başlangıç": kullanim_araligi[0],
                        "Bitiş": kullanim_araligi[1]
                    })
                    st.success(f"✅ '{aciklama}' ({tutar:.2f} ₺) başarıyla kaydedildi!")

        # Kayıtlı Harcamalar ve Silme
        if st.session_state.harcamalar:
            st.markdown("---")
            st.subheader("📋 Kayıtlı Harcamalar")
            
            ozet_harcamalar = []
            for h in st.session_state.harcamalar:
                ozet_harcamalar.append({
                    "ID": h["ID"],
                    "Açıklama": h["Açıklama"],
                    "Tutar (₺)": f"{h['Tutar']:.2f}",
                    "Ödeyen": h["Ödeyen"],
                    "Özel Kapsam": ", ".join(h["Dahil Olanlar"]) if h["Dahil Olanlar"] else "Herkes",
                    "Günler": f"{h['Başlangıç']}-{h['Bitiş']}"
                })
            st.dataframe(pd.DataFrame(ozet_harcamalar), use_container_width=True)
            
            harcama_sil_id = st.selectbox(
                "🗑️ Silmek İstediğiniz Harcama:", 
                [f"#{h['ID']} - {h['Açıklama']} ({h['Tutar']:.2f} ₺)" for h in st.session_state.harcamalar]
            )
            if st.button("❌ Seçili Harcamayı Sil"):
                secili_id = int(harcama_sil_id.split(" - ")[0].replace("#", ""))
                st.session_state.harcamalar = [h for h in st.session_state.harcamalar if h["ID"] != secili_id]
                st.rerun()

# -------------------------------------------------------------------
# MENÜ 3: FİŞTEN YAPAY ZEKA İLE EKLE
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
                        st.warning("Fişte okunabilir kalem bulunamadı veya bir hata oluştu.")

        # Okunan Kalemleri Tek Tek Onaylama ve Düzenleme Arayüzü
        if st.session_state.fisten_okunanlar:
            st.markdown("---")
            st.subheader("🛒 Okunan Kalemleri Özelleştir ve Kaydet")
            st.caption("Her ürün için kimin ödediğini, kimlerin tükettiğini ve gün aralığını seçip kaydedin.")
            
            for i, kalem in enumerate(list(st.session_state.fisten_okunanlar)):
                with st.expander(f"📌 {kalem.get('Açıklama', 'Ürün')} — {kalem.get('Tutar', 0.0):.2f} ₺", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        kalem_adi = st.text_input("Ürün Adı", value=kalem.get('Açıklama', ''), key=f"ad_{i}")
                        kalem_tutar = st.number_input("Tutar (₺)", value=float(kalem.get('Tutar', 0.0)), format="%.2f", key=f"tut_{i}")
                        odeyen_fis = st.selectbox("Parayı Kim Ödedi?", kisi_isimleri, key=f"odeyen_{i}")
                    with col2:
                        dahiller_fis = st.multiselect("Kimlere Bölünsün? (Boşsa Herkes)", kisi_isimleri, key=f"dahil_{i}")
                        gunler_fis = st.slider("Kullanım Günleri", 1, st.session_state.toplam_gun, (1, st.session_state.toplam_gun), key=f"gun_{i}")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button(f"✅ Harcamalara Ekle", key=f"ekle_{i}", use_container_width=True):
                            st.session_state.harcamalar.append({
                                "ID": len(st.session_state.harcamalar) + 1,
                                "Açıklama": kalem_adi,
                                "Tutar": kalem_tutar,
                                "Ödeyen": odeyen_fis,
                                "Dahil Olanlar": dahiller_fis,
                                "Başlangıç": gunler_fis[0],
                                "Bitiş": gunler_fis[1]
                            })
                            st.session_state.fisten_okunanlar.pop(i)
                            st.rerun()
                    with col_b2:
                        if st.button(f"🗑️ Bu Kalemi Yoksay", key=f"sil_{i}", use_container_width=True):
                            st.session_state.fisten_okunanlar.pop(i)
                            st.rerun()

# -------------------------------------------------------------------
# MENÜ 4: HESAPLAŞMA & WHATSAPP
# -------------------------------------------------------------------
elif menu == "📊 Hesaplaşma & WhatsApp":
    st.header("📊 Kim Kime Ne Kadar Ödemeli?")
    
    if not st.session_state.kisiler or not st.session_state.harcamalar:
        st.info("Hesaplama yapabilmek için en az bir kişi ve bir harcama girmelisiniz.")
    else:
        bakiyeler = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        toplam_harcanan = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        kisi_kullanim_payi = {k["İsim"]: 0.0 for k in st.session_state.kisiler}
        
        # 1. Adım: Ödeyenlerin alacaklarını ekle
        for h in st.session_state.harcamalar:
            bakiyeler[h["Ödeyen"]] += h["Tutar"]
            toplam_harcanan[h["Ödeyen"]] += h["Tutar"]
            
            # 2. Adım: Harcamanın günlerinde aktif kişileri tespit et
            gecerli_gunler = []
            for gun in range(h["Başlangıç"], h["Bitiş"] + 1):
                o_gun_evdekiler = [k["İsim"] for k in st.session_state.kisiler if k["Geliş"] <= gun <= k["Gidiş"]]
                odeyecekler = [k for k in o_gun_evdekiler if k in h["Dahil Olanlar"]] if h.get("Dahil Olanlar") else o_gun_evdekiler
                if odeyecekler:
                    gecerli_gunler.append((gun, odeyecekler))
            
            # Eğer o günlerde kimse evde değilse genel dahil listesine böl
            if not gecerli_gunler:
                hedef_kisiler = h["Dahil Olanlar"] if h.get("Dahil Olanlar") else [k["İsim"] for k in st.session_state.kisiler]
                kisi_basi = h["Tutar"] / len(hedef_kisiler)
                for kisi in hedef_kisiler:
                    bakiyeler[kisi] -= kisi_basi
                    kisi_kullanim_payi[kisi] += kisi_basi
            else:
                gunluk_maliyet = h["Tutar"] / len(gecerli_gunler)
                for gun, odeyecekler in gecerli_gunler:
                    kisi_basi = gunluk_maliyet / len(odeyecekler)
                    for kisi in odeyecekler:
                        bakiyeler[kisi] -= kisi_basi
                        kisi_kullanim_payi[kisi] += kisi_basi

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

        # ==========================================
        # 💬 WHATSAPP ÖZET METNİ VE BUTONU
        # ==========================================
        st.markdown("---")
        st.subheader("📲 WhatsApp Tatil Grubu Özeti")
        
        toplam_grup_harcamasi = sum(h["Tutar"] for h in st.session_state.harcamalar)
        
        wp_metin = f"🏖️ *TATİL HESAPLAŞMA DÖKÜMÜ*\n"
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
            wp_metin += "Tüm hesaplar sıfırlandı, transfer gerekmiyor! 🎉\n"
            
        st.text_area("Kopyalanabilir Özet Metni:", value=wp_metin, height=200)
        
        encoded_wp = urllib.parse.quote(wp_metin)
        whatsapp_link = f"https://api.whatsapp.com/send?text={encoded_wp}"
        st.markdown(f'<a href="{whatsapp_link}" target="_blank"><button style="width:100%; padding:12px; background-color:#25D366; color:white; border:none; border-radius:8px; font-weight:bold; font-size:16px; cursor:pointer;">📲 WhatsApp Grubuna Gönder</button></a>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# MENÜ 5: AYARLAR & SIFIRLA
# -------------------------------------------------------------------
elif menu == "⚙️ Ayarlar":
    st.header("⚙️ Tatil ve Uygulama Ayarları")
    
    st.subheader("🔑 Gemini API Anahtarı")
    yeni_api_key = st.text_input(
        "Gemini API Key:", 
        value=st.session_state.gemini_api_key, 
        type="password", 
        placeholder="AIzaSy..."
    )
    if st.button("API Key Kaydet"):
        st.session_state.gemini_api_key = yeni_api_key
        st.success("API Anahtarı kaydedildi!")
        
    st.markdown("---")
    st.subheader("📅 Tatil Süresi")
    yeni_gun = st.number_input("Tatil Toplam Kaç Gün?", min_value=1, max_value=60, value=st.session_state.toplam_gun)
    if st.button("Gün Sayısını Güncelle"):
        st.session_state.toplam_gun = yeni_gun
        st.success(f"Tatil süresi {yeni_gun} gün olarak ayarlandı!")
        
    st.markdown("---")
    st.subheader("⚠️ Verileri Temizle")
    if st.button("🗑️ Tüm Verileri Sıfırla (Kişiler ve Harcamalar)", type="primary"):
        st.session_state.kisiler = []
        st.session_state.harcamalar = []
        st.session_state.fisten_okunanlar = []
        st.rerun()
