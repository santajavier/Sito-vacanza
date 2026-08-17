import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
from fpdf import FPDF

# 1. Apriamo la cassaforte e leggiamo i dati
config = st.secrets["config"]
titolo_app = config["TITOLO_APP"]
url_foglio = config["URL_FOGLIO"]
password_accesso = config["PASSWORD_ACCESSO"]
master_password = config["MASTER_PASSWORD"]
partecipanti = config["PARTECIPANTI"]

# Recuperiamo la lista dei link dalla sua sezione dedicata
link_paypal = st.secrets["paypal"]

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

    st.header("➕ Aggiungi Nuova Spesa")
    
    # Usiamo un container normale invece del form per avere l'aggiornamento in tempo reale
    col1, col2 = st.columns(2)

    with col1:
        st.write("💳 **Chi ha anticipato i soldi?**")
        paganti_selezionati = st.multiselect("Seleziona chi ha pagato", partecipanti, default=[partecipanti[0]], key="new_paganti")
        tipo_div_pag = st.radio("Come hanno diviso l'anticipo?", ["In parti uguali", "Quote personalizzate"], key="new_tipo_div_pag")
        
        nuovo_importo = st.number_input("Importo Totale (€)", min_value=0.0, step=0.5, value=0.0, key="new_imp")
        
        stringa_paganti = ""
        if tipo_div_pag == "In parti uguali":
            stringa_paganti = ", ".join(paganti_selezionati)
        else:
            st.caption("Inserisci la quota esatta anticipata da ciascuno:")
            quote_pag = {}
            # Usiamo colonne interne per affiancare gli input numerici
            cols_pag = st.columns(3)
            for i, p in enumerate(paganti_selezionati):
                with cols_pag[i % 3]:
                    quote_pag[p] = st.number_input(f"{p} (€)", min_value=0.0, step=0.5, value=0.0, key=f"new_qpag_{p}")
            
            stringa_paganti = ", ".join([f"{p}:{quote_pag[p]}" for p in paganti_selezionati])
            
            somma_pagata = sum(quote_pag.values())
            if abs(somma_pagata - nuovo_importo) > 0.01:
                st.warning(f"⚠️ Attenzione: la somma degli anticipi ({somma_pagata:.2f} €) non coincide con l'importo ({nuovo_importo:.2f} €).")

    with col2:
        st.write("🛒 **Dettagli Spesa**")
        # Qui sotto metterai i campi per Causale, Categoria e chi partecipa alla spesa (i debitori)
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
    st.header("💸 Riepilogo Spese")
    
    if not df.empty:
        # --- FILTRO PER CATEGORIA ---
        if "Categoria" in df.columns:
            # Recuperiamo tutte le categorie uniche dal foglio (ignorando le celle vuote)
            categorie_uniche = df["Categoria"].dropna().unique().tolist()
            # Aggiungiamo l'opzione per vedere tutto
            opzioni_filtro = ["Tutte le categorie"] + sorted(categorie_uniche)
            
            categoria_selezionata = st.selectbox("🔍 Filtra per categoria:", opzioni_filtro, key="filtro_cat_principale")
            
            # Applichiamo il filtro se non è selezionato "Tutte le categorie"
            if categoria_selezionata != "Tutte le categorie":
                df_mostrato = df[df["Categoria"] == categoria_selezionata].copy()
            else:
                df_mostrato = df.copy()
        else:
            df_mostrato = df.copy()
            
        # Mostriamo la tabella filtrata
        st.dataframe(df_mostrato, use_container_width=True)
        
        # Mostriamo il totale degli scontrini filtrati
        if not df_mostrato.empty:
            df_mostrato["Importo"] = pd.to_numeric(df_mostrato["Importo"])
            totale_mostrato = df_mostrato["Importo"].sum()
            st.caption(f"Totale spese in questa vista: **{totale_mostrato:.2f} €**")
    else:
        st.info("Nessuna spesa registrata.")

    st.divider()
    st.subheader("🏦 Estratto Conto Personale")
    st.write("Verifica al centesimo i tuoi movimenti: gli anticipi, i consumi reali e i rimborsi. Il saldo finale qui corrisponde esattamente al calcolo dei bilanci.")
    
    # 1. Selettore persona
    persona_selezionata = st.selectbox("Seleziona il tuo nome:", partecipanti, key="estratto_persona")
    
    if not df.empty:
        anticipi_personali = []
        consumi_personali = []
        rimborsi_in = []  # Soldi ricevuti (ero pagante del rimborso)
        rimborsi_out = [] # Soldi inviati (ero partecipante del rimborso)
        
        # 2. MOTORE DI CALCOLO UNICO
        for index, riga in df.iterrows():
            cat = riga.get("Categoria", "Altro")
            is_rimborso = "rimbors" in str(cat).lower()
            causale = riga["Causale"]
            importo_totale = float(riga["Importo"])
            
            # --- A. Calcolo di quanto ha ANTICIPATO (Pagante) ---
            paganti_str = str(riga["Pagante"])
            quota_anticipata = 0.0
            
            if ":" in paganti_str:
                for voce in paganti_str.split(","):
                    if ":" in voce:
                        nome, q = voce.split(":")
                        if nome.strip() == persona_selezionata:
                            quota_anticipata = float(q)
            else:
                lista_paganti = [n.strip() for n in paganti_str.split(",") if n.strip()]
                if persona_selezionata in lista_paganti:
                    num_paganti = len(lista_paganti)
                    imp_cents = int(round(importo_totale * 100))
                    quota_base = imp_cents // num_paganti
                    resto = imp_cents % num_paganti
                    idx = lista_paganti.index(persona_selezionata)
                    quota_anticipata = (quota_base + (1 if idx < resto else 0)) / 100.0
                    
            if quota_anticipata > 0:
                if is_rimborso:
                    # Se sono il pagante di un rimborso, significa che STO DANDO dei soldi a qualcuno
                    rimborsi_out.append({"Riga N.": index, "A chi ho inviato": str(riga["Partecipanti"]), "Importo (€)": quota_anticipata})
                else:
                    anticipi_personali.append({"Riga N.": index, "Causale": causale, "Categoria": cat, "Importo (€)": quota_anticipata})

            # --- B. Calcolo di quanto ha CONSUMATO (Partecipante) ---
            partecipanti_str = str(riga["Partecipanti"])
            quota_consumata = 0.0
            
            if ":" in partecipanti_str:
                for voce in partecipanti_str.split(","):
                    if ":" in voce:
                        nome, q = voce.split(":")
                        if nome.strip() == persona_selezionata:
                            quota_consumata = float(q)
            else:
                lista_debitori = [n.strip() for n in partecipanti_str.split(",") if n.strip()]
                if persona_selezionata in lista_debitori:
                    num_debitori = len(lista_debitori)
                    imp_cents = int(round(importo_totale * 100))
                    quota_base = imp_cents // num_debitori
                    resto = imp_cents % num_debitori
                    idx = lista_debitori.index(persona_selezionata)
                    quota_consumata = (quota_base + (1 if idx < resto else 0)) / 100.0
                    
            if quota_consumata > 0:
                if is_rimborso:
                    # Se sono il partecipante di un rimborso, significa che STO RICEVENDO soldi
                    rimborsi_in.append({"Riga N.": index, "Da chi ho ricevuto": str(riga["Pagante"]), "Importo (€)": quota_consumata})
                else:
                    consumi_personali.append({"Riga N.": index, "Causale": causale, "Categoria": cat, "Importo (€)": quota_consumata})

        # 3. TOTALI E METRICHE
        tot_anticipato = sum(item["Importo (€)"] for item in anticipi_personali)
        tot_consumato = sum(item["Importo (€)"] for item in consumi_personali)
        tot_rimborsi_in = sum(item["Importo (€)"] for item in rimborsi_in)
        tot_rimborsi_out = sum(item["Importo (€)"] for item in rimborsi_out)
        
        # Saldo Matematico: Anticipato (Credito) - Consumato (Debito) + Rimborsi in uscita (Credito verso il gruppo) - Rimborsi in entrata (Debito saldato)
        saldo_finale = tot_anticipato - tot_consumato + tot_rimborsi_out - tot_rimborsi_in
        
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        col_kpi1.metric("🛒 Spesa Effettiva", f"{tot_consumato:.2f} €", help="La tua quota di consumo reale.")
        col_kpi2.metric("💳 Hai Anticipato", f"{tot_anticipato:.2f} €", help="Soldi messi di tasca tua per il gruppo.")
        col_kpi3.metric("⚖️ Saldo Attuale", f"{saldo_finale:.2f} €", delta="In Credito" if saldo_finale > 0.01 else ("In Debito" if saldo_finale < -0.01 else "In Pari"), delta_color="normal" if saldo_finale >= 0 else "inverse")

        st.write("") # Spazio
        
        # --- GENERATORE PDF ---
        def genera_pdf_estratto():
            pdf = FPDF()
            pdf.add_page()
            # Intestazione
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, f"Estratto Conto: {persona_selezionata}", ln=True, align='C')
            pdf.ln(5)
            
            # Riepilogo Metriche (Usiamo EUR invece di € per evitare errori di codifica del font standard)
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 8, f"Spesa Effettiva (Consumi): {tot_consumato:.2f} EUR", ln=True)
            pdf.cell(0, 8, f"Totale Anticipato: {tot_anticipato:.2f} EUR", ln=True)
            pdf.cell(0, 8, f"Rimborsi Ricevuti: {tot_rimborsi_in:.2f} EUR | Rimborsi Inviati: {tot_rimborsi_out:.2f} EUR", ln=True)
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"SALDO ATTUALE: {saldo_finale:.2f} EUR", ln=True)
            pdf.ln(8)

            # Funzione interna per stampare le singole tabelle
            def stampa_sezione_pdf(titolo, lista, chiavi_extra):
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, titolo, ln=True)
                pdf.set_font("Arial", '', 10)
                if not lista:
                    pdf.cell(0, 6, "Nessun movimento registrato.", ln=True)
                else:
                    for item in lista:
                        valori = []
                        for k in chiavi_extra:
                            val = str(item.get(k, ""))
                            # Formattiamo l'importo
                            if k == "Importo (€)":
                                val = f"{float(val):.2f} EUR"
                            valori.append(val)
                        
                        riga = f"Riga {item['Riga N.']} | " + " | ".join(valori)
                        # Codifica sicura per evitare crash se ci sono accenti particolari nella causale
                        riga_sicura = riga.encode('latin-1', 'ignore').decode('latin-1')
                        pdf.cell(0, 6, riga_sicura, ln=True)
                pdf.ln(5)

            # Stampa le varie sezioni
            stampa_sezione_pdf("I TUOI ANTICIPI", anticipi_personali, ["Causale", "Categoria", "Importo (€)"])
            stampa_sezione_pdf("LE TUE QUOTE (CONSUMI)", consumi_personali, ["Causale", "Categoria", "Importo (€)"])
            stampa_sezione_pdf("RIMBORSI RICEVUTI", rimborsi_in, ["Da chi ho ricevuto", "Importo (€)"])
            stampa_sezione_pdf("RIMBORSI INVIATI", rimborsi_out, ["A chi ho inviato", "Importo (€)"])
            
            return pdf.output(dest="S").encode("latin-1")

        # Mostriamo il bottone di download centrato
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            st.download_button(
                label=f"📄 Scarica Estratto Conto (PDF)",
                data=genera_pdf_estratto(),
                file_name=f"Estratto_Conto_{persona_selezionata}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        st.write("") # Spazio finale prima delle schede

        # 4. LE TRE SOTTO-SCHEDE (TABS)
        tab_ant, tab_cons, tab_rimb = st.tabs(["💳 I tuoi Anticipi", "🛒 Le tue Quote (Consumi)", "🔄 Rimborsi"])
        
        with tab_ant:
            if anticipi_personali:
                df_ant = pd.DataFrame(anticipi_personali).set_index("Riga N.")
                
                # Filtro per categoria richiesto!
                categorie_anticipi = df_ant["Categoria"].unique().tolist()
                filtro_cat_ant = st.multiselect("Filtra anticipi per Categoria:", categorie_anticipi, default=categorie_anticipi, key="filtro_cat_ant")
                
                df_ant_filtrato = df_ant[df_ant["Categoria"].isin(filtro_cat_ant)]
                
                st.dataframe(df_ant_filtrato.style.format({"Importo (€)": "{:.2f} €"}), use_container_width=True)
                if not df_ant_filtrato.empty:
                    st.caption(f"Totale filtrato: **{df_ant_filtrato['Importo (€)'].sum():.2f} €**")
            else:
                st.info("Non hai ancora anticipato soldi per nessuna spesa.")
                
        with tab_cons:
            if consumi_personali:
                df_cons = pd.DataFrame(consumi_personali).set_index("Riga N.")
                
                # Stesso filtro opzionale anche qui per simmetria
                categorie_consumi = df_cons["Categoria"].unique().tolist()
                filtro_cat_cons = st.multiselect("Filtra quote per Categoria:", categorie_consumi, default=categorie_consumi, key="filtro_cat_cons")
                
                df_cons_filtrato = df_cons[df_cons["Categoria"].isin(filtro_cat_cons)]
                
                st.dataframe(df_cons_filtrato.style.format({"Importo (€)": "{:.2f} €"}), use_container_width=True)
                if not df_cons_filtrato.empty:
                    st.caption(f"Totale filtrato: **{df_cons_filtrato['Importo (€)'].sum():.2f} €**")
            else:
                st.info("Non hai ancora quote di spesa a tuo carico.")
                
        with tab_rimb:
            col_rin, col_rout = st.columns(2)
            with col_rin:
                st.write("**📥 Rimborsi Ricevuti**")
                if rimborsi_in:
                    df_rin = pd.DataFrame(rimborsi_in).set_index("Riga N.")
                    st.dataframe(df_rin.style.format({"Importo (€)": "{:.2f} €"}), use_container_width=True)
                else:
                    st.caption("Nessun rimborso ricevuto.")
            with col_rout:
                st.write("**📤 Rimborsi Inviati**")
                if rimborsi_out:
                    df_rout = pd.DataFrame(rimborsi_out).set_index("Riga N.")
                    st.dataframe(df_rout.style.format({"Importo (€)": "{:.2f} €"}), use_container_width=True)
                else:
                    st.caption("Nessun rimborso inviato.")
    
    st.divider()
    st.subheader("⚖️ Confronto Puntuale Spese")
    st.write("Verifica riga per riga gli importi addebitati a due persone per le categorie selezionate (Rimborsi esclusi).")

    if not df.empty:
        # --- FILTRO RIMBORSI E LETTURA CATEGORIE ---
        if "Categoria" in df.columns:
            df_confronto = df[~df["Categoria"].str.lower().str.contains("rimbors", na=False)].copy()
            categorie_disponibili = sorted(df_confronto["Categoria"].dropna().unique().tolist())
        else:
            df_confronto = df.copy()
            categorie_disponibili = ["Altro"]
            
        # --- MENU DI SELEZIONE ---
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            persona1 = st.selectbox("Prima persona", partecipanti, index=0, key="vs_p1_puntuale")
        with col_c2:
            persona2 = st.selectbox("Seconda persona", partecipanti, index=1 if len(partecipanti) > 1 else 0, key="vs_p2_puntuale")
            
        categorie_selezionate = st.multiselect(
            "Seleziona le categorie da confrontare:", 
            categorie_disponibili, 
            default=categorie_disponibili, 
            key="vs_cat_puntuale"
        )
        
        # --- CONTROLLI DI SICUREZZA ---
        if persona1 == persona2:
            st.warning("⚠️ Seleziona due persone diverse per avviare il confronto.")
        elif not categorie_selezionate:
            st.warning("⚠️ Seleziona almeno una categoria dal menu.")
        else:
            dettagli_confronto = []
            
            # --- CALCOLO QUOTE RIGA PER RIGA ---
            for index, riga in df_confronto.iterrows():
                cat = riga.get("Categoria", "Altro")
                
                # Filtro per categoria
                if cat not in categorie_selezionate:
                    continue
                    
                causale = riga["Causale"]
                importo_totale = float(riga["Importo"])
                partecipanti_str = str(riga["Partecipanti"])
                
                quote_riga = {persona1: 0.0, persona2: 0.0}
                
                if ":" in partecipanti_str:
                    # Quote personalizzate
                    voci = partecipanti_str.split(",")
                    for voce in voci:
                        if ":" in voce:
                            nome_debitore, quota_str = voce.split(":")
                            nome_debitore = nome_debitore.strip()
                            if nome_debitore in quote_riga:
                                quote_riga[nome_debitore] = float(quota_str)
                else:
                    # Divisione alla romana (con centesimo fantasma)
                    lista_debitori = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip() != ""]
                    num_debitori = len(lista_debitori)
                    
                    if num_debitori > 0:
                        importo_cents = int(round(importo_totale * 100))
                        quota_base_cents = importo_cents // num_debitori
                        resto_cents = importo_cents % num_debitori
                        
                        for p in [persona1, persona2]:
                            if p in lista_debitori:
                                indice_persona = lista_debitori.index(p)
                                centesimi_extra = 1 if indice_persona < resto_cents else 0
                                quote_riga[p] = (quota_base_cents + centesimi_extra) / 100.0
                
                # Inseriamo la riga nella tabella SOLO se almeno uno dei due è coinvolto nella spesa
                if quote_riga[persona1] > 0 or quote_riga[persona2] > 0:
                    dettagli_confronto.append({
                        "Riga N.": index,
                        "Causale": causale,
                        "Categoria": cat,
                        "Scontrino (€)": importo_totale,
                        f"Quota {persona1} (€)": quote_riga[persona1],
                        f"Quota {persona2} (€)": quote_riga[persona2]
                    })
            
            # --- MOSTRA I RISULTATI ---
            if dettagli_confronto:
                df_vs_puntuale = pd.DataFrame(dettagli_confronto)
                # Impostiamo la riga originale come indice per poter andare a ricontrollare facilmente
                df_vs_puntuale.set_index("Riga N.", inplace=True)
                
                st.success(f"🧾 Trovate **{len(df_vs_puntuale)}** spese che coinvolgono {persona1} o {persona2}.")
                
                # Formattiamo tutte le colonne numeriche in Euro
                format_dict = {
                    "Scontrino (€)": "{:.2f} €",
                    f"Quota {persona1} (€)": "{:.2f} €",
                    f"Quota {persona2} (€)": "{:.2f} €"
                }
                
                st.dataframe(df_vs_puntuale.style.format(format_dict), use_container_width=True)
                
                # Aggiungiamo un riepilogo rapido sotto la tabella
                tot_p1 = df_vs_puntuale[f"Quota {persona1} (€)"].sum()
                tot_p2 = df_vs_puntuale[f"Quota {persona2} (€)"].sum()
                
                col_res1, col_res2, col_diff = st.columns(3)
                col_res1.metric(f"Totale {persona1}", f"{tot_p1:.2f} €")
                col_res2.metric(f"Totale {persona2}", f"{tot_p2:.2f} €")
                col_diff.metric("Differenza", f"{abs(tot_p1 - tot_p2):.2f} €")
                
            else:
                st.info("Nessuna spesa registrata per queste due persone nelle categorie selezionate.")
            
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
        
        # 1. Estraiamo l'indice dal menu a tendina
        indice_mod_selezionato = int(spesa_da_mod.split(" ")[1])
        
        # 2. Pulsante esplicito per forzare il caricamento
        if st.button("🔄 Carica Dati per questa spesa"):
            st.session_state["indice_in_modifica"] = indice_mod_selezionato
            
        # 3. Mostriamo i campi di testo SOLO dopo aver cliccato il pulsante e salvato la scelta
        if "indice_in_modifica" in st.session_state:
            indice_mod = st.session_state["indice_in_modifica"]
            riga_attuale = df.loc[indice_mod]
            
            st.info(f"Stai modificando i dati della **Riga {indice_mod}** (Premi 'Carica Dati' in alto se cambi spesa nel menu)")
            
            # --- LOGICA DI LETTURA PARTECIPANTI E QUOTE ATTUALI ---
            partecipanti_str = str(riga_attuale["Partecipanti"])
            is_custom = ":" in partecipanti_str
            
            quote_esistenti = {}
            partecipanti_esistenti = []
            
            if is_custom:
                for item in partecipanti_str.split(","):
                    if ":" in item:
                        nome, quota = item.split(":")
                        quote_esistenti[nome.strip()] = float(quota)
                        partecipanti_esistenti.append(nome.strip())
            else:
                partecipanti_esistenti = [nome.strip() for nome in partecipanti_str.split(",") if nome.strip()]
            
            default_partecipanti = [p for p in partecipanti_esistenti if p in partecipanti]
            
            # --- LOGICA DI LETTURA PAGANTI ATTUALI ---
            paganti_str = str(riga_attuale["Pagante"])
            is_custom_pag = ":" in paganti_str
            
            quote_esistenti_pag = {}
            if is_custom_pag:
                for item in paganti_str.split(","):
                    if ":" in item:
                        nome, quota = item.split(":")
                        quote_esistenti_pag[nome.strip()] = float(quota)
                paganti_esistenti_pag = list(quote_esistenti_pag.keys())
            else:
                paganti_esistenti_pag = [nome.strip() for nome in paganti_str.split(",") if nome.strip()]
            
            default_paganti = [p for p in paganti_esistenti_pag if p in partecipanti]
            if not default_paganti: # Fallback di sicurezza
                default_paganti = [partecipanti[0]]

            # --- INTERFACCIA PAGANTI MULTIPLI ---
            st.write("💳 **Chi ha anticipato i soldi?**")
            tipo_div_pag_mod = st.radio("Come hanno diviso l'anticipo?", ["In parti uguali", "Quote personalizzate"], index=1 if is_custom_pag else 0, key=f"mod_tipo_div_pag_{indice_mod}")
            
            nuovi_paganti = st.multiselect("Pagante/i", partecipanti, default=default_paganti, key=f"mod_paganti_{indice_mod}")
            nuovo_importo = st.number_input("Importo Totale (€)", min_value=0.0, step=0.5, value=float(riga_attuale["Importo"]), key=f"mod_imp_{indice_mod}")
            
            nuova_stringa_paganti = ""
            if tipo_div_pag_mod == "In parti uguali":
                nuova_stringa_paganti = ", ".join(nuovi_paganti)
            else:
                st.caption("Inserisci la quota esatta anticipata da ciascuno:")
                quote_pag_mod = {}
                cols_pag_mod = st.columns(3)
                for i, p in enumerate(nuovi_paganti):
                    valore_default_pag = quote_esistenti_pag.get(p, 0.0)
                    with cols_pag_mod[i % 3]:
                        quote_pag_mod[p] = st.number_input(f"{p} ha pagato (€)", min_value=0.0, step=0.5, value=float(valore_default_pag), key=f"mod_qpag_{p}_{indice_mod}")
                
                nuova_stringa_paganti = ", ".join([f"{p}:{quote_pag_mod[p]}" for p in nuovi_paganti])
                
                somma_pagata_mod = sum(quote_pag_mod.values())
                if abs(somma_pagata_mod - nuovo_importo) > 0.01:
                    st.warning(f"⚠️ Attenzione: la somma degli anticipi ({somma_pagata_mod:.2f} €) non coincide con l'importo totale ({nuovo_importo:.2f} €).")

            # --- DATI AGGIUNTIVI SPESA ---
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                nuova_causale = st.text_input("Causale", value=str(riga_attuale["Causale"]), key=f"mod_caus_{indice_mod}")
            with col_m2:
                nuova_categoria = st.text_input("Categoria", value=str(riga_attuale.get("Categoria", "")), key=f"mod_cat_{indice_mod}")

            # --- INTERFACCIA GESTIONE AVANZATA PARTECIPANTI ---
            st.write("👥 **Gestione Partecipanti e Quote**")
            tipo_div = st.radio("Come dividere la spesa?", ["In parti uguali", "Quote personalizzate"], index=1 if is_custom else 0, key=f"mod_tipo_div_{indice_mod}")
            
            nuovi_partecipanti = st.multiselect("Partecipanti coinvolti", partecipanti, default=default_partecipanti, key=f"mod_part_{indice_mod}")
            
            nuova_stringa_partecipanti = ""
            
            if tipo_div == "In parti uguali":
                nuova_stringa_partecipanti = ", ".join(nuovi_partecipanti)
            else:
                st.caption("Inserisci o modifica la quota esatta per ogni partecipante:")
                quote_aggiornate = {}
                cols = st.columns(3)
                for i, p in enumerate(nuovi_partecipanti):
                    valore_default = quote_esistenti.get(p, 0.0)
                    with cols[i % 3]:
                        quote_aggiornate[p] = st.number_input(f"{p} (€)", min_value=0.0, step=0.5, value=float(valore_default), key=f"mod_quota_{p}_{indice_mod}")
                
                nuova_stringa_partecipanti = ", ".join([f"{p}:{quote_aggiornate[p]}" for p in nuovi_partecipanti])
                
                somma_quote = sum(quote_aggiornate.values())
                if abs(somma_quote - nuovo_importo) > 0.01:
                    st.warning(f"⚠️ Attenzione: la somma delle quote personalizzate ({somma_quote:.2f} €) non coincide con l'importo totale ({nuovo_importo:.2f} €).")
                elif len(nuovi_partecipanti) > 0:
                    st.success("✅ La somma delle quote combacia con il totale.")

            # --- SALVATAGGIO ---
            col_mp1, col_mp2 = st.columns(2)
            with col_mp1:
                pwd_mod = st.text_input("Master Password per confermare", type="password", key=f"pwd_mod_{indice_mod}")
            with col_mp2:
                st.write("")
                st.write("")
                if st.button("Salva Modifiche", key=f"btn_salva_mod_{indice_mod}"):
                    if pwd_mod == master_password:
                        # Riscriviamo i dati aggiornati
                        df.at[indice_mod, "Pagante"] = nuova_stringa_paganti
                        df.at[indice_mod, "Importo"] = nuovo_importo
                        df.at[indice_mod, "Causale"] = nuova_causale
                        if "Categoria" in df.columns:
                            df.at[indice_mod, "Categoria"] = nuova_categoria
                        df.at[indice_mod, "Partecipanti"] = nuova_stringa_partecipanti
                        
                        conn.update(spreadsheet=url_foglio, data=df)
                        st.success("✏️ Spesa aggiornata con successo!")
                        
                        # Eliminiamo la memoria di modifica per "chiudere" l'editor
                        del st.session_state["indice_in_modifica"]
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Master Password errata!")
    
