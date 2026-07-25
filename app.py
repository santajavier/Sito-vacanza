import streamlit as st
import pandas as pd

# Impostazioni della pagina
st.set_page_config(page_title="Gestione Vacanza", page_icon="✈️", layout="centered")

st.title("✈️ La Nostra Vacanza")

# La lista del gruppo
partecipanti = [
    "Michele Napoli", "Guglfr", "Isu", "Evilra", "Lore", "Gallo"]

tab_spese, tab_itinerario = st.tabs(["💸 Spese & Debiti", "🗺️ Itinerario"])

with tab_spese:
    st.header("Aggiungi una nuova spesa")
    
    # Creiamo il modulo (form) per l'inserimento
    with st.form("form_spese", clear_on_submit=True):
        
        # Dividiamo in due colonne per un layout più compatto
        col1, col2 = st.columns(2)
        
        with col1:
            pagante = st.selectbox("Chi ha pagato?", partecipanti)
            importo = st.number_input("Importo (€)", min_value=0.0, step=0.5, format="%.2f")
            
        with col2:
            causale = st.text_input("Causale (es. Benzina, Cena)")
            # Di default tutti partecipano, ma l'utente può togliere le spunte
            diviso_tra = st.multiselect("Diviso tra chi?", partecipanti, default=partecipanti)
            
        # Il pulsante per inviare i dati
        inviato = st.form_submit_button("Inserisci Spesa", use_container_width=True)
        
        # Cosa succede quando si clicca il pulsante
        if inviato:
            if causale and importo > 0 and len(diviso_tra) > 0:
                st.success(f"✅ Spesa di {importo}€ per '{causale}' aggiunta da {pagante}!")
                st.info(f"Divisa tra {len(diviso_tra)} persone: {', '.join(diviso_tra)}")
                # (Qui in futuro scriveremo il codice per mandare i dati a Google Sheets)
            else:
                st.error("⚠️ Attenzione: compila la causale, inserisci un importo maggiore di 0 e seleziona almeno un partecipante.")
                
with tab_itinerario:
    st.header("Logistica")
    st.info("Qui metteremo le tappe del viaggio e i link utili.")