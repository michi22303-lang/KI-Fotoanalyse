import streamlit as st
import google.generativeai as genai
from PIL import Image
from streamlit_js_eval import get_geolocation

# 1. Verbindung zu Gemini (Key kommt aus den Secrets)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Bitte den GEMINI_API_KEY in den Streamlit Cloud Secrets hinterlegen.")

model = genai.GenerativeModel('gemini-1.5-flash')

st.title("⚓ FM-Fix Hamburg")
st.subheader("Digitaler Mängel-Scanner")

# 2. Standort abfragen
loc = get_geolocation()
address_placeholder = st.empty()
if loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
    address_placeholder.info(f"📍 Standort erfasst: {lat}, {lon}")

# 3. Kamera nutzen
img_file = st.camera_input("Mangel für das Backoffice fotografieren")

if img_file:
    img = Image.open(img_file)
    st.image(img, caption="Vorschau", use_container_width=True)
    
    if st.button("KI-Bericht erstellen"):
        with st.spinner('Gemini analysiert...'):
            prompt = "Analysiere diesen Schaden im Facility Management. Nenne Gewerk, Schadensart, Priorität (1-5) und Handlungsempfehlung."
            response = model.generate_content([prompt, img])
            
            st.session_state['bericht'] = response.text
            st.markdown("### Analyse-Ergebnis")
            st.write(response.text)

    # 4. Email-Link generieren (Die einfachste Lösung ohne SMTP-Stress)
    if 'bericht' in st.session_state:
        empfaenger = "backoffice@deine-firma.de" # Hier anpassen!
        betreff = "Meldung_Mangel_Hamburg"
        body = f"Standort: {loc if loc else 'Unbekannt'}\n\nBericht:\n{st.session_state['bericht']}"
        
        # Erstellt einen Link, der die Mail-App auf dem iPhone öffnet
        mail_link = f"mailto:{empfaenger}?subject={betreff}&body={body.replace(' ', '%20')}"
        st.link_button("📩 Bericht per E-Mail senden", mail_link)