with tab_bilanci:
    st.header("⚖️ Bilancio Finale: Chi deve a chi")
    
    if not df.empty:
        # 1. Inizializziamo il "conto in banca" di tutti a zero
        bilanci = {p: 0.0 for p in partecipanti}
        
        # 2. CALCOLO DEI SALDI PERSONALI (Crediti - Debiti)
        for index, riga in df.iterrows():
            importo_totale = float(riga["Importo"])
            
            # --- A. GESTIONE CREDITI (Chi ha messo i soldi = +) ---
            paganti_str = str(riga["Pagante"])
            if ":" in paganti_str:
                # Pagamento con quote personalizzate
                for voce in paganti_str.split(","):
                    if ":" in voce:
                        nome, quota = voce.split(":")
                        nome_pulito = nome.strip()
                        if nome_pulito in bilanci:
                            bilanci[nome_pulito] += float(quota)
            else:
                # Pagamento in parti uguali tra chi ha anticipato
                lista_paganti = [n.strip() for n in paganti_str.split(",") if n.strip()]
                num_paganti = len(lista_paganti)
                
                if num_paganti > 0:
                    imp_cents = int(round(importo_totale * 100))
                    quota_base_cents = imp_cents // num_paganti
                    resto_cents = imp_cents % num_paganti
                    
                    for i, p in enumerate(lista_paganti):
                        centesimi_extra = 1 if i < resto_cents else 0
                        quota_finale = (quota_base_cents + centesimi_extra) / 100.0
                        if p in bilanci:
                            bilanci[p] += quota_finale
                            
            # --- B. GESTIONE DEBITI (Chi ha usufruito della spesa = -) ---
            partecipanti_str = str(riga["Partecipanti"])
            if ":" in partecipanti_str:
                # Consumo con quote personalizzate
                for voce in partecipanti_str.split(","):
                    if ":" in voce:
                        nome, quota = voce.split(":")
                        nome_pulito = nome.strip()
                        if nome_pulito in bilanci:
                            bilanci[nome_pulito] -= float(quota)
            else:
                # Consumo in parti uguali (alla romana)
                lista_debitori = [n.strip() for n in partecipanti_str.split(",") if n.strip()]
                num_debitori = len(lista_debitori)
                
                if num_debitori > 0:
                    imp_cents = int(round(importo_totale * 100))
                    quota_base_cents = imp_cents // num_debitori
                    resto_cents = imp_cents % num_debitori
                    
                    for i, p in enumerate(lista_debitori):
                        centesimi_extra = 1 if i < resto_cents else 0
                        quota_finale = (quota_base_cents + centesimi_extra) / 100.0
                        if p in bilanci:
                            bilanci[p] -= quota_finale
                            
        # Arrotondiamo tutto a 2 decimali per evitare errori di virgola mobile
        for p in bilanci:
            bilanci[p] = round(bilanci[p], 2)

        # 3. MOSTRA I SALDI ATTUALI IN UN GRAFICO
        st.subheader("📊 Situazione Attuale")
        df_bilanci = pd.DataFrame(list(bilanci.items()), columns=["Partecipante", "Saldo"])
        
        # --- ORDINA DAL PIÙ IN CREDITO AL PIÙ IN DEBITO ---
        df_bilanci = df_bilanci.sort_values(by="Saldo", ascending=False).reset_index(drop=True)
        
        # Grafico a barre
        df_bilanci["Colore"] = df_bilanci["Saldo"].apply(lambda x: "Credito" if x > 0 else ("Debito" if x < 0 else "Pari"))
        fig_saldi = px.bar(
            df_bilanci, 
            x="Partecipante", 
            y="Saldo", 
            color="Colore",
            color_discrete_map={"Credito": "#2ecc71", "Debito": "#e74c3c", "Pari": "#95a5a6"},
            text="Saldo"
        )
        fig_saldi.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Euro (€)", showlegend=False)
        
        # --- AUMENTA LA DIMENSIONE DEL FONT DEI NUMERI (textfont_size=16) ---
        fig_saldi.update_traces(texttemplate='%{text:.2f} €', textposition='outside', textfont_size=16)
        
        st.plotly_chart(fig_saldi, use_container_width=True)

        # --- NUOVA TABELLA CON COLORI DINAMICI (ORA ORDINATA) ---
        st.write("📋 **Dettaglio Saldi**")
        
        def colora_saldo(valore):
            """Applica il testo verde se positivo, rosso se negativo"""
            if valore > 0.01:
                colore = '#2ecc71' # Verde
            elif valore < -0.01:
                colore = '#e74c3c' # Rosso
            else:
                colore = '#ffffff' # Bianco/Neutro
            return f'color: {colore}; font-weight: bold;'
            
        # Mostriamo la tabella applicando lo stile solo alla colonna 'Saldo'
        st.dataframe(
            df_bilanci[["Partecipante", "Saldo"]].style
            .map(colora_saldo, subset=["Saldo"])
            .format({"Saldo": "{:.2f} €"}),
            use_container_width=True
        )

        st.divider()

        # 4. ALGORITMO DI RISOLUZIONE DEI DEBITI (Chi paga chi)
        st.subheader("💸 Come pareggiare i conti")
        
        debitori = [{"nome": k, "importo": -v} for k, v in bilanci.items() if v < -0.01]
        creditori = [{"nome": k, "importo": v} for k, v in bilanci.items() if v > 0.01]
        
        debitori = sorted(debitori, key=lambda x: x["importo"], reverse=True)
        creditori = sorted(creditori, key=lambda x: x["importo"], reverse=True)
        
        transazioni = []
        i, j = 0, 0
        
        while i < len(debitori) and j < len(creditori):
            deb = debitori[i]
            cred = creditori[j]
            
            importo_transazione = min(deb["importo"], cred["importo"])
            
            transazioni.append({
                "Da": deb["nome"],
                "A": cred["nome"],
                "Importo": round(importo_transazione, 2)
            })
            
            deb["importo"] -= importo_transazione
            cred["importo"] -= importo_transazione
            
            if deb["importo"] < 0.01:
                i += 1
            if cred["importo"] < 0.01:
                j += 1
                
        # --- BOX GIALLI PERSONALIZZATI PER LE TRANSAZIONI ---
        if transazioni:
            for t in transazioni:
                debitore = t['Da']
                creditore = t['A']
                importo = t['Importo']
                
                testo_transazione = f"{debitore} deve dare {importo:.2f} € a {creditore}"
                
                # Prepariamo il pulsante PayPal
                link_html = ""
                if creditore in link_paypal and link_paypal[creditore].startswith("http"):
                    importo_formattato = f"{importo:.2f}".replace(",", ".")
                    
                    # Trasformiamo il link corto nel link esteso per aggirare il bug dell'app mobile
                    url_base = link_paypal[creditore].replace("paypal.me", "paypal.com/paypalme")
                    url_pagamento = f"{url_base}/{importo_formattato}"
                    
                    # HTML compresso su una sola riga
                    link_html = f"<br><a href='{url_pagamento}' target='_blank' style='display: inline-block; margin-top: 12px; padding: 8px 16px; background-color: #0070ba; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: normal;'>💸 Paga {importo:.2f} € con PayPal</a>"
                
                box_giallo = f"<div style='background-color: #fff9c4; color: #b7950b; padding: 16px; border-radius: 8px; margin-bottom: 12px; font-weight: bold; border: 1px solid #f1c40f; text-align: center; font-size: 16px;'>🔄 {testo_transazione}{link_html}</div>"
                
                st.markdown(box_giallo, unsafe_allow_html=True)
        else:
            st.success("🎉 I conti sono perfettamente in pareggio! Nessuno deve soldi a nessuno.")
            
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
