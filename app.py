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
    st.header("⚖️ Situazione Saldi e Rimborsi")

    if not df.empty:
        # 1. Calcolo dei saldi netti (la logica che avevamo già)
        saldi = {persona: 0.0 for persona in partecipanti}

        for index, riga in df.iterrows():
            pagante = riga["Pagante"]
            importo = float(riga["Importo"])
            lista_debitori = [nome.strip() for nome in riga["Partecipanti"].split(",")]
            
            if len(lista_debitori) > 0:
                quota = importo / len(lista_debitori)
                saldi[pagante] += importo
                for debitore in lista_debitori:
                    if debitore in saldi:
                        saldi[debitore] -= quota

        # Mostriamo il resoconto netto
        st.subheader("1. Bilancio Netto")
        for persona, saldo in saldi.items():
            saldo_arrotondato = round(saldo, 2)
            if saldo_arrotondato > 0.01:
                st.success(f"🟩 **{persona}** è in credito di {saldo_arrotondato}€")
            elif saldo_arrotondato < -0.01:
                st.error(f"🟥 **{persona}** è in debito di {abs(saldo_arrotondato)}€")

        st.divider()

        # 2. Algoritmo "Semplifica Debiti"
        st.subheader("2. Semplifica Debiti (Chi paga chi)")
        
        # Separiamo chi deve ricevere (creditori) da chi deve dare (debitori)
        creditori = []
        debitori = []
        for persona, saldo in saldi.items():
            if saldo > 0.01:
                creditori.append([persona, saldo])
            elif saldo < -0.01:
                debitori.append([persona, abs(saldo)])
                
        # Ordiniamo per facilitare gli incroci (dal debito/credito più alto al più basso)
        creditori.sort(key=lambda x: x[1], reverse=True)
        debitori.sort(key=lambda x: x[1], reverse=True)
        
        transazioni = []
        i = 0 # Indice creditori
        j = 0 # Indice debitori
        
        while i < len(creditori) and j < len(debitori):
            cred_nome, cred_importo = creditori[i]
            deb_nome, deb_importo = debitori[j]
            
            # L'importo da scambiare è il minimo tra il debito e il credito
            importo_scambiato = min(cred_importo, deb_importo)
            importo_scambiato = round(importo_scambiato, 2)
            
            transazioni.append((deb_nome, cred_nome, importo_scambiato))
            
            # Aggiorniamo i saldi residui dopo questa transazione virtuale
            creditori[i][1] -= importo_scambiato
            debitori[j][1] -= importo_scambiato
            
            # Se il creditore o il debitore ha azzerato il suo conto, passiamo al prossimo
            if creditori[i][1] < 0.01:
                i += 1
            if debitori[j][1] < 0.01:
                j += 1

        # Mostriamo i risultati
        if len(transazioni) > 0:
            for da, a, cifra in transazioni:
                st.warning(f"💸 **{da}** deve dare **{cifra}€** a **{a}**")
        else:
            st.info("🎉 I conti sono in pari! Nessuno deve dare soldi a nessuno.")
            
    else:
        st.info("Nessuna spesa registrata finora.")
