"""
🏠 Analyseur de Rentabilité Immobilière
Application Streamlit pour analyser la rentabilité d'un immeuble résidentiel au Québec.
Fichier unique regroupant tous les modules : finance, scraper, localisation et UI.
"""

import re
from urllib.parse import urlparse

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
from bs4 import BeautifulSoup

try:
    import numpy_financial as npf
    _HAS_NPF = True
except ImportError:
    _HAS_NPF = False


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    MODULE FINANCE — CALCULS FINANCIERS                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# --- Barèmes droits de mutation Québec 2026 ---
TRANCHES_MUTATION_QC_2026 = [
    (62_900, 0.005), (315_000, 0.01), (float("inf"), 0.015),
]
TRANCHES_MUTATION_MTL_2026 = [
    (62_900, 0.005), (315_000, 0.01), (500_000, 0.015),
    (1_000_000, 0.02), (2_000_000, 0.025), (3_113_000, 0.035),
    (float("inf"), 0.04),
]
TRANCHES_MUTATION_QCV_2026 = [
    (62_900, 0.005), (315_000, 0.01), (500_000, 0.015),
    (750_000, 0.025), (float("inf"), 0.03),
]
BAREMES = {
    "Québec (général)": TRANCHES_MUTATION_QC_2026,
    "Montréal": TRANCHES_MUTATION_MTL_2026,
    "Ville de Québec": TRANCHES_MUTATION_QCV_2026,
}


def calculer_droits_mutation(prix: float, bareme: str = "Québec (général)") -> float:
    tranches = BAREMES.get(bareme, TRANCHES_MUTATION_QC_2026)
    taxe, seuil_prec = 0.0, 0.0
    for seuil, taux in tranches:
        if prix <= seuil_prec:
            break
        taxe += (min(prix, seuil) - seuil_prec) * taux
        seuil_prec = seuil
    return round(taxe, 2)


def calculer_couts_initiaux(prix, mise_de_fonds_pct=20.0, frais_notaire=2000.0,
    frais_inspection=800.0, frais_evaluation=500.0, frais_comptable=500.0,
    travaux_initiaux=0.0, frais_financement=0.0, bareme_mutation="Québec (général)"):
    mise_de_fonds = prix * (mise_de_fonds_pct / 100)
    droits_mutation = calculer_droits_mutation(prix, bareme_mutation)
    couts = {
        "Mise de fonds": mise_de_fonds, "Droits de mutation": droits_mutation,
        "Frais de notaire": frais_notaire, "Inspection": frais_inspection,
        "Évaluation bancaire": frais_evaluation, "Honoraires comptables": frais_comptable,
        "Travaux initiaux": travaux_initiaux, "Frais de financement": frais_financement,
    }
    couts["Total coûts initiaux"] = sum(couts.values())
    return couts


def calculer_paiement_hypothecaire(montant, taux_annuel, amortissement_annees=25):
    if montant <= 0 or taux_annuel <= 0:
        return 0.0
    r = taux_annuel / 100 / 12
    n = amortissement_annees * 12
    return round(montant * (r * (1 + r) ** n) / ((1 + r) ** n - 1), 2)


def tableau_amortissement(montant, taux_annuel, amortissement_annees=25, annees=10):
    r = taux_annuel / 100 / 12
    pmt = calculer_paiement_hypothecaire(montant, taux_annuel, amortissement_annees)
    solde, tableau = montant, []
    for annee in range(1, annees + 1):
        int_an, cap_an = 0.0, 0.0
        for _ in range(12):
            interet = solde * r
            capital = pmt - interet
            int_an += interet
            cap_an += capital
            solde -= capital
        tableau.append({"Année": annee, "Paiement annuel": round(pmt * 12, 2),
            "Intérêts": round(int_an, 2), "Capital remboursé": round(cap_an, 2),
            "Solde restant": round(max(solde, 0), 2)})
    return tableau


