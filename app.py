import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import urllib.parse

# --- KONFIGURATION & CSS (MOBILE OPTIMIZED) ---
st.set_page_config(page_title="FM-Fix Wizard", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    /* Container Ränder minimieren für Mobile */
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    /* VERSUCH: Kamera größer machen auf Mobile */
    [data-testid="stCameraInput"] > div {
        width: 100% !important;
        aspect-ratio: 3/4 !important; /* Hochformat erzwingen falls möglich */
    }
    [data-testid="stCameraInput"] video {
         object-fit: cover;
    }

    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3em;
        font-weight: 600;
    }
    /* Header kleiner */
    h1 { font-size: 1.5rem !important; margin-bottom: 0 !important; }
    h3 { font-size: 1.2rem !important; margin-top: 10px !important;}
    </style>
""", unsafe_allow_html=True)

# --- SETUP ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("⚠️ API Key fehlt!")

# Wir bleiben bei Flash für Geschwindigkeit, verbessern aber den Prompt.
MODEL_NAME = 'gemini-2.0-flash-exp'

# --- STATE MANAGEMENT (WIZARD LOGIK) ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'captured_image' not in st.session_state:
    st.session_state.captured_image = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'current_address' not in st.session_state:
    st.session_state.current_address = "Wird ermittelt..."

def reset_wizard():
    st.session_state.step = 1
    st.session_state.captured_image = None
    st.session_state.analysis_result = None
    st.rerun()

# --- FUNKTIONEN ---
@st.cache_data(ttl=300)
def get_address_cached(lat, lon):
    try:
        geolocator = Nominatim(user_agent="fm_fix_wizard", timeout=10)
        location = geolocator.reverse(f"{lat}, {lon}")
        parts = location.address.split(",")
        # Versuch einer kurzen Adresse: Straße HNr, Stadtteil
        if len(parts) >= 4:
             return f"{parts[0].strip()},{parts[2].strip()}"
        return location.address
    except:
        return f"GPS: {lat:.4f}, {lon:.4f}"

# --- KI ANALYSE FUNKTION ---
def analyze_image(image, address):
    model = genai.GenerativeModel(MODEL_NAME)
    # NEUER PROMPT: "Chain of Thought" - Erst denken, dann formatieren.
    prompt = f"""
    Du bist ein erfahrener Facility Manager. Deine Aufgabe ist die visuelle Inspektion von Mängeln.
    Standort: {address}.

    Schritt 1: Analysiere das Bild visuell. Was ist das Hauptobjekt? (Unterscheide genau: Ein Whiteboard ist keine Heizung, ein Riss in der Wand ist kein Rohrbruch). In welchem Zustand ist es?
    
    Schritt 2: Basierend auf Schritt 1, extrahiere die Fakten in das geforderte Kurzformat.

    Gib NUR das finale Format aus Schritt 2 zurück (keine Einleitung):
    GEWERK: [z.B. Sanitär, Elektro, Bau, Reinigung]
    SCHADEN: [Präzise Beschreibung in max 5 Wörtern]
    PRIO: [Niedrig/Mittel/Hoch]
    MASSNAHME: [Vorschlag in max 5 Wörtern]
    """
    response = model.generate_content([prompt, image])
    return response.text.strip()

# --- APP START ---
c1, c2 = st.columns([1, 6])
with c1: st.markdown("### ⚓")
with c2: st.markdown("### FM-Fix Wizard")

# ==========================================
# WIZARD SCHRITT 1: STANDORT & FOTO
# ==========================================
if st.session_state.step == 1:
    st.info("Schritt 1: Foto aufnehmen")
    
    # Standort im Hintergrund
    loc = get_geolocation()
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        st.session_state.current_address = get_address_cached(lat, lon)
        st.caption(f"📍 {st.session_state.current_address}")

    # Die Kamera - möglichst groß durch CSS Hacks oben
    img_file = st.camera_input("Kamera", label_visibility="collapsed")

    if img_file:
        # Foto speichern und zum nächsten Schritt wechseln
        st.session_state.captured_image = Image.open(img_file)
        st.session_state.step = 2
        st.rerun() # Seite neu laden für Schritt 2

# ==========================================
# WIZARD SCHRITT 2: ANALYSE & VERSAND
# ==========================================
elif st.session_state.step == 2:
    st.info("Schritt 2: Überprüfen & Senden")
    
    # Kleineres Vorschaubild
    st.image(st.session_state.captured_image, width=200)

    # Automatische Analyse, falls noch nicht geschehen
    if st.session_state.analysis_result is None:
        with st.status("KI analysiert das Bild...", expanded=True) as status:
            try:
                result = analyze_image(st.session_state.captured_image, st.session_state.current_address)
                st.session_state.analysis_result = result
                status.update(label="Analyse abgeschlossen!", state="complete", expanded=False)
            except Exception as e:
                st.error(f"KI Fehler: {e}")
                status.update(label="Fehler bei Analyse", state="error")
    
    # Ergebnis anzeigen, wenn vorhanden
    if res := st.session_state.analysis_result:
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #003063;">
            <pre style="font-family: sans-serif; white-space: pre-wrap; margin: 0;">{res}</pre>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Abstand

        # Email vorbereiten
        subject = "FM-Meldung (Wizard)"
        body = f"Moin Backoffice,\n\nStandort: {st.session_state.current_address}\n\n{res}\n\nGesendet via FM-Fix."
        safe_body = urllib.parse.quote(body)
        safe_subject = urllib.parse.quote(subject)
        mail_link = f"mailto:backoffice@firma.de?subject={safe_subject}&body={safe_body}"

        # Buttons nebeneinander
        col_send, col_reset = st.columns([2, 1])
        with col_send:
            st.link_button("✉️ Meldung abschicken", mail_link, type="primary", use_container_width=True)
        with col_reset:
            st.button("🔄 Neu", on_click=reset_wizard, use_container_width=True)
