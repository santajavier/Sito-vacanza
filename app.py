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
                stringa_partecipanti = ", ".join([f"{p}:{q}" for p, q in quote_personalizzate.items()])
            else:
                # Formato standard per la divisione alla romana
                stringa_partecipanti = ", ".join(diviso_tra)

            nuova_spesa = pd.DataFrame([{
                "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Pagante": pagante,
                "Importo": importo,
                "Causale": causale,
                "Partecipanti": stringa_partecipanti,
                "Categoria": categoria
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
    st.subheader("👤 Dettaglio Quote Personali")
    st.write("Controlla la causale e l'esatto importo che ti è stato addebitato per ogni spesa.")
    
    # 1. Creiamo il menu a tendina
    persona_selezionata = st.selectbox("Seleziona un partecipante:", partecipanti, key="filtro_persona")
    
    if not df.empty:
        # 2. Troviamo tutte le righe dove la persona compare tra i partecipanti (deve pagare una quota)
        mask_coinvolto = df["Partecipanti"].astype(str).str.contains(persona_selezionata, na=False)
        df_coinvolto = df[mask_coinvolto].copy()
        
        if not df_coinvolto.empty:
            dettagli_personali = []
            
            # 3. Calcoliamo la quota esatta per ogni singola spesa
            for index, riga in df_coinvolto.iterrows():
                causale = riga["Causale"]
                importo_totale = float(riga["Importo"])
                partecipanti_str = str(riga["Partecipanti"])
                quota_finale = 0.0
                
                if ":" in partecipanti_str:
                    # Caso A: Quote personalizzate
                    voci = partecipanti_str.split(",")
                    for voce in voci:
                        if ":" in voce:
                            nome_debitore, quota_str = voce.split(":")
                            if nome_debitore.strip() == persona_selezionata:
                                quota_finale = float(quota_str)
                else:
                    # Caso B: Divisione alla romana (con centesimo fantasma)
                    lista_debitori = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip() != ""]
                    num_debitori = len(lista_debitori)
                    
                    if num_debitori > 0 and persona_selezionata in lista_debitori:
                        importo_cents = int(round(importo_totale * 100))
                        quota_base_cents = importo_cents // num_debitori
                        resto_cents = importo_cents % num_debitori
                        
                        # Troviamo la posizione della persona per assegnare i centesimi extra
                        indice_persona = lista_debitori.index(persona_selezionata)
                        centesimi_extra = 1 if indice_persona < resto_cents else 0
                        quota_finale = (quota_base_cents + centesimi_extra) / 100.0
                
                # Salviamo solo Causale e Quota se l'importo è maggiore di zero
                if quota_finale > 0:
                    dettagli_personali.append({
                        "Causale": causale, 
                        "Quota Attribuita (€)": quota_finale
                    })
            
            # 4. Generiamo la tabella finale snella
            if dettagli_personali:
                df_dettaglio = pd.DataFrame(dettagli_personali)
                
                st.success(f"Trovate **{len(df_dettaglio)}** spese a carico di **{persona_selezionata}**.")
                
                # Mostriamo la tabella formattando la colonna in Euro
                st.dataframe(df_dettaglio.style.format({"Quota Attribuita (€)": "{:.2f} €"}), use_container_width=True)
                
                # Calcoliamo anche la somma di queste specifiche quote
                totale_quote = df_dettaglio["Quota Attribuita (€)"].sum()
                st.info(f"💡 Il totale complessivo addebitato in queste spese è di {totale_quote:.2f} €")
        else:
            st.warning(f"{persona_selezionata} non ha quote a suo carico.")
    
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
                if pwd_master == master_password:
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

    st.divider()
    st.subheader("✏️ Modifica una spesa")
    if not df.empty:
        opzioni_modifica = [f"Riga {i} - {row['Causale']} ({row['Importo']}€)" for i, row in df.iterrows()]
        spesa_da_mod = st.selectbox("Seleziona la spesa da modificare", opzioni_modifica, key="sel_mod")
        
        # Estraiamo l'indice e i dati attuali
        indice_mod = int(spesa_da_mod.split(" ")[1])
        riga_attuale = df.loc[indice_mod]
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            nuovo_pagante = st.selectbox("Pagante", partecipanti, index=partecipanti.index(riga_attuale["Pagante"]) if riga_attuale["Pagante"] in partecipanti else 0, key="mod_pag")
            nuovo_importo = st.number_input("Importo (€)", min_value=0.0, step=0.5, value=float(riga_attuale["Importo"]), key="mod_imp")
        with col_m2:
            nuova_causale = st.text_input("Causale", value=riga_attuale["Causale"], key="mod_caus")
            nuova_categoria = st.text_input("Categoria", value=riga_attuale.get("Categoria", ""), key="mod_cat")
            
        st.info("💡 Per modificare le quote esatte dei partecipanti, ti consigliamo di eliminare e reinserire la spesa.")
        
        col_mp1, col_mp2 = st.columns(2)
        with col_mp1:
            pwd_mod = st.text_input("Master Password per confermare", type="password", key="pwd_mod")
        with col_mp2:
            st.write("")
            st.write("")
            if st.button("Salva Modifiche"):
                if pwd_mod == master_password:
                    df.at[indice_mod, "Pagante"] = nuovo_pagante
                    df.at[indice_mod, "Importo"] = nuovo_importo
                    df.at[indice_mod, "Causale"] = nuova_causale
                    if "Categoria" in df.columns:
                        df.at[indice_mod, "Categoria"] = nuova_categoria
                    
                    conn.update(spreadsheet=url_foglio, data=df)
                    st.success("✏️ Spesa aggiornata con successo!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Master Password errata!")

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
                # Es: "Michele, Luisa" (Divisione alla romana corretta al centesimo)
                lista_debitori = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip() != ""]
                num_debitori = len(lista_debitori)
                
                if num_debitori > 0:
                    # Trasformiamo l'importo in centesimi interi (es. 3.50 -> 350)
                    importo_cents = int(round(importo * 100))
                    
                    # Calcoliamo la quota base e il resto
                    quota_base_cents = importo_cents // num_debitori # Divisione senza virgola (es. 43)
                    resto_cents = importo_cents % num_debitori       # Il resto (es. 6 centesimi)
                    
                    for i, debitore in enumerate(lista_debitori):
                        # Diamo 1 centesimo extra ai primi della lista per smaltire il resto
                        centesimi_extra = 1 if i < resto_cents else 0
                        quota_finale = (quota_base_cents + centesimi_extra) / 100.0
                        
                        if debitore in saldi:
                            saldi[debitore] -= quota_finale

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

with tab_statistiche:
    st.header("📊 Statistiche Spese")
    
    if not df.empty:
        # Assicuriamoci che gli importi siano letti come numeri
        df["Importo"] = pd.to_numeric(df["Importo"])
        
        # --- FILTRO RIMBORSI ---
        # Creiamo un dataframe per le statistiche escludendo i rimborsi
        if "Categoria" in df.columns:
            df["Categoria"] = df["Categoria"].fillna("Altro")
            # Escludiamo le righe dove la categoria contiene la parola "rimbors"
            df_stat = df[~df["Categoria"].str.lower().str.contains("rimbors", na=False)].copy()
        else:
            df_stat = df.copy()

        st.caption("Le statistiche escludono automaticamente la categoria 'Rimborsi'.")
        
        # 1. Metrica: Totale Speso Reale
        totale_viaggio = df_stat["Importo"].sum()
        st.metric(label="💰 Totale speso dal gruppo (esclusi rimborsi)", value=f"{totale_viaggio:.2f} €")
        
        st.divider()
        
# --- SPESA REALE ATTRIBUITA PER CATEGORIA (STACKED BAR E TABELLA) ---
        st.subheader("🎯 Spesa Reale Attribuita per Categoria")
        st.write("Il dettaglio di quanto ha speso ogni persona, diviso per tipologia:")
        
        consumi_dettagliati = []
        
        # 1. Calcoliamo le quote di tutti riga per riga
        for index, riga in df_stat.iterrows():
            importo = float(riga["Importo"])
            cat = riga["Categoria"] if "Categoria" in df_stat.columns else "Altro"
            partecipanti_str = str(riga["Partecipanti"])
            
            if ":" in partecipanti_str:
                # Quote personalizzate
                voci = partecipanti_str.split(",")
                for voce in voci:
                    if ":" in voce:
                        nome_debitore, quota_str = voce.split(":")
                        nome_debitore = nome_debitore.strip()
                        consumi_dettagliati.append({"Persona": nome_debitore, "Categoria": cat, "Importo": float(quota_str)})
            else:
                # Divisione alla romana (con logica del centesimo fantasma per pareggiare i conti)
                lista_debitori = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip() != ""]
                num_debitori = len(lista_debitori)
                
                if num_debitori > 0:
                    importo_cents = int(round(importo * 100))
                    quota_base_cents = importo_cents // num_debitori
                    resto_cents = importo_cents % num_debitori
                    
                    for i, debitore in enumerate(lista_debitori):
                        centesimi_extra = 1 if i < resto_cents else 0
                        quota_finale = (quota_base_cents + centesimi_extra) / 100.0
                        consumi_dettagliati.append({"Persona": debitore, "Categoria": cat, "Importo": quota_finale})
        
        # 2. Raggruppiamo i dati e generiamo Grafico + Tabella
        if consumi_dettagliati:
            # Creiamo il dataframe
            df_consumi_det = pd.DataFrame(consumi_dettagliati)
            df_raggruppato = df_consumi_det.groupby(["Persona", "Categoria"])["Importo"].sum().reset_index()
            df_raggruppato["Importo"] = df_raggruppato["Importo"].round(2)
            
            # --- GRAFICO A COLONNE IN PILA CON PLOTLY ---
            fig_stacked = px.bar(
                df_raggruppato, 
                x="Persona", 
                y="Importo", 
                color="Categoria", 
                text="Importo",
                barmode="stack" # Costringe i blocchi a impilarsi in una singola colonna
            )
            
            # Miglioriamo l'estetica del grafico
            fig_stacked.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="",
                yaxis_title="Euro (€)",
                legend_title_text="Categoria"
            )
            fig_stacked.update_traces(textposition='inside', textfont=dict(color='white'))
            
            # Mostriamo il grafico
            st.plotly_chart(fig_stacked, use_container_width=True)
            
            st.divider()
            
            # --- TABELLA DETTAGLIATA ---
            st.write("📋 *Dettaglio in Tabella*")
            
            # Creiamo la tabella "pivot"
            df_pivot = df_raggruppato.pivot(index="Persona", columns="Categoria", values="Importo").fillna(0)
            
            # Aggiungiamo il Totale per persona e ordiniamo
            df_pivot["Totale (€)"] = df_pivot.sum(axis=1)
            df_pivot = df_pivot.sort_values(by="Totale (€)", ascending=False)
            
            # Mostriamo la tabella formattata
            st.dataframe(df_pivot.style.format("{:.2f} €"), use_container_width=True)            
        # 3. Grafico a TORTA per le Categorie
        st.subheader("🛍️ In cosa stiamo spendendo?")
        if "Categoria" in df_stat.columns:
            spese_per_categoria = df_stat.groupby("Categoria")["Importo"].sum().reset_index()
            
            fig = px.pie(spese_per_categoria, values='Importo', names='Categoria', hole=0.4)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.info("Inizia ad aggiungere qualche spesa per vedere i grafici!")
