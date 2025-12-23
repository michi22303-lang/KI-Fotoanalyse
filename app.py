import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim
import urllib.parse
import io

# --- KONFIGURATION ---
st.set_page_config(page_title="FM-Fix Pro", page_icon="⚓", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* Kamera Maximieren */
    [data-testid="stCameraInput"] > div { width: 100% !important; aspect-ratio: 3/4 !important; }
    [data-testid="stCameraInput"] video { object-fit: cover; }
    
    /* Buttons optimieren */
    .stButton>button, .stDownloadButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        font-weight: bold;
        border: none;
    }
    /* Primär-Button Farbe */
    a[kind="primary"] { 
        background-color: #003063 !important; 
        color: white !important;
        text-align: center;
        display: block;
        padding: 0.8em;
        border-radius: 12px;
        text-decoration: none;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
MODEL_NAME = 'gemini-2.0-flash-exp'

# --- STATE INITIALISIERUNG ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None
if 'captured_image' not in st.session_state: st.session_state.captured_image = None
if 'manual_address' not in st.session_state: st.session_state.manual_address = ""
if 'location_context' not in st.session_state: st.session_state.location_context = {}

def reset_wizard():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# --- HELFER ---
@st.cache_data(ttl=60)
def resolve_address(lat, lon):
    try:
        geolocator = Nominatim(user_agent="fm_fix_final", timeout=5)
        location = geolocator.reverse(f"{lat}, {lon}", zoom=18)
        if location and location.address:
            parts = location.address.split(",")
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
    1. Erkenne das technische Objekt exakt (Heizung, Fenster, Whiteboard, Bodenbelag etc.).
    2. Erstelle eine kurze Meldung für das Backoffice.

    Format (NUR DIESEN TEXT):
    GEWERK: [Gewerk]
    ORT: [Raum/Etage aus Kontext]
    MANGEL: [Präzise Beschreibung]
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
    
    # 1. Standort (Fehlerfreier Aufruf)
    loc = get_geolocation() 
    
    detected_address = ""
    gps_info = "Suche GPS..."

    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        resolved = resolve_address(lat, lon)
        if resolved:
            detected_address = resolved
            gps_info = "✅ GPS aktiv"
            if st.session_state.manual_address == "":
                st.session_state.manual_address = detected_address
    else:
        gps_info = "⚠️ Kein GPS"

    st.info(f"Schritt 1: Ort ({gps_info})")

    # Formular
    address_input = st.text_input("Adresse", value=st.session_state.manual_address, placeholder="Straße Hausnummer")
    st.session_state.manual_address = address_input

    c_f, c_r = st.columns(2)
    with c_f: floor = st.selectbox("Etage", ["UG", "EG", "1. OG", "2. OG", "3. OG", "4. OG"], index=1)
    with c_r: room = st.text_input("Raum", placeholder="z.B. 204")

    st.markdown("---")
    
    # Kamera
    img_file = st.camera_input("Foto", label_visibility="visible")

    if img_file:
        if len(st.session_state.manual_address) < 3:
            st.error("Bitte Adresse prüfen!")
        else:
            st.session_state.captured_image = Image.open(img_file)
            st.session_state.location_context = {"addr": st.session_state.manual_address, "floor": floor, "room": room}
            st.session_state.step = 2
            st.rerun()

# ==========================================
# SCHRITT 2: ANALYSE & SENDEN
# ==========================================
elif st.session_state.step == 2:
    st.info("Schritt 2: Bericht senden")
    
    # Bild anzeigen
    if st.session_state.captured_image:
        st.image(st.session_state.captured_image, use_container_width=True)

    # KI Analyse
    if st.session_state.analysis_result is None:
        with st.status("KI analysiert...", expanded=True) as status:
            try:
                ctx = f"Adresse: {st.session_state.location_context['addr']}, {st.session_state.location_context['floor']}, {st.session_state.location_context['room']}"
                res = analyze_image(st.session_state.captured_image, ctx)
                st.session_state.analysis_result = res
                status.update(label="Fertig!", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Fehler: {e}")
                status.update(label="Fehler", state="error")

    # Ergebnis & Buttons
    if res := st.session_state.analysis_result:
        
        # 1. Ergebnis Box
        st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:8px; border-left: 5px solid #003063; margin-bottom: 20px;">
            <pre style="font-family:sans-serif; white-space:pre-wrap; margin:0;">{res}</pre>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. Bild für Download vorbereiten (Workaround für Mail-Anhang)
        img_buffer = io.BytesIO()
        st.session_state.captured_image.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        # 3. Mail Link bauen
        subject = f"Mangel: {st.session_state.location_context['addr']}"
        body = f"Moin,\n\nOrt: {st.session_state.location_context['addr']}\nBereich: {st.session_state.location_context['floor']} / {st.session_state.location_context['room']}\n\n{res}\n\n(Foto bitte manuell einfügen)"
        mail_link = f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

        # 4. Action Buttons
        col1, col2 = st.columns(2)
        
        with col1:
            # Download Button (Damit man das Bild fürs Anhängen hat)
            st.download_button(
                label="💾 1. Foto speichern",
                data=img_bytes,
                file_name="mangel.jpg",
                mime="image/jpeg"
            )
            
        with col2:
            # Mail Button
            st.markdown(f'<a href="{mail_link}" kind="primary">✉️ 2. Mail App</a>', unsafe_allow_html=True)
        
        st.caption("ℹ️ iOS erlaubt keine automatischen Anhänge im Browser. Bitte Foto speichern und in der Mail einfügen.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🔄 Neuer Fall", on_click=reset_wizard)
