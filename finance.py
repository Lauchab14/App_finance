"""
Module de calculs financiers pour l'analyse de rentabilité immobilière.
Inclut : droits de mutation, analyse année 1, projection 10 ans, indicateurs.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Tentative d'import de numpy_financial (optionnel)
# ---------------------------------------------------------------------------
try:
    import numpy_financial as npf
    _HAS_NPF = True
except ImportError:
    _HAS_NPF = False


# ═══════════════════════════════════════════════════════════════════════════
# 1. DROITS DE MUTATION (TAXE DE BIENVENUE) — QUÉBEC 2026
# ═══════════════════════════════════════════════════════════════════════════

# Barème général Québec 2026
TRANCHES_MUTATION_QC_2026 = [
    (62_900, 0.005),
    (315_000, 0.01),
    (float("inf"), 0.015),
]

# Barème Montréal 2026 (tranches supplémentaires)
TRANCHES_MUTATION_MTL_2026 = [
    (62_900, 0.005),
    (315_000, 0.01),
    (500_000, 0.015),
    (1_000_000, 0.02),
    (2_000_000, 0.025),
    (3_113_000, 0.035),
    (float("inf"), 0.04),
]

# Barème Québec (ville) 2026
TRANCHES_MUTATION_QCV_2026 = [
    (62_900, 0.005),
    (315_000, 0.01),
    (500_000, 0.015),
    (750_000, 0.025),
    (float("inf"), 0.03),
]

BAREMES = {
    "Québec (général)": TRANCHES_MUTATION_QC_2026,
    "Montréal": TRANCHES_MUTATION_MTL_2026,
    "Ville de Québec": TRANCHES_MUTATION_QCV_2026,
}


def calculer_droits_mutation(prix: float, bareme: str = "Québec (général)") -> float:
    """Calcule les droits de mutation (taxe de bienvenue) selon le barème choisi."""
    tranches = BAREMES.get(bareme, TRANCHES_MUTATION_QC_2026)
    taxe = 0.0
    seuil_precedent = 0.0
    for seuil, taux in tranches:
        if prix <= seuil_precedent:
            break
        montant_tranche = min(prix, seuil) - seuil_precedent
        taxe += montant_tranche * taux
        seuil_precedent = seuil
    return round(taxe, 2)


# ═══════════════════════════════════════════════════════════════════════════
# 2. COÛTS INITIAUX NON RÉCURRENTS
# ═══════════════════════════════════════════════════════════════════════════

def calculer_couts_initiaux(
    prix: float,
    mise_de_fonds_pct: float = 20.0,
    frais_notaire: float = 2000.0,
    frais_inspection: float = 800.0,
    frais_evaluation: float = 500.0,
    frais_comptable: float = 500.0,
    travaux_initiaux: float = 0.0,
    frais_financement: float = 0.0,
    bareme_mutation: str = "Québec (général)",
) -> dict:
    """Calcule tous les coûts initiaux non récurrents."""
    mise_de_fonds = prix * (mise_de_fonds_pct / 100)
    droits_mutation = calculer_droits_mutation(prix, bareme_mutation)

    couts = {
        "Mise de fonds": mise_de_fonds,
        "Droits de mutation": droits_mutation,
        "Frais de notaire": frais_notaire,
        "Inspection": frais_inspection,
        "Évaluation bancaire": frais_evaluation,
        "Honoraires comptables": frais_comptable,
        "Travaux initiaux": travaux_initiaux,
        "Frais de financement": frais_financement,
    }
    couts["Total coûts initiaux"] = sum(couts.values())
    return couts


# ═══════════════════════════════════════════════════════════════════════════
# 3. SERVICE DE DETTE (HYPOTHÈQUE)
# ═══════════════════════════════════════════════════════════════════════════

def calculer_paiement_hypothecaire(
    montant: float,
    taux_annuel: float,
    amortissement_annees: int = 25,
) -> float:
    """Calcule le paiement hypothécaire mensuel."""
    if montant <= 0 or taux_annuel <= 0:
        return 0.0
    taux_mensuel = taux_annuel / 100 / 12
    n = amortissement_annees * 12
    paiement = montant * (taux_mensuel * (1 + taux_mensuel) ** n) / (
        (1 + taux_mensuel) ** n - 1
    )
    return round(paiement, 2)


def tableau_amortissement(
    montant: float,
    taux_annuel: float,
    amortissement_annees: int = 25,
    annees: int = 10,
) -> list[dict]:
    """Génère un tableau d'amortissement annuel sur N années."""
    taux_mensuel = taux_annuel / 100 / 12
    paiement_mensuel = calculer_paiement_hypothecaire(
        montant, taux_annuel, amortissement_annees
    )
    solde = montant
    tableau = []
    for annee in range(1, annees + 1):
        interet_annuel = 0.0
        capital_annuel = 0.0
        for _ in range(12):
            interet = solde * taux_mensuel
            capital = paiement_mensuel - interet
            interet_annuel += interet
            capital_annuel += capital
            solde -= capital
        tableau.append({
            "Année": annee,
            "Paiement annuel": round(paiement_mensuel * 12, 2),
            "Intérêts": round(interet_annuel, 2),
            "Capital remboursé": round(capital_annuel, 2),
            "Solde restant": round(max(solde, 0), 2),
        })
    return tableau