def analyse_annee_1(prix, revenus_bruts_annuels, taux_inoccupation=5.0,
    taxes_municipales=0.0, taxes_scolaires=0.0, assurances=0.0, entretien=0.0,
    gestion_pct=0.0, autres_depenses=0.0, mise_de_fonds_pct=20.0,
    taux_interet=5.0, amortissement=25, couts_initiaux=None):
    vacance = revenus_bruts_annuels * (taux_inoccupation / 100)
    revenus_nets = revenus_bruts_annuels - vacance
    frais_gestion = revenus_nets * (gestion_pct / 100)
    depenses = taxes_municipales + taxes_scolaires + assurances + entretien + frais_gestion + autres_depenses
    noi = revenus_nets - depenses
    hypotheque = prix * (1 - mise_de_fonds_pct / 100)
    service_dette_annuel = calculer_paiement_hypothecaire(hypotheque, taux_interet, amortissement) * 12
    cashflow = noi - service_dette_annuel
    mdf_totale = couts_initiaux.get("Total coûts initiaux", prix * (mise_de_fonds_pct / 100)) if couts_initiaux else prix * (mise_de_fonds_pct / 100)
    csd = revenus_nets / service_dette_annuel if service_dette_annuel > 0 else 0
    ltv = hypotheque / prix if prix > 0 else 0
    return {
        "Revenus bruts": round(revenus_bruts_annuels, 2), "Vacance": round(vacance, 2),
        "Revenus nets": round(revenus_nets, 2), "Depenses exploitation": round(depenses, 2),
        "NOI": round(noi, 2), "Service de dette": round(service_dette_annuel, 2),
        "Cashflow": round(cashflow, 2), "Hypothèque": round(hypotheque, 2),
        "CSD": round(csd, 3), "LTV": round(ltv * 100, 1),
        "Rendement mise de fonds (%)": round((cashflow / mdf_totale * 100) if mdf_totale > 0 else 0, 2),
        "Cap Rate (%)": round((noi / prix * 100) if prix > 0 else 0, 2),
        "Cash-on-Cash (%)": round((cashflow / mdf_totale * 100) if mdf_totale > 0 else 0, 2),
        "Mise de fonds totale": round(mdf_totale, 2),
    }


def projection_10_ans(prix, revenus_bruts_annuels, depenses_exploitation_an1, noi_an1,
    taux_inoccupation=5.0, mise_de_fonds_pct=20.0, taux_interet=5.0, amortissement=25,
    croissance_loyers=3.0, inflation_depenses=2.0, appreciation_immeuble=3.0,
    mise_de_fonds_totale=0.0, annees=10):
    hypotheque = prix * (1 - mise_de_fonds_pct / 100)
    amor = tableau_amortissement(hypotheque, taux_interet, amortissement, annees)
    projection, cashflow_cumule = [], 0.0
    rev_bruts, dep, val_imm = revenus_bruts_annuels, depenses_exploitation_an1, prix
    flux = [-mise_de_fonds_totale]
    for i in range(annees):
        if i > 0:
            rev_bruts *= (1 + croissance_loyers / 100)
            dep *= (1 + inflation_depenses / 100)
        vac = rev_bruts * (taux_inoccupation / 100)
        rev_nets = rev_bruts - vac
        noi = rev_nets - dep
        sd = amor[i]["Paiement annuel"]
        cf = noi - sd
        cashflow_cumule += cf
        if i > 0:
            val_imm *= (1 + appreciation_immeuble / 100)
        solde_hyp = amor[i]["Solde restant"]
        equite = val_imm - solde_hyp
        projection.append({"Année": i+1, "Revenus bruts": round(rev_bruts, 2),
            "Revenus nets": round(rev_nets, 2), "Dépenses": round(dep, 2),
            "NOI": round(noi, 2), "Service de dette": round(sd, 2),
            "Cashflow": round(cf, 2), "Cashflow cumulé": round(cashflow_cumule, 2),
            "Valeur immeuble": round(val_imm, 2), "Solde hypothèque": round(solde_hyp, 2),
            "Équité": round(equite, 2)})
        flux.append(cf if i < annees - 1 else cf + val_imm - solde_hyp)
    tri, van = None, None
    if _HAS_NPF:
        try:
            t = npf.irr(flux)
            if not np.isnan(t): tri = round(t * 100, 2)
        except Exception: pass
        try: van = round(npf.npv(taux_interet / 100, flux), 2)
        except Exception: pass
    rend_cum = None
    if mise_de_fonds_totale > 0:
        gain = cashflow_cumule + (val_imm - prix) + (hypotheque - projection[-1]["Solde hypothèque"])
        rend_cum = round(gain / mise_de_fonds_totale * 100, 2)
    return {"projection": projection, "TRI (%)": tri, "VAN ($)": van,
        "Cashflow cumulé": round(cashflow_cumule, 2), "Équité finale": round(projection[-1]["Équité"], 2),
        "Valeur projetée": round(val_imm, 2), "Rendement cumulé (%)": rend_cum}


