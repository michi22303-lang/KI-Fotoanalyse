import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import urllib.parse

# --- KONFIGURATION & CSS (MOBILE FIRST) ---
st.set_page_config(page_title="FM-Fix Mobile", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    /* Ränder auf dem Handy entfernen für mehr Platz */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    /* Button Styling: Groß und Touch-freundlich */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        background-color: #003063;
        color: white;
        font-size: 18px;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* Kamera-Label ausblenden */
    .stCameraInput > label { display: none; }
    /* Header kleiner machen */
    h1 { font-size: 1.8rem !important; margin-bottom: 0 !important; }
    </style>
""", unsafe_allow_html=True)

# --- SETUP ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ API Key fehlt in st.secrets")

MODEL_NAME = 'gemini-2.0-flash-exp' 

# --- CACHED FUNCTIONS (PERFORMANCE) ---
@st.cache_data(ttl=300) # Cache für 5 Minuten, spart API Calls
def get_address_cached(lat, lon):
    try:
        # Timeout erhöht für langsame Mobilverbindungen
        geolocator = Nominatim(user_agent="fm_fix_mobile_app", timeout=10)
        location = geolocator.reverse(f"{lat}, {lon}")
        # Adresse verkürzen (nur Straße + Stadt), spart Platz auf dem iPhone
        address_parts = location.address.split(",")
        short_address = f"{address_parts[0]},{address_parts[1]},{address_parts[3]}" if len(address_parts) > 3 else location.address
        return short_address
    except:
        return f"GPS: {lat:.4f}, {lon:.4f}"

# --- APP LOGIK ---

# Header Bereich (Kompakt)
c1, c2 = st.columns([1, 5])
with c1:
    st.markdown("# ⚓")
with c2:
    st.title("FM-Fix")
    st.caption("Schnellmeldung Hamburg")

# 1. Standort (Automatisch & Unauffällig)
loc = get_geolocation()
current_address = "Standort wird ermittelt..."

if loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
    current_address = get_address_cached(lat, lon)
    st.info(f"📍 {current_address}")
else:
    st.markdown("Waiting for GPS...")


# 2. Kamera (Der Fokus der App)
img_file = st.camera_input("Foto machen", label_visibility="collapsed")

if img_file:
    # Bild wird sofort angezeigt durch camera_input, wir laden es nur für Gemini
    img = Image.open(img_file)
    
    # Analyse Button
    if st.button("🚀 ANALYSIEREN"):
        # Status Container sieht auf Mobile besser aus als Spinner
        with st.status("KI wertet aus...", expanded=True) as status:
            try:
                model = genai.GenerativeModel(MODEL_NAME)
                
                # PROMPT OPTIMIERUNG: Maximale Kürze gefordert
                prompt = f"""
                Du bist ein technischer Assistent im Facility Management.
                Analysiere das Bild. Standort: {current_address}.
                
                Antworte NUR in diesem exakten Format (keine Einleitung, kein Markdown Fettgedruckt):
                
                GEWERK: [Nur das Gewerk]
                SCHADEN: [Maximal 5 Wörter Beschreibung]
                PRIO: [Niedrig/Mittel/Hoch]
                MASSNAHME: [Maximal 5 Wörter Aktion]
                """
                
                response = model.generate_content([prompt, img])
                result_text = response.text.strip()
                
                st.session_state['result'] = result_text
                status.update(label="Fertig!", state="complete", expanded=False)
                
            except Exception as e:
                st.error(f"Fehler: {e}")
                status.update(label="Fehler", state="error")

# 3. Ergebnis Anzeige (Karten-Stil für Mobile)
if 'result' in st.session_state and img_file:
    res = st.session_state['result']
    
    # Visuelle Darstellung als Info-Box
    st.markdown(f"""
    <div style="background-color: white; padding: 15px; border-radius: 10px; border-left: 5px solid #003063; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <pre style="font-family: sans-serif; white-space: pre-wrap; margin: 0;">{res}</pre>
    </div>
    """, unsafe_allow_html=True)

    # Email Vorbereitung (Sicher encodiert)
    subject = "FM-Meldung"
    body = f"Moin,\n\nStandort: {current_address}\n\n{res}\n\nGesendet via FM-Fix WebApp."
    
    # Sicherstellen, dass Umlaute und Leerzeichen funktionieren
    safe_body = urllib.parse.quote(body)
    safe_subject = urllib.parse.quote(subject)
    mail_link = f"mailto:?subject={safe_subject}&body={safe_body}"
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("✉️ An Backoffice senden", mail_link, type="primary")
