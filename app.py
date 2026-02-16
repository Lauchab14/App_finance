"""
🏠 Analyseur de Rentabilité Immobilière
Application Streamlit pour analyser la rentabilité d'un immeuble résidentiel au Québec.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from finance import (
    calculer_droits_mutation,
    calculer_couts_initiaux,
    calculer_paiement_hypothecaire,
    tableau_amortissement,
    analyse_annee_1,
    projection_10_ans,
    calculer_indicateurs,
    BAREMES,
)
from scraper import extraire_donnees, detecter_plateforme
from location import CRITERES, calculer_score_localisation

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION DE LA PAGE
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="🏠 Analyseur Immobilier",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════
# CSS CUSTOM — THÈME PREMIUM
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* Police Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Thème global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* En-tête principal */
    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        font-size: 1rem;
        opacity: 0.85;
        margin-top: 0.5rem;
    }

    /* Cartes métriques */
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
    }
    .metric-card .label {
        font-size: 0.85rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }
    .metric-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #64ffda;
        margin-top: 0.3rem;
    }
    .metric-card .value.negative { color: #ff6b6b; }
    .metric-card .value.warning { color: #ffd93d; }

    /* Badges de score */
    .score-badge {
        display: inline-block;
        font-size: 3rem;
        font-weight: 800;
        padding: 1rem 2rem;
        border-radius: 16px;
        margin: 1rem 0;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 10px 20px;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f2027 0%, #203a43 100%);
    }
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #64ffda;
    }

    /* Table styling */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }

    /* Section dividers */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #64ffda44, transparent);
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# EN-TÊTE
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>🏠 Analyseur de Rentabilité Immobilière</h1>
    <p>Analysez la rentabilité d'un immeuble résidentiel au Québec — Année 1, projection 10 ans, localisation et indicateurs financiers</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — HYPOTHÈSES MODIFIABLES
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Hypothèses financières")
    st.markdown("---")

    st.markdown("### 💵 Financement")
    taux_interet = st.slider("Taux d'intérêt (%)", 1.0, 10.0, 5.0, 0.25)
    amortissement = st.selectbox("Amortissement (années)", [15, 20, 25, 30], index=2)
    mise_de_fonds_pct = st.slider("Mise de fonds (%)", 5.0, 50.0, 20.0, 1.0)

    st.markdown("---")
    st.markdown("### 📈 Projections")
    croissance_loyers = st.slider("Croissance annuelle des loyers (%)", 0.0, 8.0, 3.0, 0.5)
    inflation_depenses = st.slider("Inflation annuelle des dépenses (%)", 0.0, 8.0, 2.0, 0.5)
    appreciation_immeuble = st.slider("Appréciation annuelle de l'immeuble (%)", 0.0, 10.0, 3.0, 0.5)
    taux_inoccupation = st.slider("Taux d'inoccupation (%)", 0.0, 15.0, 5.0, 0.5)

    st.markdown("---")
    st.markdown("### 🏛️ Municipalité")
    bareme_mutation = st.selectbox("Barème droits de mutation", list(BAREMES.keys()))

    st.markdown("---")
    st.markdown("### ℹ️ À propos")
    st.caption(
        "Application développée pour analyser la rentabilité "
        "d'immeubles résidentiels au Québec. Les calculs sont "
        "basés sur les barèmes 2026."
    )


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — SAISIE DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("## 🔗 Source des données")

col_url, col_btn = st.columns([4, 1])
with col_url:
    url_input = st.text_input(
        "Collez l'URL d'une annonce (Centris, DuProprio, LesPACs)",
        placeholder="https://www.centris.ca/fr/...",
        label_visibility="collapsed",
    )
with col_btn:
    btn_scrape = st.button("🔍 Analyser l'URL", use_container_width=True)

# Scraping
donnees_scrapees = None
if btn_scrape and url_input:
    with st.spinner("Extraction des données en cours..."):
        donnees_scrapees = extraire_donnees(url_input)
    if donnees_scrapees.get("erreur"):
        st.warning(f"⚠️ {donnees_scrapees['erreur']}")
    else:
        st.success(f"✅ Données extraites de {donnees_scrapees.get('plateforme', 'la plateforme')}")

# Valeurs par défaut (issues du scraping si disponible)
prix_defaut = 0
if donnees_scrapees and donnees_scrapees.get("prix"):
    prix_defaut = int(donnees_scrapees["prix"])

st.markdown("### 📝 Données de l'immeuble")
st.caption("Remplissez ou complétez les informations ci-dessous.")

col1, col2, col3 = st.columns(3)
with col1:
    prix_achat = st.number_input("💲 Prix d'achat ($)", min_value=0, value=prix_defaut, step=5000)
    nb_logements = st.number_input("🏘️ Nombre de logements", min_value=1, value=4, step=1)
with col2:
    loyer_moyen = st.number_input("💰 Loyer moyen par logement ($/mois)", min_value=0, value=800, step=50)
    type_immeuble = st.selectbox("🏠 Type d'immeuble", [
        "Duplex", "Triplex", "Quadruplex", "Quintuplex",
        "6-plex", "Immeuble (7+ logements)", "Autre"
    ])
with col3:
    ville = st.text_input("📍 Ville / Quartier", value=donnees_scrapees.get("ville", "") if donnees_scrapees else "")
    adresse = st.text_input("🏡 Adresse", value=donnees_scrapees.get("adresse", "") if donnees_scrapees else "")

revenus_bruts_annuels = loyer_moyen * nb_logements * 12

st.markdown("### 💸 Dépenses d'exploitation annuelles")
col_d1, col_d2, col_d3 = st.columns(3)
with col_d1:
    taxes_municipales = st.number_input("🏛️ Taxes municipales ($/an)", min_value=0, value=5000, step=100)
    taxes_scolaires = st.number_input("📚 Taxes scolaires ($/an)", min_value=0, value=500, step=50)
with col_d2:
    assurances = st.number_input("🛡️ Assurances ($/an)", min_value=0, value=2500, step=100)
    entretien = st.number_input("🔧 Entretien et réparations ($/an)", min_value=0, value=3000, step=100)
with col_d3:
    gestion_pct = st.number_input("👤 Frais de gestion (% revenus)", min_value=0.0, value=0.0, step=1.0)
    autres_depenses = st.number_input("📦 Autres dépenses ($/an)", min_value=0, value=0, step=100)

st.markdown("### 🏗️ Coûts initiaux non récurrents")
col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    frais_notaire = st.number_input("📜 Frais de notaire ($)", min_value=0, value=2000, step=100)
    frais_inspection = st.number_input("🔎 Inspection ($)", min_value=0, value=800, step=100)
with col_c2:
    frais_evaluation = st.number_input("🏦 Évaluation bancaire ($)", min_value=0, value=500, step=100)
    frais_comptable = st.number_input("🧮 Honoraires comptables ($)", min_value=0, value=500, step=100)
with col_c3:
    travaux_initiaux = st.number_input("🔨 Travaux initiaux ($)", min_value=0, value=0, step=500)
    frais_financement = st.number_input("💳 Frais de financement ($)", min_value=0, value=0, step=100)


# ═══════════════════════════════════════════════════════════════════════════
# CALCULS
# ═══════════════════════════════════════════════════════════════════════════

if prix_achat > 0 and revenus_bruts_annuels > 0:

    # Coûts initiaux
    couts_init = calculer_couts_initiaux(
        prix=prix_achat,
        mise_de_fonds_pct=mise_de_fonds_pct,
        frais_notaire=frais_notaire,
        frais_inspection=frais_inspection,
        frais_evaluation=frais_evaluation,
        frais_comptable=frais_comptable,
        travaux_initiaux=travaux_initiaux,
        frais_financement=frais_financement,
        bareme_mutation=bareme_mutation,
    )

    # Dépenses d'exploitation
    depenses_exploitation = (
        taxes_municipales + taxes_scolaires + assurances
        + entretien + (revenus_bruts_annuels * (1 - taux_inoccupation/100) * gestion_pct / 100)
        + autres_depenses
    )

    # Analyse année 1
    an1 = analyse_annee_1(
        prix=prix_achat,
        revenus_bruts_annuels=revenus_bruts_annuels,
        taux_inoccupation=taux_inoccupation,
        taxes_municipales=taxes_municipales,
        taxes_scolaires=taxes_scolaires,
        assurances=assurances,
        entretien=entretien,
        gestion_pct=gestion_pct,
        autres_depenses=autres_depenses,
        mise_de_fonds_pct=mise_de_fonds_pct,
        taux_interet=taux_interet,
        amortissement=amortissement,
        couts_initiaux=couts_init,
    )

    # Projection 10 ans
    proj = projection_10_ans(
        prix=prix_achat,
        revenus_bruts_annuels=revenus_bruts_annuels,
        depenses_exploitation_an1=depenses_exploitation,
        noi_an1=an1["NOI"],
        taux_inoccupation=taux_inoccupation,
        mise_de_fonds_pct=mise_de_fonds_pct,
        taux_interet=taux_interet,
        amortissement=amortissement,
        croissance_loyers=croissance_loyers,
        inflation_depenses=inflation_depenses,
        appreciation_immeuble=appreciation_immeuble,
        mise_de_fonds_totale=couts_init["Total coûts initiaux"],
    )

    # Indicateurs
    indicateurs = calculer_indicateurs(
        prix=prix_achat,
        noi=an1["NOI"],
        cashflow=an1["Cashflow"],
        mise_de_fonds_totale=couts_init["Total coûts initiaux"],
        service_dette=an1["Service de dette"],
        revenus_nets=an1["Revenus nets"],
        taux_interet=taux_interet,
        hypotheque=an1["Hypothèque"],
    )

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # ONGLETS
    # ═══════════════════════════════════════════════════════════════════

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Année 1",
        "📈 Projection 10 ans",
        "📍 Localisation",
        "📊 Indicateurs",
    ])

    # ───────────────────────────────────────────────────────────────────
    # ONGLET 1 : ANNÉE 1
    # ───────────────────────────────────────────────────────────────────
    with tab1:
        st.markdown("## 📋 Analyse de la première année")

        # Métriques principales
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            cashflow_color = "normal" if an1["Cashflow"] >= 0 else "inverse"
            st.metric("💵 Cashflow annuel", f"{an1['Cashflow']:,.2f} $", delta=f"{an1['Cashflow']/12:,.0f} $/mois", delta_color=cashflow_color)
        with m2:
            st.metric("📊 CSD (ratio)", f"{an1['CSD']:.3f}", delta="≥ 1.20 recommandé" if an1['CSD'] >= 1.2 else "< 1.20 ⚠️", delta_color="normal" if an1['CSD'] >= 1.2 else "inverse")
        with m3:
            st.metric("🏦 LTV", f"{an1['LTV']:.1f} %")
        with m4:
            rend_color = "normal" if an1["Rendement mise de fonds (%)"] >= 0 else "inverse"
            st.metric("💰 Rendement MDF", f"{an1['Rendement mise de fonds (%)']:.2f} %", delta_color=rend_color)

        st.markdown("")

        m5, m6, m7, m8 = st.columns(4)
        with m5:
            st.metric("🏠 Cap Rate", f"{an1['Cap Rate (%)']:.2f} %")
        with m6:
            st.metric("💵 Cash-on-Cash", f"{an1['Cash-on-Cash (%)']:.2f} %")
        with m7:
            st.metric("📈 NOI", f"{an1['NOI']:,.2f} $")
        with m8:
            st.metric("🏦 Service de dette", f"{an1['Service de dette']:,.2f} $")

        st.markdown("---")

        # Graphiques côte à côte
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.markdown("#### 💸 Répartition des coûts initiaux")
            couts_df = pd.DataFrame([
                {"Poste": k, "Montant": v}
                for k, v in couts_init.items()
                if k != "Total coûts initiaux" and v > 0
            ])
            if not couts_df.empty:
                fig_couts = px.pie(
                    couts_df, values="Montant", names="Poste",
                    hole=0.45,
                    color_discrete_sequence=px.colors.sequential.Tealgrn,
                )
                fig_couts.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="white"),
                    showlegend=True,
                    legend=dict(font=dict(size=11)),
                    margin=dict(t=20, b=20),
                )
                st.plotly_chart(fig_couts, use_container_width=True)

            st.markdown(f"**Total coûts initiaux : {couts_init['Total coûts initiaux']:,.2f} $**")

        with col_g2:
            st.markdown("#### 📊 Revenus vs Dépenses (Année 1)")
            rev_dep = pd.DataFrame({
                "Catégorie": ["Revenus bruts", "Vacance", "Dépenses exploitation", "Service de dette", "Cashflow"],
                "Montant": [
                    an1["Revenus bruts"],
                    -an1["Vacance"],
                    -an1["Dépenses d'exploitation"],
                    -an1["Service de dette"],
                    an1["Cashflow"],
                ],
            })
            colors = ["#64ffda", "#ff6b6b", "#ff9100", "#ffd93d", "#00c853" if an1["Cashflow"] >= 0 else "#ff1744"]
            fig_rev = go.Figure(go.Bar(
                x=rev_dep["Catégorie"],
                y=rev_dep["Montant"],
                marker_color=colors,
                text=[f"{v:,.0f} $" for v in rev_dep["Montant"]],
                textposition="outside",
            ))
            fig_rev.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(t=20, b=20),
                height=400,
            )
            st.plotly_chart(fig_rev, use_container_width=True)

    # ───────────────────────────────────────────────────────────────────
    # ONGLET 2 : PROJECTION 10 ANS
    # ───────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("## 📈 Projection sur 10 ans")

        # Métriques sommaires
        pm1, pm2, pm3, pm4 = st.columns(4)
        with pm1:
            tri_value = proj["TRI (%)"]
            tri_display = f"{tri_value:.2f} %" if tri_value is not None else "N/A"
            st.metric("📈 TRI", tri_display)
        with pm2:
            van_value = proj["VAN ($)"]
            van_display = f"{van_value:,.2f} $" if van_value is not None else "N/A"
            st.metric("💰 VAN", van_display)
        with pm3:
            st.metric("📊 Cashflow cumulé (10 ans)", f"{proj['Cashflow cumulé']:,.2f} $")
        with pm4:
            st.metric("🏠 Équité finale", f"{proj['Équité finale']:,.2f} $")

        pm5, pm6 = st.columns(2)
        with pm5:
            st.metric("🏡 Valeur projetée (an 10)", f"{proj['Valeur projetée']:,.2f} $")
        with pm6:
            rend_cum = proj["Rendement cumulé (%)"]
            rend_cum_display = f"{rend_cum:.2f} %" if rend_cum is not None else "N/A"
            st.metric("💵 Rendement cumulé", rend_cum_display)

        st.markdown("---")

        # Tableau de projection
        df_proj = pd.DataFrame(proj["projection"])
        st.markdown("#### 📋 Tableau détaillé")
        st.dataframe(
            df_proj.style.format({
                "Revenus bruts": "{:,.0f} $",
                "Revenus nets": "{:,.0f} $",
                "Dépenses": "{:,.0f} $",
                "NOI": "{:,.0f} $",
                "Service de dette": "{:,.0f} $",
                "Cashflow": "{:,.0f} $",
                "Cashflow cumulé": "{:,.0f} $",
                "Valeur immeuble": "{:,.0f} $",
                "Solde hypothèque": "{:,.0f} $",
                "Équité": "{:,.0f} $",
            }),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")

        # Graphiques
        col_p1, col_p2 = st.columns(2)

        with col_p1:
            st.markdown("#### 💵 Cashflow annuel et cumulé")
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(
                x=df_proj["Année"], y=df_proj["Cashflow"],
                name="Cashflow annuel",
                marker_color="#64ffda",
            ))
            fig_cf.add_trace(go.Scatter(
                x=df_proj["Année"], y=df_proj["Cashflow cumulé"],
                name="Cashflow cumulé",
                line=dict(color="#ffd93d", width=3),
                mode="lines+markers",
            ))
            fig_cf.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(orientation="h", y=-0.15),
                margin=dict(t=20, b=40),
                height=400,
            )
            st.plotly_chart(fig_cf, use_container_width=True)

        with col_p2:
            st.markdown("#### 🏠 Valeur immeuble vs Hypothèque")
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=df_proj["Année"], y=df_proj["Valeur immeuble"],
                name="Valeur immeuble",
                fill="tozeroy",
                line=dict(color="#64ffda", width=2),
            ))
            fig_eq.add_trace(go.Scatter(
                x=df_proj["Année"], y=df_proj["Solde hypothèque"],
                name="Solde hypothèque",
                fill="tozeroy",
                line=dict(color="#ff6b6b", width=2),
            ))
            fig_eq.add_trace(go.Scatter(
                x=df_proj["Année"], y=df_proj["Équité"],
                name="Équité",
                line=dict(color="#ffd93d", width=3, dash="dash"),
                mode="lines+markers",
            ))
            fig_eq.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(orientation="h", y=-0.15),
                margin=dict(t=20, b=40),
                height=400,
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        # Graphique revenus vs dépenses dans le temps
        st.markdown("#### 📊 Évolution revenus nets vs dépenses")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(
            x=df_proj["Année"], y=df_proj["Revenus nets"],
            name="Revenus nets", line=dict(color="#64ffda", width=2),
            mode="lines+markers",
        ))
        fig_evol.add_trace(go.Scatter(
            x=df_proj["Année"], y=df_proj["Dépenses"],
            name="Dépenses", line=dict(color="#ff6b6b", width=2),
            mode="lines+markers",
        ))
        fig_evol.add_trace(go.Scatter(
            x=df_proj["Année"], y=df_proj["NOI"],
            name="NOI", line=dict(color="#ffd93d", width=3),
            mode="lines+markers",
        ))
        fig_evol.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            legend=dict(orientation="h", y=-0.15),
            margin=dict(t=20, b=40),
            height=400,
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    # ───────────────────────────────────────────────────────────────────
    # ONGLET 3 : LOCALISATION
    # ───────────────────────────────────────────────────────────────────
    with tab3:
        st.markdown("## 📍 Analyse de la localisation")

        if ville:
            st.markdown(f"**Emplacement analysé :** {adresse}, {ville}" if adresse else f"**Secteur :** {ville}")

        st.markdown("Évaluez chaque critère pour obtenir un score de localisation global.")
        st.markdown("")

        reponses = {}
        # Afficher les critères en 2 colonnes
        critere_ids = list(CRITERES.keys())
        col_loc1, col_loc2 = st.columns(2)

        for i, cid in enumerate(critere_ids):
            info = CRITERES[cid]
            col = col_loc1 if i % 2 == 0 else col_loc2
            with col:
                choix = st.selectbox(
                    info["label"],
                    options=list(info["options"].keys()),
                    index=2,  # Valeur par défaut : milieu
                    help=info["description"],
                    key=f"loc_{cid}",
                )
                reponses[cid] = choix

        st.markdown("---")

        # Calcul du score
        resultat_loc = calculer_score_localisation(reponses)

        col_score, col_radar = st.columns([1, 2])

        with col_score:
            score = resultat_loc["score_global"]
            couleur = resultat_loc["couleur"]
            st.markdown(
                f'<div class="score-badge" style="background:{couleur}22; border: 2px solid {couleur}; color:{couleur}">'
                f'{score}/10</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"### {resultat_loc['appreciation']}")

        with col_radar:
            # Graphique radar
            labels = list(resultat_loc["valeurs_radar"].keys())
            values = list(resultat_loc["valeurs_radar"].values())
            # Fermer le polygone
            labels_r = labels + [labels[0]]
            values_r = values + [values[0]]

            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=values_r,
                theta=labels_r,
                fill="toself",
                fillcolor="rgba(100, 255, 218, 0.2)",
                line=dict(color="#64ffda", width=2),
                marker=dict(size=6),
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 10], gridcolor="rgba(255,255,255,0.1)"),
                    angularaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
                    bgcolor="rgba(0,0,0,0)",
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white", size=11),
                margin=dict(t=40, b=40),
                height=450,
                showlegend=False,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # Tableau détaillé
        st.markdown("#### 📋 Détail des scores")
        df_loc = pd.DataFrame(resultat_loc["details"])
        st.dataframe(
            df_loc.style.format({
                "Score": "{:.0f}",
                "Poids": "{:.1f}",
                "Score pondéré": "{:.1f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    # ───────────────────────────────────────────────────────────────────
    # ONGLET 4 : INDICATEURS FINANCIERS
    # ───────────────────────────────────────────────────────────────────
    with tab4:
        st.markdown("## 📊 Indicateurs financiers")

        # Indicateurs principaux
        i1, i2, i3 = st.columns(3)
        with i1:
            st.metric("📈 Cap Rate", f"{indicateurs['Cap Rate (%)']:.2f} %")
        with i2:
            st.metric("💵 Cash-on-Cash", f"{indicateurs['Cash-on-Cash (%)']:.2f} %")
        with i3:
            st.metric("📊 CSD", f"{indicateurs['CSD']:.3f}")

        i4, i5, i6 = st.columns(3)
        with i4:
            st.metric("🏦 LTV", f"{indicateurs['LTV (%)']:.1f} %")
        with i5:
            delai = indicateurs["Délai de récupération (années)"]
            st.metric("⏱️ Délai de récupération", f"{delai} ans" if delai != "∞" else "∞")
        with i6:
            st.metric("📐 GRM", f"{indicateurs['GRM']:.2f}")

        st.markdown("---")

        # Tableau récapitulatif
        st.markdown("#### 📋 Récapitulatif complet")
        recap_data = {
            "Indicateur": [
                "Prix d'achat",
                "Mise de fonds totale (avec frais)",
                "Hypothèque",
                "Paiement hypothécaire mensuel",
                "Revenus bruts annuels",
                "Revenus nets (après vacance)",
                "Dépenses d'exploitation",
                "NOI (revenu net d'exploitation)",
                "Service de dette annuel",
                "Cashflow annuel",
                "Cashflow mensuel",
            ],
            "Valeur": [
                f"{prix_achat:,.2f} $",
                f"{couts_init['Total coûts initiaux']:,.2f} $",
                f"{an1['Hypothèque']:,.2f} $",
                f"{calculer_paiement_hypothecaire(an1['Hypothèque'], taux_interet, amortissement):,.2f} $",
                f"{an1['Revenus bruts']:,.2f} $",
                f"{an1['Revenus nets']:,.2f} $",
                f"{an1['Dépenses d' + 'exploitation']:,.2f} $",
                f"{an1['NOI']:,.2f} $",
                f"{an1['Service de dette']:,.2f} $",
                f"{an1['Cashflow']:,.2f} $",
                f"{an1['Cashflow']/12:,.2f} $",
            ],
        }
        st.dataframe(pd.DataFrame(recap_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Sensibilité aux taux d'intérêt
        st.markdown("#### 🎛️ Sensibilité aux taux d'intérêt")
        st.caption("Impact d'une variation du taux d'intérêt sur le cashflow annuel")

        sensibilite = indicateurs["Sensibilité taux d'intérêt"]
        if sensibilite:
            taux_labels = list(sensibilite.keys())
            cashflows_sens = list(sensibilite.values())
            colors_sens = ["#64ffda" if cf >= 0 else "#ff6b6b" for cf in cashflows_sens]

            fig_sens = go.Figure(go.Bar(
                x=taux_labels,
                y=cashflows_sens,
                marker_color=colors_sens,
                text=[f"{cf:,.0f} $" for cf in cashflows_sens],
                textposition="outside",
            ))
            fig_sens.update_layout(
                xaxis_title="Taux d'intérêt",
                yaxis_title="Cashflow annuel ($)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(t=20, b=40),
                height=400,
            )
            # Ajouter une ligne à y=0
            fig_sens.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
            # Ajouter le taux actuel
            fig_sens.add_vline(
                x=f"{taux_interet:.1f}%",
                line_dash="dot",
                line_color="#ffd93d",
                annotation_text="Taux actuel",
                annotation_font_color="#ffd93d",
            )

            st.plotly_chart(fig_sens, use_container_width=True)

else:
    st.markdown("---")
    st.info("👆 Remplissez les données de l'immeuble ci-dessus pour lancer l'analyse.")
    st.markdown("""
    ### 🎯 Fonctionnalités
    - 🔗 **Extraction automatique** des données depuis Centris, DuProprio
    - 📋 **Analyse complète de l'année 1** incluant tous les coûts non récurrents
    - 📈 **Projection financière sur 10 ans** avec TRI, VAN et rendement cumulé
    - 📍 **Analyse de localisation** avec score pondéré sur 10
    - 📊 **Indicateurs financiers** : Cap Rate, CSD, LTV, Cash-on-Cash, sensibilité aux taux
    - ⚙️ **Hypothèses modifiables** dans la barre latérale
    """)