def calculer_indicateurs(prix, noi, cashflow, mise_de_fonds_totale, service_dette,
    revenus_nets, taux_interet=5.0, hypotheque=0.0):
    cap_rate = (noi / prix * 100) if prix > 0 else 0
    coc = (cashflow / mise_de_fonds_totale * 100) if mise_de_fonds_totale > 0 else 0
    csd = revenus_nets / service_dette if service_dette > 0 else 0
    ltv = (hypotheque / prix * 100) if prix > 0 else 0
    delai = (mise_de_fonds_totale / cashflow) if cashflow > 0 else float("inf")
    grm = prix / (noi / (1 - 0.05)) if noi > 0 else 0
    sens = {}
    for delta in [-1.0, -0.5, 0.5, 1.0]:
        nt = taux_interet + delta
        if nt > 0:
            sens[f"{nt:.1f}%"] = round(noi - calculer_paiement_hypothecaire(hypotheque, nt) * 12, 2)
    return {"Cap Rate (%)": round(cap_rate, 2), "Cash-on-Cash (%)": round(coc, 2),
        "CSD": round(csd, 3), "LTV (%)": round(ltv, 1),
        "Délai de récupération (années)": round(delai, 1) if delai != float("inf") else "∞",
        "GRM": round(grm, 2), "Sensibilité taux d'intérêt": sens}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    MODULE SCRAPER — EXTRACTION DONNÉES                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

def detecter_plateforme(url):
    d = urlparse(url).netloc.lower()
    if "centris" in d: return "centris"
    elif "duproprio" in d: return "duproprio"
    elif "lespacs" in d: return "lespacs"
    return None

def _nettoyer_prix(texte):
    if not texte: return None
    c = re.sub(r"[^\d,.]", "", texte).replace(",", "").replace(" ", "")
    try: return float(c)
    except: return None

