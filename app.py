import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import urllib.parse

# --- KONFIGURATION ---
st.set_page_config(page_title="FM-Fix Pro", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* Kamera Maximieren */
    [data-testid="stCameraInput"] > div { width: 100% !important; aspect-ratio: 3/4 !important; }
    [data-testid="stCameraInput"] video { object-fit: cover; }
    
    /* Eingabefelder Touch-freundlich */
    .stSelectbox > div > div { height: 3em; align-items: center; }
    .stTextInput > div > div { height: 3em; align-items: center; }
    
    /* Wichtige Buttons hervorheben */
    button[kind="primary"] { 
        background-color: #003063 !important; 
        border: none !important;
        height: 3.5em !important;
        font-size: 1.1rem !important;
    }
    </style>
""", unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
MODEL_NAME = 'gemini-2.0-flash-exp'

# --- STATE ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'manual_address' not in st.session_state: st.session_state.manual_address = ""
if 'location_context' not in st.session_state: st.session_state.location_context = {}

def reset_wizard():
    st.session_state.step = 1
    st.session_state.captured_image = None
    st.session_state.analysis_result = None
    st.session_state.manual_address = ""
    st.rerun()

# --- HELFER ---
@st.cache_data(ttl=60)
def resolve_address(lat, lon):
    try:
        geolocator = Nominatim(user_agent="fm_fix_fallback_v2", timeout=5)
        location = geolocator.reverse(f"{lat}, {lon}", zoom=18)
        if location and location.address:
            parts = location.address.split(",")
            # Nimmt Straße und Hausnummer (Index 0 und 1)
            return f"{parts[0]}, {parts[1] if len(parts)>1 else ''}"
        return f"{lat}, {lon}"
    except:
        return ""

def analyze_image(image, context):
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    Rolle: Facility Management Experte.
    Kontext: {context}
    
    Aufgabe:
    1. Erkenne das technische Objekt exakt. (Unterscheide Heizung vs. Whiteboard, Riss vs. Schatten).
    2. Erstelle eine kurze Meldung.

    Format (NUR TEXT):
    GEWERK: [Gewerk]
    ORT: [Raum/Etage aus Kontext]
    MANGEL: [Beschreibung]
    PRIO: [1-5]
    VORSCHLAG: [Maßnahme]
    """
    return model.generate_content([prompt, image]).text.strip()

# --- UI HEADER ---
c1, c2 = st.columns([1, 6])
with c1: st.markdown("### ⚓")
with c2: st.markdown("### FM-Fix Pro")

# ==========================================
# SCHRITT 1: STANDORT & FOTO
# ==========================================
if st.session_state.step == 1:
    
    # --- KORREKTUR HIER: KEINE ARGUMENTE FÜR GEOLOCATION ---
    loc = get_geolocation() 
    
    detected_address = ""
    gps_info = "Suche Standort..."

    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        # Accuracy ist manchmal nicht verfügbar, daher fallback auf 0
        acc = loc['coords'].get('accuracy', 0)
        
        resolved = resolve_address(lat, lon)
        if resolved:
            detected_address = resolved
            gps_info = f"✅ GPS gefunden"
            # Wenn das Feld noch leer ist, fülle es automatisch
            if st.session_state.manual_address == "":
                st.session_state.manual_address = detected_address
    else:
        gps_info = "⚠️ Kein GPS (Bitte Adresse eingeben)"

    # --- FORMULAR ---
    st.info("Schritt 1: Wo ist der Mangel?")
    
    st.caption(gps_info)
    address_input = st.text_input("Adresse / Objekt", 
                                  value=st.session_state.manual_address, 
                                  placeholder="z.B. Hauptstraße 1")
    
    # Update Session State mit Eingabe
    st.session_state.manual_address = address_input

    # 2. Etage & Raum
    col_f, col_r = st.columns(2)
    with col_f:
        floor = st.selectbox("Etage", ["UG", "EG", "1. OG", "2. OG", "3. OG", "4. OG", "Dach"], index=1)
    with col_r:
        room = st.text_input("Raum", placeholder="z.B. Küche")

    st.markdown("---")
    
    # 3. Kamera (Groß)
    img_file = st.camera_input("Foto aufnehmen", label_visibility="visible")

    if img_file:
        # Validierung: Adresse muss da sein (GPS oder Manuell)
        if len(st.session_state.manual_address) < 3:
            st.error("Bitte erst eine Adresse eingeben!")
        else:
            st.session_state.captured_image = Image.open(img_file)
            st.session_state.location_context = {
                "addr": st.session_state.manual_address,
                "floor": floor,
                "room": room
            }
            st.session_state.step = 2
            st.rerun()

# ==========================================
# SCHRITT 2: CHECK & SEND
# ==========================================
elif st.session_state.step == 2:
    st.info("Schritt 2: Analyse")
    
    c_img, c_txt = st.columns([1,2])
    with c_img:
        st.image(st.session_state.captured_image, use_container_width=True)
    with c_txt:
        loc_data = st.session_state.location_context
        st.caption(f"📍 {loc_data['addr']}")
        st.caption(f"🏢 {loc_data['floor']} | {loc_data['room']}")

    # KI Analyse
    if st.session_state.analysis_result is None:
        with st.status("KI prüft Bild...", expanded=True) as status:
            try:
                ctx_str = f"Adresse: {loc_data['addr']}, Etage: {loc_data['floor']}, Raum: {loc_data['room']}"
                res = analyze_image(st.session_state.captured_image, ctx_str)
                st.session_state.analysis_result = res
                status.update(label="Fertig!", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Fehler: {e}")
                status.update(label="Fehler", state="error")

    # Ergebnis Anzeige
    if res := st.session_state.analysis_result:
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:8px; border-left: 5px solid #003063; margin-top:10px;">
            <pre style="font-family:sans-serif; white-space:pre-wrap; margin:0;">{res}</pre>
        </div>
        """, unsafe_allow_html=True)
        
        # Email Link
        subject = f"Mangel: {loc_data['addr']} ({loc_data['room']})"
        body = f"Hallo,\n\nOrt: {loc_data['addr']}\nBereich: {loc_data['floor']} - {loc_data['room']}\n\n{res}"
        
        safe_link = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("✉️ Bericht senden", safe_link, type="primary", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Startseite", on_click=reset_wizard, use_container_width=True)
