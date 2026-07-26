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

# --- SISTEMA DI LOGIN ---
if "autenticato" not in st.session_state:
    st.session_state["autenticato"] = False

if not st.session_state["autenticato"]:
    st.subheader("🔒 Accesso Riservato")
    password_inserita = st.text_input("Inserisci la password per entrare", type="password")
    
    if st.button("Entra"):
        # Sostituisci 'Vacanze2026' con la password che vuoi dare al gruppo
        if password_inserita == "Vacanze2026": 
            st.session_state["autenticato"] = True
            st.rerun()
        else:
            st.error("Password errata!")
    st.stop() # Questo comando impedisce a Python di leggere il resto del codice se non sei loggato!
# ------------------------

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
    
    # Usiamo un container normale invece del form, per avere l'aggiornamento in tempo reale dei campi
    st.subheader("Nuova Spesa")
    col1, col2 = st.columns(2)
    
    with col1:
        pagante = st.selectbox("Chi ha pagato?", partecipanti)
        importo = st.number_input("Importo Totale (€)", min_value=0.0, step=0.5, format="%.2f")
    with col2:
        causale = st.text_input("Causale (es. Benzina, Cena)")
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
                stringa_partecipanti = ", ".join([f"{p}:{q}" for p, q in quote_personalizzate.items()])
            else:
                # Formato standard per la divisione alla romana
                stringa_partecipanti = ", ".join(diviso_tra)

            nuova_spesa = pd.DataFrame([{
                "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Pagante": pagante,
                "Importo": importo,
                "Causale": causale,
                "Partecipanti": stringa_partecipanti
            }])
            
            df_aggiornato = nuova_spesa if df.empty else pd.concat([df, nuova_spesa], ignore_index=True)
            conn.update(spreadsheet=url_foglio, data=df_aggiornato)
            
            st.success("✅ Spesa registrata!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("⚠️ Compila tutti i campi richiesti.")

    st.divider()
    st.subheader("📊 Storico Spese")
    # Mostriamo la tabella con i dati reali presi da Google Sheets
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🗑️ Elimina una spesa")
    if not df.empty:
        # Creiamo un menu a tendina che mostra l'indice, la causale e l'importo
        opzioni_eliminazione = [f"Riga {i} - {row['Causale']} ({row['Importo']}€) pagata da {row['Pagante']}" for i, row in df.iterrows()]
        spesa_da_eliminare = st.selectbox("Seleziona la spesa da annullare", opzioni_eliminazione)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pwd_master = st.text_input("Master Password", type="password")
        with col_p2:
            st.write("") # Spazio vuoto per allineare il bottone
            st.write("")
            if st.button("Elimina Definitivamente"):
                # Sostituisci 'Admin123' con la TUA password segreta
                if pwd_master == "Admin123":
                    # Estraiamo l'indice della riga dalla stringa selezionata
                    indice_riga = int(spesa_da_eliminare.split(" ")[1])
                    
                    # Eliminiamo la riga dal dataframe
                    df_aggiornato = df.drop(index=indice_riga)
                    
                    # Riscriviamo il dataframe aggiornato su Google Sheets
                    conn.update(spreadsheet=url_foglio, data=df_aggiornato)
                    st.success("🗑️ Spesa eliminata con successo!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Master Password errata!")

with tab_itinerario:
    st.header("Logistica")
    st.info("Qui metteremo le tappe del viaggio e i link utili.")

with tab_bilanci:
    st.header("⚖️ Situazione Saldi e Rimborsi")

    if not df.empty:
        # 1. Inizializziamo i saldi a zero
        saldi = {persona: 0.0 for persona in partecipanti}

        for index, riga in df.iterrows():
            pagante = riga["Pagante"]
            importo = float(riga["Importo"])
            partecipanti_str = str(riga["Partecipanti"])
            
            # Il pagante va in positivo dell'intero importo sborsato
            if pagante in saldi:
                saldi[pagante] += importo
            
            # Controlliamo se è una spesa con quote personalizzate (c'è il ':')
            if ":" in partecipanti_str:
                # Es: "Michele:15.5, Luisa:10.0"
                voci = partecipanti_str.split(",")
                for voce in voci:
                    if ":" in voce:
                        nome_debitore, quota_str = voce.split(":")
                        nome_debitore = nome_debitore.strip()
                        quota = float(quota_str)
                        if nome_debitore in saldi:
                            saldi[nome_debitore] -= quota
            else:
                # Es: "Michele, Luisa" (Divisione alla romana)
                lista_debitori = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip() != ""]
                if len(lista_debitori) > 0:
                    quota = importo / len(lista_debitori)
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