def _telecharger_page(url):
    try:
        r = requests.get(url, headers=HEADERS_HTTP, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except: return None

def _scraper_generique(url, plateforme):
    res = {"plateforme": plateforme, "url": url, "prix": None, "type_immeuble": None,
        "nb_logements": None, "adresse": None, "ville": None, "revenus_bruts": None,
        "depenses": None, "erreur": None}
    soup = _telecharger_page(url)
    if soup is None:
        res["erreur"] = f"Impossible de charger la page {plateforme}. Veuillez saisir les données manuellement."
        return res
    prix_el = soup.find("span", class_=re.compile(r"price|prix", re.I))
    if prix_el: res["prix"] = _nettoyer_prix(prix_el.get_text())
    if res["prix"] is None:
        meta = soup.find("meta", {"property": "og:price:amount"})
        if meta: res["prix"] = _nettoyer_prix(meta.get("content", ""))
    adr_el = soup.find(["h1", "h2"], class_=re.compile(r"address|adresse|listing-location", re.I))
    if adr_el: res["adresse"] = adr_el.get_text(strip=True)
    if res["adresse"] is None:
        meta_t = soup.find("meta", {"property": "og:title"})
        if meta_t: res["adresse"] = meta_t.get("content", "")
    title = soup.find("title")
    if title:
        for mot in ["Duplex", "Triplex", "Quadruplex", "Quintuplex", "Immeuble", "Plex"]:
            if mot.lower() in title.get_text().lower():
                res["type_immeuble"] = mot
                break
    if res["prix"] is None and res["adresse"] is None:
        res["erreur"] = f"Le scraping de {plateforme} a partiellement échoué. Veuillez compléter manuellement."
    return res

def extraire_donnees(url):
    p = detecter_plateforme(url)
    if p in ("centris", "duproprio"): return _scraper_generique(url, p.capitalize())
    if p == "lespacs":
        return {"plateforme": "LesPACs", "url": url, "prix": None, "type_immeuble": None,
            "nb_logements": None, "adresse": None, "ville": None, "revenus_bruts": None,
            "depenses": None, "erreur": "LesPACs n'est plus actif pour l'immobilier résidentiel. Saisie manuelle requise."}
    return {"plateforme": "Inconnue", "url": url, "prix": None, "type_immeuble": None,
        "nb_logements": None, "adresse": None, "ville": None, "revenus_bruts": None,
        "depenses": None, "erreur": "Plateforme non reconnue. Plateformes supportées : Centris, DuProprio, LesPACs."}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    MODULE LOCALISATION — SCORE /10                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

CRITERES = {
    "croissance_demographique": {"label": "📈 Croissance démographique",
        "description": "La population du secteur est-elle en croissance ?", "poids": 1.5,
        "options": {"Forte croissance (> 3%/an)": 10, "Croissance modérée (1-3%/an)": 7, "Stable": 5, "Déclin léger": 3, "Déclin important": 1}},
    "niveau_loyers": {"label": "💰 Niveau des loyers",
        "description": "Les loyers sont-ils compétitifs dans le secteur ?", "poids": 1.5,
        "options": {"Très élevés (forte demande)": 10, "Au-dessus de la moyenne": 8, "Dans la moyenne": 6, "Sous la moyenne": 3, "Très bas": 1}},
    "taux_inoccupation": {"label": "🏚️ Taux d'inoccupation",
        "description": "Quel est le taux d'inoccupation du secteur ?", "poids": 2.0,
        "options": {"Très faible (< 1%)": 10, "Faible (1-3%)": 8, "Modéré (3-5%)": 6, "Élevé (5-8%)": 3, "Très élevé (> 8%)": 1}},
    "transport": {"label": "🚌 Transport en commun",
        "description": "Accessibilité au transport en commun ?", "poids": 1.0,
        "options": {"Excellent (métro/train à pied)": 10, "Bon (bus fréquent)": 7, "Moyen": 5, "Limité": 3, "Inexistant": 1}},
    "ecoles": {"label": "🏫 Écoles et services",
        "description": "Proximité des écoles, garderies et services ?", "poids": 1.0,
        "options": {"Excellent (tout à pied)": 10, "Bon": 7, "Moyen": 5, "Limité": 3, "Très limité": 1}},
    "commerces": {"label": "🛒 Commerces et commodités",
        "description": "Accès aux commerces, épiceries, restaurants ?", "poids": 1.0,
        "options": {"Excellent (quartier commercial)": 10, "Bon": 7, "Moyen": 5, "Limité": 3, "Très limité": 1}},
    "securite": {"label": "🔒 Sécurité du quartier",
        "description": "Le quartier est-il considéré sécuritaire ?", "poids": 1.5,
        "options": {"Très sécuritaire": 10, "Sécuritaire": 8, "Moyen": 5, "Problématique": 3, "Dangereux": 1}},
    "risque_locatif": {"label": "⚠️ Risque locatif",
        "description": "Risque de mauvais payeurs ou de litiges ?", "poids": 1.5,
        "options": {"Très faible": 10, "Faible": 8, "Modéré": 5, "Élevé": 3, "Très élevé": 1}},
}

def calculer_score_localisation(reponses):
    details, total_p, total_w = [], 0.0, 0.0
    for cid, info in CRITERES.items():
        opt = reponses.get(cid)
        if opt is None: continue
        s = info["options"].get(opt, 5)
        w = info["poids"]
        total_p += s * w
        total_w += w
        details.append({"Critère": info["label"], "Réponse": opt, "Score": s, "Poids": w, "Score pondéré": round(s * w, 1)})
    score = round(total_p / total_w, 1) if total_w > 0 else 0
    if score >= 8.5: appr, coul = "🟢 Excellent emplacement", "#00c853"
    elif score >= 7.0: appr, coul = "🟢 Bon emplacement", "#64dd17"
    elif score >= 5.5: appr, coul = "🟡 Emplacement correct", "#ffd600"
    elif score >= 4.0: appr, coul = "🟠 Emplacement à risque modéré", "#ff9100"
    else: appr, coul = "🔴 Emplacement à risque élevé", "#ff1744"
    vals = {info["label"]: info["options"].get(reponses.get(cid, ""), 0) for cid, info in CRITERES.items()}
    return {"score_global": score, "appreciation": appr, "couleur": coul, "details": details, "valeurs_radar": vals}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                    APPLICATION STREAMLIT — UI PRINCIPALE                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

st.set_page_config(page_title="🏠 Analyseur Immobilier", page_icon="🏠", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
    .main-header { background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%); padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem; color: white; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
    .main-header h1 { font-size: 2.2rem; font-weight: 800; margin: 0; letter-spacing: -0.5px; }
    .main-header p { font-size: 1rem; opacity: 0.85; margin-top: 0.5rem; }
    .score-badge { display: inline-block; font-size: 3rem; font-weight: 800; padding: 1rem 2rem; border-radius: 16px; margin: 1rem 0; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; font-weight: 600; font-size: 0.95rem; padding: 10px 20px; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0f2027 0%, #203a43 100%); }
    [data-testid="stSidebar"] .stMarkdown h2, [data-testid="stSidebar"] .stMarkdown h3 { color: #64ffda; }
    div[data-testid="stMetric"] { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1rem; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
    .section-divider { border: none; height: 1px; background: linear-gradient(90deg, transparent, #64ffda44, transparent); margin: 2rem 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏠 Analyseur de Rentabilité Immobilière</h1>
    <p>Analysez la rentabilité d'un immeuble résidentiel au Québec — Année 1, projection 10 ans, localisation et indicateurs financiers</p>
</div>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
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
    st.caption("Application développée pour analyser la rentabilité d'immeubles résidentiels au Québec. Barèmes 2026.")

# --- SAISIE DES DONNÉES ---
st.markdown("## 🔗 Source des données")
col_url, col_btn = st.columns([4, 1])
with col_url:
    url_input = st.text_input("Collez l'URL d'une annonce (Centris, DuProprio, LesPACs)",
        placeholder="https://www.centris.ca/fr/...", label_visibility="collapsed")
with col_btn:
    btn_scrape = st.button("🔍 Analyser l'URL", use_container_width=True)

donnees_scrapees = None
if btn_scrape and url_input:
    with st.spinner("Extraction des données en cours..."):
        donnees_scrapees = extraire_donnees(url_input)
    if donnees_scrapees.get("erreur"):
        st.warning(f"⚠️ {donnees_scrapees['erreur']}")
    else:
        st.success(f"✅ Données extraites de {donnees_scrapees.get('plateforme', 'la plateforme')}")

prix_defaut = int(donnees_scrapees["prix"]) if donnees_scrapees and donnees_scrapees.get("prix") else 0

st.markdown("### 📝 Données de l'immeuble")
st.caption("Remplissez ou complétez les informations ci-dessous.")
col1, col2, col3 = st.columns(3)
with col1:
    prix_achat = st.number_input("💲 Prix d'achat ($)", min_value=0, value=prix_defaut, step=5000)
    nb_logements = st.number_input("🏘️ Nombre de logements", min_value=1, value=4, step=1)
with col2:
    loyer_moyen = st.number_input("💰 Loyer moyen par logement ($/mois)", min_value=0, value=800, step=50)
    type_immeuble = st.selectbox("🏠 Type d'immeuble", ["Duplex", "Triplex", "Quadruplex", "Quintuplex", "6-plex", "Immeuble (7+ logements)", "Autre"])
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

# --- CALCULS ET AFFICHAGE ---
if prix_achat > 0 and revenus_bruts_annuels > 0:
    couts_init = calculer_couts_initiaux(prix=prix_achat, mise_de_fonds_pct=mise_de_fonds_pct,
        frais_notaire=frais_notaire, frais_inspection=frais_inspection, frais_evaluation=frais_evaluation,
        frais_comptable=frais_comptable, travaux_initiaux=travaux_initiaux, frais_financement=frais_financement,
        bareme_mutation=bareme_mutation)
    depenses_exploitation = (taxes_municipales + taxes_scolaires + assurances + entretien
        + (revenus_bruts_annuels * (1 - taux_inoccupation/100) * gestion_pct / 100) + autres_depenses)
    an1 = analyse_annee_1(prix=prix_achat, revenus_bruts_annuels=revenus_bruts_annuels,
        taux_inoccupation=taux_inoccupation, taxes_municipales=taxes_municipales,
        taxes_scolaires=taxes_scolaires, assurances=assurances, entretien=entretien,
        gestion_pct=gestion_pct, autres_depenses=autres_depenses, mise_de_fonds_pct=mise_de_fonds_pct,
        taux_interet=taux_interet, amortissement=amortissement, couts_initiaux=couts_init)
    proj = projection_10_ans(prix=prix_achat, revenus_bruts_annuels=revenus_bruts_annuels,
        depenses_exploitation_an1=depenses_exploitation, noi_an1=an1["NOI"],
        taux_inoccupation=taux_inoccupation, mise_de_fonds_pct=mise_de_fonds_pct,
        taux_interet=taux_interet, amortissement=amortissement, croissance_loyers=croissance_loyers,
        inflation_depenses=inflation_depenses, appreciation_immeuble=appreciation_immeuble,
        mise_de_fonds_totale=couts_init["Total coûts initiaux"])
    indicateurs = calculer_indicateurs(prix=prix_achat, noi=an1["NOI"], cashflow=an1["Cashflow"],
        mise_de_fonds_totale=couts_init["Total coûts initiaux"], service_dette=an1["Service de dette"],
        revenus_nets=an1["Revenus nets"], taux_interet=taux_interet, hypotheque=an1["Hypothèque"])

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Année 1", "📈 Projection 10 ans", "📍 Localisation", "📊 Indicateurs"])

    # --- ONGLET 1: ANNÉE 1 ---
    with tab1:
        st.markdown("## 📋 Analyse de la première année")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("💵 Cashflow annuel", f"{an1['Cashflow']:,.2f} $", delta=f"{an1['Cashflow']/12:,.0f} $/mois",
                delta_color="normal" if an1["Cashflow"] >= 0 else "inverse")
        with m2:
            st.metric("📊 CSD (ratio)", f"{an1['CSD']:.3f}",
                delta="≥ 1.20 recommandé" if an1['CSD'] >= 1.2 else "< 1.20 ⚠️",
                delta_color="normal" if an1['CSD'] >= 1.2 else "inverse")
        with m3:
            st.metric("🏦 LTV", f"{an1['LTV']:.1f} %")
        with m4:
            st.metric("💰 Rendement MDF", f"{an1['Rendement mise de fonds (%)']:.2f} %",
                delta_color="normal" if an1["Rendement mise de fonds (%)"] >= 0 else "inverse")
        st.markdown("")
        m5, m6, m7, m8 = st.columns(4)
        with m5: st.metric("🏠 Cap Rate", f"{an1['Cap Rate (%)']:.2f} %")
        with m6: st.metric("💵 Cash-on-Cash", f"{an1['Cash-on-Cash (%)']:.2f} %")
        with m7: st.metric("📈 NOI", f"{an1['NOI']:,.2f} $")
        with m8: st.metric("🏦 Service de dette", f"{an1['Service de dette']:,.2f} $")
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("#### 💸 Répartition des coûts initiaux")
            couts_df = pd.DataFrame([{"Poste": k, "Montant": v} for k, v in couts_init.items() if k != "Total coûts initiaux" and v > 0])
            if not couts_df.empty:
                fig_c = px.pie(couts_df, values="Montant", names="Poste", hole=0.45, color_discrete_sequence=px.colors.sequential.Tealgrn)
                fig_c.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"), showlegend=True, margin=dict(t=20, b=20))
                st.plotly_chart(fig_c, use_container_width=True)
            st.markdown(f"**Total coûts initiaux : {couts_init['Total coûts initiaux']:,.2f} $**")
        with col_g2:
            st.markdown("#### 📊 Revenus vs Dépenses (Année 1)")
            rev_dep = pd.DataFrame({"Catégorie": ["Revenus bruts", "Vacance", "Dépenses exploitation", "Service de dette", "Cashflow"],
                "Montant": [an1["Revenus bruts"], -an1["Vacance"], -an1["Depenses exploitation"], -an1["Service de dette"], an1["Cashflow"]]})
            colors = ["#64ffda", "#ff6b6b", "#ff9100", "#ffd93d", "#00c853" if an1["Cashflow"] >= 0 else "#ff1744"]
            fig_r = go.Figure(go.Bar(x=rev_dep["Catégorie"], y=rev_dep["Montant"], marker_color=colors,
                text=[f"{v:,.0f} $" for v in rev_dep["Montant"]], textposition="outside"))
            fig_r.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), margin=dict(t=20, b=20), height=400)
            st.plotly_chart(fig_r, use_container_width=True)

    # --- ONGLET 2: PROJECTION 10 ANS ---
    with tab2:
        st.markdown("## 📈 Projection sur 10 ans")
        pm1, pm2, pm3, pm4 = st.columns(4)
        with pm1: st.metric("📈 TRI", f"{proj['TRI (%)']:.2f} %" if proj["TRI (%)"] is not None else "N/A")
        with pm2: st.metric("💰 VAN", f"{proj['VAN ($)']:,.2f} $" if proj["VAN ($)"] is not None else "N/A")
        with pm3: st.metric("📊 Cashflow cumulé (10 ans)", f"{proj['Cashflow cumulé']:,.2f} $")
        with pm4: st.metric("🏠 Équité finale", f"{proj['Équité finale']:,.2f} $")
        pm5, pm6 = st.columns(2)
        with pm5: st.metric("🏡 Valeur projetée (an 10)", f"{proj['Valeur projetée']:,.2f} $")
        with pm6: st.metric("💵 Rendement cumulé", f"{proj['Rendement cumulé (%)']:.2f} %" if proj["Rendement cumulé (%)"] is not None else "N/A")
        st.markdown("---")
        df_proj = pd.DataFrame(proj["projection"])
        st.markdown("#### 📋 Tableau détaillé")
        st.dataframe(df_proj.style.format({"Revenus bruts": "{:,.0f} $", "Revenus nets": "{:,.0f} $", "Dépenses": "{:,.0f} $",
            "NOI": "{:,.0f} $", "Service de dette": "{:,.0f} $", "Cashflow": "{:,.0f} $", "Cashflow cumulé": "{:,.0f} $",
            "Valeur immeuble": "{:,.0f} $", "Solde hypothèque": "{:,.0f} $", "Équité": "{:,.0f} $"}),
            use_container_width=True, hide_index=True)
        st.markdown("---")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown("#### 💵 Cashflow annuel et cumulé")
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(x=df_proj["Année"], y=df_proj["Cashflow"], name="Cashflow annuel", marker_color="#64ffda"))
            fig_cf.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Cashflow cumulé"], name="Cashflow cumulé", line=dict(color="#ffd93d", width=3), mode="lines+markers"))
            fig_cf.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), legend=dict(orientation="h", y=-0.15), margin=dict(t=20, b=40), height=400)
            st.plotly_chart(fig_cf, use_container_width=True)
        with col_p2:
            st.markdown("#### 🏠 Valeur immeuble vs Hypothèque")
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Valeur immeuble"], name="Valeur immeuble", fill="tozeroy", line=dict(color="#64ffda", width=2)))
            fig_eq.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Solde hypothèque"], name="Solde hypothèque", fill="tozeroy", line=dict(color="#ff6b6b", width=2)))
            fig_eq.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Équité"], name="Équité", line=dict(color="#ffd93d", width=3, dash="dash"), mode="lines+markers"))
            fig_eq.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), legend=dict(orientation="h", y=-0.15), margin=dict(t=20, b=40), height=400)
            st.plotly_chart(fig_eq, use_container_width=True)
        st.markdown("#### 📊 Évolution revenus nets vs dépenses")
        fig_ev = go.Figure()
        fig_ev.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Revenus nets"], name="Revenus nets", line=dict(color="#64ffda", width=2), mode="lines+markers"))
        fig_ev.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["Dépenses"], name="Dépenses", line=dict(color="#ff6b6b", width=2), mode="lines+markers"))
        fig_ev.add_trace(go.Scatter(x=df_proj["Année"], y=df_proj["NOI"], name="NOI", line=dict(color="#ffd93d", width=3), mode="lines+markers"))
        fig_ev.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), legend=dict(orientation="h", y=-0.15), margin=dict(t=20, b=40), height=400)
        st.plotly_chart(fig_ev, use_container_width=True)

    # --- ONGLET 3: LOCALISATION ---
    with tab3:
        st.markdown("## 📍 Analyse de la localisation")
        if ville:
            st.markdown(f"**Emplacement analysé :** {adresse}, {ville}" if adresse else f"**Secteur :** {ville}")
        st.markdown("Évaluez chaque critère pour obtenir un score de localisation global.")
        st.markdown("")
        reponses = {}
        critere_ids = list(CRITERES.keys())
        col_loc1, col_loc2 = st.columns(2)
        for i, cid in enumerate(critere_ids):
            info = CRITERES[cid]
            col = col_loc1 if i % 2 == 0 else col_loc2
            with col:
                reponses[cid] = st.selectbox(info["label"], options=list(info["options"].keys()), index=2, help=info["description"], key=f"loc_{cid}")
        st.markdown("---")
        resultat_loc = calculer_score_localisation(reponses)
        col_score, col_radar = st.columns([1, 2])
        with col_score:
            score = resultat_loc["score_global"]
            couleur = resultat_loc["couleur"]
            st.markdown(f'<div class="score-badge" style="background:{couleur}22; border: 2px solid {couleur}; color:{couleur}">{score}/10</div>', unsafe_allow_html=True)
            st.markdown(f"### {resultat_loc['appreciation']}")
        with col_radar:
            labels = list(resultat_loc["valeurs_radar"].keys())
            values = list(resultat_loc["valeurs_radar"].values())
            fig_rad = go.Figure()
            fig_rad.add_trace(go.Scatterpolar(r=values + [values[0]], theta=labels + [labels[0]], fill="toself",
                fillcolor="rgba(100, 255, 218, 0.2)", line=dict(color="#64ffda", width=2), marker=dict(size=6)))
            fig_rad.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10], gridcolor="rgba(255,255,255,0.1)"),
                angularaxis=dict(gridcolor="rgba(255,255,255,0.1)"), bgcolor="rgba(0,0,0,0)"),
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white", size=11), margin=dict(t=40, b=40), height=450, showlegend=False)
            st.plotly_chart(fig_rad, use_container_width=True)
        st.markdown("#### 📋 Détail des scores")
        df_loc = pd.DataFrame(resultat_loc["details"])
        st.dataframe(df_loc.style.format({"Score": "{:.0f}", "Poids": "{:.1f}", "Score pondéré": "{:.1f}"}), use_container_width=True, hide_index=True)

    # --- ONGLET 4: INDICATEURS ---
    with tab4:
        st.markdown("## 📊 Indicateurs financiers")
        i1, i2, i3 = st.columns(3)
        with i1: st.metric("📈 Cap Rate", f"{indicateurs['Cap Rate (%)']:.2f} %")
        with i2: st.metric("💵 Cash-on-Cash", f"{indicateurs['Cash-on-Cash (%)']:.2f} %")
        with i3: st.metric("📊 CSD", f"{indicateurs['CSD']:.3f}")
        i4, i5, i6 = st.columns(3)
        with i4: st.metric("🏦 LTV", f"{indicateurs['LTV (%)']:.1f} %")
        with i5:
            delai = indicateurs["Délai de récupération (années)"]
            st.metric("⏱️ Délai de récupération", f"{delai} ans" if delai != "∞" else "∞")
        with i6: st.metric("📐 GRM", f"{indicateurs['GRM']:.2f}")
        st.markdown("---")
        st.markdown("#### 📋 Récapitulatif complet")
        dep_expl_val = an1["Depenses exploitation"]
        recap_data = {"Indicateur": ["Prix d'achat", "Mise de fonds totale (avec frais)", "Hypothèque",
            "Paiement hypothécaire mensuel", "Revenus bruts annuels", "Revenus nets (après vacance)",
            "Dépenses d'exploitation", "NOI (revenu net d'exploitation)", "Service de dette annuel",
            "Cashflow annuel", "Cashflow mensuel"],
            "Valeur": [f"{prix_achat:,.2f} $", f"{couts_init['Total coûts initiaux']:,.2f} $",
                f"{an1['Hypothèque']:,.2f} $",
                f"{calculer_paiement_hypothecaire(an1['Hypothèque'], taux_interet, amortissement):,.2f} $",
                f"{an1['Revenus bruts']:,.2f} $", f"{an1['Revenus nets']:,.2f} $",
                f"{dep_expl_val:,.2f} $", f"{an1['NOI']:,.2f} $",
                f"{an1['Service de dette']:,.2f} $", f"{an1['Cashflow']:,.2f} $",
                f"{an1['Cashflow']/12:,.2f} $"]}
        st.dataframe(pd.DataFrame(recap_data), use_container_width=True, hide_index=True)
        st.markdown("---")
        st.markdown("#### 🎛️ Sensibilité aux taux d'intérêt")
        st.caption("Impact d'une variation du taux d'intérêt sur le cashflow annuel")
        sensibilite = indicateurs["Sensibilité taux d'intérêt"]
        if sensibilite:
            taux_labels = list(sensibilite.keys())
            cashflows_sens = list(sensibilite.values())
            fig_s = go.Figure(go.Bar(x=taux_labels, y=cashflows_sens,
                marker_color=["#64ffda" if cf >= 0 else "#ff6b6b" for cf in cashflows_sens],
                text=[f"{cf:,.0f} $" for cf in cashflows_sens], textposition="outside"))
            fig_s.update_layout(xaxis_title="Taux d'intérêt", yaxis_title="Cashflow annuel ($)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)"), margin=dict(t=20, b=40), height=400)
            fig_s.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
            fig_s.add_vline(x=f"{taux_interet:.1f}%", line_dash="dot", line_color="#ffd93d",
                annotation_text="Taux actuel", annotation_font_color="#ffd93d")
            st.plotly_chart(fig_s, use_container_width=True)
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
