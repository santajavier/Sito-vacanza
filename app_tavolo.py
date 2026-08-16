import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px

# 1. Apriamo la cassaforte e leggiamo i dati
config = st.secrets["config"]
titolo_app = config["TITOLO_APP"]
url_foglio = config["URL_FOGLIO"]
password_accesso = config["PASSWORD_ACCESSO"]
master_password = config["MASTER_PASSWORD"]
partecipanti = config["PARTECIPANTI"]

# 2. Impostazioni pagina usando il titolo preso dalla cassaforte
st.set_page_config(page_title=titolo_app, page_icon="✈️", layout="centered")
st.title(titolo_app)

# 3. Connessione al database usando l'url preso dalla cassaforte
conn = st.connection("gsheets", type=GSheetsConnection)

# --- SISTEMA DI LOGIN ---
if "autenticato" not in st.session_state:
    st.session_state["autenticato"] = False

if not st.session_state["autenticato"]:
    st.subheader("🔒 Accesso Riservato")
    password_inserita = st.text_input("Inserisci la password per entrare", type="password")
    
    if st.button("Entra"):
        # Sostituisci 'Vacanze2026' con la password che vuoi dare al gruppo
        if password_inserita == password_accesso: 
            st.session_state["autenticato"] = True
            st.rerun()
        else:
            st.error("Password errata!")
    st.stop() # Questo comando impedisce a Python di leggere il resto del codice se non sei loggato!
# ------------------------

# 2. Lettura dei dati (leggiamo le prime 5 colonne)
try:
    df = conn.read(spreadsheet=url_foglio, usecols=[0, 1, 2, 3, 4, 5])
except Exception as e:
    st.error("Errore di connessione al database. Controlla il link e i permessi!")
    st.stop()


tab_spese, tab_bilanci, tab_statistiche = st.tabs(["💸 Spese", "⚖️ Bilanci", "📊 Statistiche"])

with tab_spese:
    st.header("Aggiungi una nuova spesa")
    
    # Usiamo un container normale invece del form, per avere l'aggiornamento in tempo reale dei campi
    st.subheader("Nuova Spesa")
    col1, col2 = st.columns(2)
    
    with col1:
        pagante = st.selectbox("Chi ha pagato?", partecipanti)
        importo = st.number_input("Importo Totale (€)", min_value=0.0, step=0.5, format="%.2f")
    with col2:
        causale = st.text_input("Causale (es. Benzina, Cena)")
        
        # --- NUOVA LOGICA CATEGORIE ---
        # Leggiamo le categorie già usate dal foglio (se esistono) ignorando le celle vuote
        categorie_esistenti = list(df["Categoria"].dropna().unique()) if "Categoria" in df.columns else []
        scelta_cat = st.selectbox("Macrocategoria", ["➕ Aggiungi nuova..."] + categorie_esistenti)
        
        if scelta_cat == "➕ Aggiungi nuova...":
            categoria = st.text_input("Scrivi la nuova categoria (es. Carburante, Cibo)")
        else:
            categoria = scelta_cat
        # ------------------------------
        
        diviso_tra = st.multiselect("Coinvolti nella spesa", partecipanti, default=partecipanti)

    divisione_uguale = st.checkbox("Dividi in parti uguali", value=True)
    
    quote_personalizzate = {}
    if not divisione_uguale and len(diviso_tra) > 0:
        st.write("Inserisci la quota esatta per ogni persona:")
        col_q1, col_q2 = st.columns(2)
        for i, persona in enumerate(diviso_tra):
            # Alterniamo le colonne per estetica
            if i % 2 == 0:
                with col_q1:
                    quote_personalizzate[persona] = st.number_input(f"Quota {persona} (€)", min_value=0.0, step=0.5, format="%.2f")
            else:
                with col_q2:
                    quote_personalizzate[persona] = st.number_input(f"Quota {persona} (€)", min_value=0.0, step=0.5, format="%.2f")

    if st.button("Inserisci Spesa", type="primary"):
        if causale and importo > 0 and len(diviso_tra) > 0:
            
            # Controllo validità quote personalizzate
            if not divisione_uguale:
                somma_quote = sum(quote_personalizzate.values())
                # Usiamo una tolleranza minima per evitare problemi di arrotondamento di Python
                if abs(somma_quote - importo) > 0.01:
                    st.error(f"⚠️ Attenzione! La somma delle quote ({somma_quote}€) non coincide con il totale ({importo}€).")
                    st.stop()
                
                # Salviamo le quote nel formato "Nome:10.5, Nome2:5.0"
