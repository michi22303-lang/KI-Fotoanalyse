import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# --- OPTIMIERTE IPHONE UI ---
st.set_page_config(page_title="FM-Fix 2.0", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        background-color: #003063; /* Dunkelblau (HH-Stil) */
        color: white;
        font-size: 18px;
        font-weight: bold;
        border: none;
        margin-top: 10px;
    }
    .stCameraInput > label { display: none; }
    div[data-testid="stStatusWidget"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- GEMINI 2.0 SETUP ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Bitte API Key in den Secrets hinterlegen!")

# Modell-Name für Gemini 2.0
MODEL_NAME = 'gemini-2.0-flash-exp'

# --- FUNKTIONEN ---
def get_address(lat, lon):
    try:
        geolocator = Nominatim(user_agent="fm_fix_hamburg")
        location = geolocator.reverse(f"{lat}, {lon}")
        return location.address
    except:
        return f"{lat}, {lon}"

# --- APP STRUKTUR ---
st.title("⚓ FM-Fix 2.0")
st.caption("Facility Management Prototyp Hamburg")

# 1. Standort-Erkennung
loc = get_geolocation()
current_address = "Suche Standort..."

if loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
    current_address = get_address(lat, lon)
    st.success(f"📍 {current_address}")

# 2. Kamera-Input (Groß für iPhone)
img_file = st.camera_input("Foto aufnehmen")

if img_file:
    img = Image.open(img_file)
    st.image(img, use_container_width=True)
    
    if st.button("🚀 SCHADEN ANALYSIEREN"):
        with st.spinner('Gemini 2.0 analysiert...'):
            try:
                model = genai.GenerativeModel(MODEL_NAME)
                prompt = f"""
                Analysiere diesen Mangel im Facility Management. 
                Standort des Objekts: {current_address}
                Erstelle einen Bericht für das Backoffice:
                1. GEWERK
                2. BESCHREIBUNG (präzise)
                3. DRINGLICHKEIT (1-5)
                4. REPARATUR-VORSCHLAG
                """
                response = model.generate_content([prompt, img])
                st.session_state['result'] = response.text
            except Exception as e:
                st.error(f"Modell-Fehler: {e}. Prüfe, ob {MODEL_NAME} verfügbar ist.")

    if 'result' in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state['result'])
        
        # Email Link
        body = f"Moin Backoffice,\n\nhier ein neuer Befund:\n\nOrt: {current_address}\n\n{st.session_state['result']}"
        mail_link = f"mailto:backoffice@firma.de?subject=FM-Meldung&body={body.replace(' ', '%20').replace('\n', '%0D%0A')}"
        
        st.link_button("📩 Per Mail melden", mail_link)
