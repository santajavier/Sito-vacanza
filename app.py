import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Impostazioni della pagina
st.set_page_config(page_title="Gestione Vacanza", page_icon="✈️", layout="centered")
st.title("✈️ La Nostra Vacanza")

# 1. Connessione al database (Google Sheets)
# Sostituisci l'URL qui sotto con il link vero del tuo foglio Google!
url_foglio = "https://docs.google.com/spreadsheets/d/1vAycXFovunoRVwow8JX8bd5WhHfZmirP0ZxxfRI8kes/edit?hl=it&gid=0#gid=0"
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Lettura dei dati (leggiamo le prime 5 colonne)
try:
    df = conn.read(spreadsheet=url_foglio, usecols=[0, 1, 2, 3, 4])
except Exception as e:
    st.error("Errore di connessione al database. Controlla il link e i permessi!")
    st.stop()

# La lista del gruppo
partecipanti = [
    "Michele", "Luisa", "Beniamino", "Han", "Yu", "Luca", 
    "Nicola", "Ciccio", "Elvira", "Matilde", "Lorenzo", "Santa", "Cristina"
]

tab_spese, tab_bilanci, tab_itinerario = st.tabs(["💸 Spese", "⚖️ Bilanci", "🗺️ Itinerario"])

with tab_spese:
    st.header("Aggiungi una nuova spesa")
    
    with st.form("form_spese", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            pagante = st.selectbox("Chi ha pagato?", partecipanti)
            importo = st.number_input("Importo (€)", min_value=0.0, step=0.5, format="%.2f")
        with col2:
            causale = st.text_input("Causale (es. Benzina, Cena)")
            diviso_tra = st.multiselect("Diviso tra chi?", partecipanti, default=partecipanti)
            
        inviato = st.form_submit_button("Inserisci Spesa", use_container_width=True)
        
        if inviato:
            if causale and importo > 0 and len(diviso_tra) > 0:
                # Creiamo la nuova riga da aggiungere
                nuova_spesa = pd.DataFrame([{
                    "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Pagante": pagante,
                    "Importo": importo,
                    "Causale": causale,
                    "Partecipanti": ", ".join(diviso_tra)
                }])
                
                # Uniamo la nuova spesa ai dati esistenti (se il file era vuoto, il codice salta la riga delle intestazioni, quindi creiamo un df pulito per non avere errori)
                if df.empty:
                    df_aggiornato = nuova_spesa
                else:
                    df_aggiornato = pd.concat([df, nuova_spesa], ignore_index=True)
                
                # Scriviamo il foglio Google aggiornato
                conn.update(spreadsheet=url_foglio, data=df_aggiornato)
                
                st.success(f"✅ Spesa di {importo}€ aggiunta da {pagante}!")
                # Svuota la memoria temporanea e ricarica la pagina per far vedere il nuovo dato
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("⚠️ Compila la causale, inserisci un importo maggiore di 0 e seleziona almeno un partecipante.")

    st.divider()
    st.subheader("📊 Storico Spese")
    # Mostriamo la tabella con i dati reali presi da Google Sheets
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab_itinerario:
    st.header("Logistica")
    st.info("Qui metteremo le tappe del viaggio e i link utili.")

with tab_bilanci:
    st.header("⚖️ Situazione Saldi")

    if not df.empty:
        # 1. Inizializziamo il saldo netto di tutti a zero
        saldi = {persona: 0.0 for persona in partecipanti}

        # 2. Iteriamo su ogni riga del dataframe (ogni spesa)
        for index, riga in df.iterrows():
            pagante = riga["Pagante"]
            importo = float(riga["Importo"])
            
            # Trasformiamo la stringa "Beniamino, Han, Luca" in una vera lista Python
            lista_debitori = [nome.strip() for nome in riga["Partecipanti"].split(",")]
            
            # Divisione alla romana (per ora)
            if len(lista_debitori) > 0:
                quota = importo / len(lista_debitori)

                # Il pagante va in positivo (ha un credito)
                saldi[pagante] += importo
                
                # Tutti i partecipanti vanno in negativo (hanno un debito)
                for debitore in lista_debitori:
                    if debitore in saldi:
                        saldi[debitore] -= quota

        # 3. Mostriamo i saldi netti a schermo
        st.subheader("Chi deve avere e chi deve dare:")
        for persona, saldo in saldi.items():
            # Arrotondiamo per evitare problemi con i decimali di Python
            saldo_arrotondato = round(saldo, 2)
            
            if saldo_arrotondato > 0:
                st.success(f"🟩 **{persona}** deve ricevere {saldo_arrotondato}€")
            elif saldo_arrotondato < 0:
                st.error(f"🟥 **{persona}** deve dare {abs(saldo_arrotondato)}€")
        
        # Qui sotto, nel prossimo step, implementeremo il "Semplifica Debiti"
        
    else:
        st.info("Nessuna spesa registrata finora.")
