import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import urllib.parse
import time

# --- KONFIGURATION ---
st.set_page_config(page_title="FM-Fix Pro", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    /* Kamera Styling */
    [data-testid="stCameraInput"] > div { width: 100% !important; aspect-ratio: 3/4 !important; }
    [data-testid="stCameraInput"] video { object-fit: cover; }
    /* Große Inputs für Mobile */
    .stSelectbox > div > div { height: 3em; }
    .stTextInput > div > div { height: 3em; }
    </style>
""", unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
MODEL_NAME = 'gemini-2.0-flash-exp'

# --- STATE MANAGEMENT ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'location_data' not in st.session_state: st.session_state.location_data = {"addr": "Suche...", "floor": "EG", "room": ""}

def reset_wizard():
    st.session_state.step = 1
    st.session_state.captured_image = None
    st.session_state.analysis_result = None
    st.rerun()

# --- HELFER: GENAUE ADRESSE ---
@st.cache_data(ttl=60) # Kurzes Caching für Bewegung
def resolve_address(lat, lon):
    try:
        # Timeout erhöht, Zoom Level 18 für Hausnummer-Genauigkeit
        geolocator = Nominatim(user_agent="fm_fix_pro_v2", timeout=10)
        location = geolocator.reverse(f"{lat}, {lon}", zoom=18) 
        
        # Adresse putzen
        if location and location.address:
            parts = location.address.split(",")
            # Versuche Straße + Hausnummer + PLZ zu greifen
            return f"{parts[0]}, {parts[1] if len(parts)>1 else ''}"
        return f"{lat}, {lon}"
    except:
        return f"GPS: {lat:.5f}, {lon:.5f}"

# --- KI ANALYSE ---
def analyze_image(image, context_text):
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    Rolle: Facility Management Experte.
    Kontext: {context_text}
    
    Aufgabe:
    1. Erkenne das technische Objekt/Problem genau (Vermeide Verwechslungen wie Whiteboard vs. Heizung).
    2. Erstelle eine strukturierte Meldung.

    Format (NUR DIESEN TEXT AUSGEBEN):
    GEWERK: [Gewerk]
    ORT: [Genauer Raum/Etage aus Kontext]
    MANGEL: [Kurze Beschreibung]
    PRIO: [1-5]
    VORSCHLAG: [Maßnahme]
    """
    return model.generate_content([prompt, image]).text.strip()

# --- HEADER ---
c1, c2 = st.columns([1, 6])
with c1: st.markdown("### ⚓")
with c2: st.markdown("### FM-Fix Pro")

# ==========================================
# SCHRITT 1: ORT & DETAILS (Der "Check-In")
# ==========================================
if st.session_state.step == 1:
    st.info("📍 Schritt 1: Standort & Details")
    
    # 1. GPS Abfrage mit 'enableHighAccuracy'
    # Hinweis: Auf dem iPhone muss der Browser Zugriff auf 'Genauer Standort' haben!
    loc = get_geolocation(enable_high_accuracy=True)
    
    gps_status = "⏳ Warte auf GPS..."
    
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        acc = loc['coords']['accuracy'] # Genauigkeit in Metern
        
        # Adresse auflösen
        addr = resolve_address(lat, lon)
        st.session_state.location_data["addr"] = addr
        
        # Farbliche Indikation der Genauigkeit
        if acc < 20:
            gps_status = f"✅ GPS Präzise ({int(acc)}m): {addr}"
        else:
            gps_status = f"⚠️ GPS Ungenau ({int(acc)}m): {addr}"
    
    st.write(gps_status)
    
    # 2. Etage & Raum (GPS Höhe ist unbrauchbar, daher manuell)
    col_floor, col_room = st.columns(2)
    with col_floor:
        floor = st.selectbox("Etage", ["UG", "EG", "1. OG", "2. OG", "3. OG", "4. OG", "Dach"], index=1)
    with col_room:
        room = st.text_input("Raum Nr. / Bez.", placeholder="z.B. 204 oder Küche")
    
    # Daten speichern für nächsten Schritt
    st.session_state.location_data["floor"] = floor
    st.session_state.location_data["room"] = room

    st.markdown("---")
    
    # 3. Kamera Starten
    img_file = st.camera_input("Beweisfoto aufnehmen", label_visibility="visible")

    if img_file:
        st.session_state.captured_image = Image.open(img_file)
        st.session_state.step = 2
        st.rerun()

# ==========================================
# SCHRITT 2: ANALYSE & ACTION
# ==========================================
elif st.session_state.step == 2:
    st.info("🚀 Schritt 2: Analyse")
    
    # Bild klein anzeigen
    st.image(st.session_state.captured_image, width=150)
    
    # Kontext für die KI zusammenbauen
    full_context = f"""
    Adresse: {st.session_state.location_data['addr']}
    Etage: {st.session_state.location_data['floor']}
    Raum: {st.session_state.location_data['room']}
    """

    # Automatische Analyse
    if st.session_state.analysis_result is None:
        with st.status("KI analysiert Bild & Standort...", expanded=True) as status:
            try:
                res = analyze_image(st.session_state.captured_image, full_context)
                st.session_state.analysis_result = res
                status.update(label="Fertig!", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Fehler: {e}")
                status.update(label="Error", state="error")

    # Ergebnis
    if res := st.session_state.analysis_result:
        st.markdown(f"""
        <div style="background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div style="font-weight:bold; color:#555; margin-bottom:5px;">📍 {st.session_state.location_data['floor']} | {st.session_state.location_data['room']}</div>
            <pre style="font-family: sans-serif; white-space: pre-wrap; margin: 0; font-size: 16px;">{res}</pre>
        </div>
        """, unsafe_allow_html=True)

        # Mail Link bauen
        subject = f"Mangel: {st.session_state.location_data['floor']} {st.session_state.location_data['room']}"
        body = f"Moin,\n\n{full_context}\n\nBEFUND:\n{res}\n\nGesendet mit FM-Fix Pro."
        
        mail_link = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        
        st.markdown("<br>", unsafe_allow_html=True)
        c_send, c_back = st.columns([2, 1])
        with c_send:
            st.link_button("✉️ Senden", mail_link, type="primary", use_container_width=True)
        with c_back:
            st.button("🔄 Neu", on_click=reset_wizard, use_container_width=True)