# ═══════════════════════════════════════════════════════════════════════════
# 4. ANALYSE ANNÉE 1
# ═══════════════════════════════════════════════════════════════════════════

def analyse_annee_1(
    prix: float,
    revenus_bruts_annuels: float,
    taux_inoccupation: float = 5.0,
    taxes_municipales: float = 0.0,
    taxes_scolaires: float = 0.0,
    assurances: float = 0.0,
    entretien: float = 0.0,
    gestion_pct: float = 0.0,
    autres_depenses: float = 0.0,
    mise_de_fonds_pct: float = 20.0,
    taux_interet: float = 5.0,
    amortissement: int = 25,
    couts_initiaux: dict | None = None,
) -> dict:
    """Analyse financière complète de la première année."""
    # Revenus nets
    vacance = revenus_bruts_annuels * (taux_inoccupation / 100)
    revenus_nets = revenus_bruts_annuels - vacance

    # Frais de gestion
    frais_gestion = revenus_nets * (gestion_pct / 100)

    # Dépenses d'exploitation totales
    depenses = (
        taxes_municipales + taxes_scolaires + assurances
        + entretien + frais_gestion + autres_depenses
    )

    # NOI (Net Operating Income)
    noi = revenus_nets - depenses

    # Service de dette
    hypotheque = prix * (1 - mise_de_fonds_pct / 100)
    paiement_mensuel = calculer_paiement_hypothecaire(
        hypotheque, taux_interet, amortissement
    )
    service_dette_annuel = paiement_mensuel * 12

    # Cashflow
    cashflow = noi - service_dette_annuel

    # Mise de fonds totale
    if couts_initiaux is None:
        mise_de_fonds_totale = prix * (mise_de_fonds_pct / 100)
    else:
        mise_de_fonds_totale = couts_initiaux.get("Total coûts initiaux", prix * (mise_de_fonds_pct / 100))

    # Ratios
    csd = revenus_nets / service_dette_annuel if service_dette_annuel > 0 else 0
    ltv = hypotheque / prix if prix > 0 else 0
    rendement_mdf = (cashflow / mise_de_fonds_totale * 100) if mise_de_fonds_totale > 0 else 0
    cap_rate = (noi / prix * 100) if prix > 0 else 0
    cash_on_cash = (cashflow / mise_de_fonds_totale * 100) if mise_de_fonds_totale > 0 else 0

    return {
        "Revenus bruts": round(revenus_bruts_annuels, 2),
        "Vacance": round(vacance, 2),
        "Revenus nets": round(revenus_nets, 2),
        "Dépenses d'exploitation": round(depenses, 2),
        "NOI": round(noi, 2),
        "Service de dette": round(service_dette_annuel, 2),
        "Cashflow": round(cashflow, 2),
        "Hypothèque": round(hypotheque, 2),
        "CSD": round(csd, 3),
        "LTV": round(ltv * 100, 1),
        "Rendement mise de fonds (%)": round(rendement_mdf, 2),
        "Cap Rate (%)": round(cap_rate, 2),
        "Cash-on-Cash (%)": round(cash_on_cash, 2),
        "Mise de fonds totale": round(mise_de_fonds_totale, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. PROJECTION 10 ANS
# ═══════════════════════════════════════════════════════════════════════════

def projection_10_ans(
    prix: float,
    revenus_bruts_annuels: float,
    depenses_exploitation_an1: float,
    noi_an1: float,
    taux_inoccupation: float = 5.0,
    mise_de_fonds_pct: float = 20.0,
    taux_interet: float = 5.0,
    amortissement: int = 25,
    croissance_loyers: float = 3.0,
    inflation_depenses: float = 2.0,
    appreciation_immeuble: float = 3.0,
    mise_de_fonds_totale: float = 0.0,
    annees: int = 10,
) -> dict:
    """Génère une projection financière sur N années."""
    hypotheque = prix * (1 - mise_de_fonds_pct / 100)
    amor = tableau_amortissement(hypotheque, taux_interet, amortissement, annees)

    projection = []
    cashflow_cumule = 0.0
    revenus_bruts = revenus_bruts_annuels
    depenses = depenses_exploitation_an1
    valeur_immeuble = prix
    flux_tresorerie = [-mise_de_fonds_totale]  # Pour le calcul du TRI

    for i in range(annees):
        if i > 0:
            revenus_bruts *= (1 + croissance_loyers / 100)
            depenses *= (1 + inflation_depenses / 100)

        vacance = revenus_bruts * (taux_inoccupation / 100)
        revenus_nets = revenus_bruts - vacance
        noi = revenus_nets - depenses
        service_dette = amor[i]["Paiement annuel"]
        cashflow = noi - service_dette
        cashflow_cumule += cashflow

        if i > 0:
            valeur_immeuble *= (1 + appreciation_immeuble / 100)

        solde_hypotheque = amor[i]["Solde restant"]
        equite = valeur_immeuble - solde_hypotheque

        projection.append({
            "Année": i + 1,
            "Revenus bruts": round(revenus_bruts, 2),
            "Revenus nets": round(revenus_nets, 2),
            "Dépenses": round(depenses, 2),
            "NOI": round(noi, 2),
            "Service de dette": round(service_dette, 2),
            "Cashflow": round(cashflow, 2),
            "Cashflow cumulé": round(cashflow_cumule, 2),
            "Valeur immeuble": round(valeur_immeuble, 2),
            "Solde hypothèque": round(solde_hypotheque, 2),
            "Équité": round(equite, 2),
        })

        # Flux pour TRI : cashflow chaque année, + valeur de revente la dernière année
        if i < annees - 1:
            flux_tresorerie.append(cashflow)
        else:
            # Dernière année : cashflow + produit de la vente (valeur - solde hypo)
            flux_tresorerie.append(cashflow + valeur_immeuble - solde_hypotheque)

    # Calcul TRI
    tri = None
    if _HAS_NPF:
        try:
            tri_val = npf.irr(flux_tresorerie)
            if not np.isnan(tri_val):
                tri = round(tri_val * 100, 2)
        except Exception:
            pass

    # Calcul VAN (taux d'actualisation = taux d'intérêt)
    van = None
    if _HAS_NPF:
        try:
            van_val = npf.npv(taux_interet / 100, flux_tresorerie)
            van = round(van_val, 2)
        except Exception:
            pass

    # Rendement cumulé
    rendement_cumule = None
    if mise_de_fonds_totale > 0:
        dernier = projection[-1]
        gain_total = cashflow_cumule + (valeur_immeuble - prix) + (hypotheque - dernier["Solde hypothèque"])
        rendement_cumule = round(gain_total / mise_de_fonds_totale * 100, 2)

    return {
        "projection": projection,
        "TRI (%)": tri,
        "VAN ($)": van,
        "Cashflow cumulé": round(cashflow_cumule, 2),
        "Équité finale": round(projection[-1]["Équité"], 2),
        "Valeur projetée": round(valeur_immeuble, 2),
        "Rendement cumulé (%)": rendement_cumule,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. INDICATEURS FINANCIERS SUPPLÉMENTAIRES
# ═══════════════════════════════════════════════════════════════════════════

def calculer_indicateurs(
    prix: float,
    noi: float,
    cashflow: float,
    mise_de_fonds_totale: float,
    service_dette: float,
    revenus_nets: float,
    taux_interet: float = 5.0,
    hypotheque: float = 0.0,
) -> dict:
    """Calcule tous les indicateurs financiers clés."""
    # Cap Rate
    cap_rate = (noi / prix * 100) if prix > 0 else 0

    # Cash-on-Cash Return
    cash_on_cash = (cashflow / mise_de_fonds_totale * 100) if mise_de_fonds_totale > 0 else 0

    # CSD (Debt Service Coverage Ratio)
    csd = revenus_nets / service_dette if service_dette > 0 else 0

    # LTV
    ltv = (hypotheque / prix * 100) if prix > 0 else 0

    # Délai de récupération (en années)
    delai_recuperation = (mise_de_fonds_totale / cashflow) if cashflow > 0 else float("inf")

    # Multiplicateur de revenus bruts (GRM)
    grm = prix / (noi / (1 - 0.05)) if noi > 0 else 0  # Approximation

    # Sensibilité aux taux d'intérêt
    sensibilite = {}
    for delta in [-1.0, -0.5, 0.5, 1.0]:
        nouveau_taux = taux_interet + delta
        if nouveau_taux > 0:
            nouveau_paiement = calculer_paiement_hypothecaire(hypotheque, nouveau_taux) * 12
            nouveau_cashflow = noi - nouveau_paiement
            sensibilite[f"{nouveau_taux:.1f}%"] = round(nouveau_cashflow, 2)

    return {
        "Cap Rate (%)": round(cap_rate, 2),
        "Cash-on-Cash (%)": round(cash_on_cash, 2),
        "CSD": round(csd, 3),
        "LTV (%)": round(ltv, 1),
        "Délai de récupération (années)": round(delai_recuperation, 1) if delai_recuperation != float("inf") else "∞",
        "GRM": round(grm, 2),
        "Sensibilité taux d'intérêt": sensibilite,
    }
