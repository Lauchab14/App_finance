"""
Module d'analyse de localisation pour l'évaluation immobilière.
Score de localisation basé sur des critères saisis par l'utilisateur.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CRITÈRES ET PONDÉRATIONS
# ═══════════════════════════════════════════════════════════════════════════

CRITERES = {
    "croissance_demographique": {
        "label": "📈 Croissance démographique",
        "description": "La population du secteur est-elle en croissance ?",
        "poids": 1.5,
        "options": {
            "Forte croissance (> 3%/an)": 10,
            "Croissance modérée (1-3%/an)": 7,
            "Stable": 5,
            "Déclin léger": 3,
            "Déclin important": 1,
        },
    },
    "niveau_loyers": {
        "label": "💰 Niveau des loyers",
        "description": "Les loyers sont-ils compétitifs dans le secteur ?",
        "poids": 1.5,
        "options": {
            "Très élevés (forte demande)": 10,
            "Au-dessus de la moyenne": 8,
            "Dans la moyenne": 6,
            "Sous la moyenne": 3,
            "Très bas": 1,
        },
    },
    "taux_inoccupation": {
        "label": "🏚️ Taux d'inoccupation",
        "description": "Quel est le taux d'inoccupation du secteur ?",
        "poids": 2.0,
        "options": {
            "Très faible (< 1%)": 10,
            "Faible (1-3%)": 8,
            "Modéré (3-5%)": 6,
            "Élevé (5-8%)": 3,
            "Très élevé (> 8%)": 1,
        },
    },
    "transport": {
        "label": "🚌 Transport en commun",
        "description": "Accessibilité au transport en commun ?",
        "poids": 1.0,
        "options": {
            "Excellent (métro/train à pied)": 10,
            "Bon (bus fréquent)": 7,
            "Moyen": 5,
            "Limité": 3,
            "Inexistant": 1,
        },
    },
    "ecoles": {
        "label": "🏫 Écoles et services",
        "description": "Proximité des écoles, garderies et services ?",
        "poids": 1.0,
        "options": {
            "Excellent (tout à pied)": 10,
            "Bon": 7,
            "Moyen": 5,
            "Limité": 3,
            "Très limité": 1,
        },
    },
    "commerces": {
        "label": "🛒 Commerces et commodités",
        "description": "Accès aux commerces, épiceries, restaurants ?",
        "poids": 1.0,
        "options": {
            "Excellent (quartier commercial)": 10,
            "Bon": 7,
            "Moyen": 5,
            "Limité": 3,
            "Très limité": 1,
        },
    },
    "securite": {
        "label": "🔒 Sécurité du quartier",
        "description": "Le quartier est-il considéré sécuritaire ?",
        "poids": 1.5,
        "options": {
            "Très sécuritaire": 10,
            "Sécuritaire": 8,
            "Moyen": 5,
            "Problématique": 3,
            "Dangereux": 1,
        },
    },
    "risque_locatif": {
        "label": "⚠️ Risque locatif",
        "description": "Risque de mauvais payeurs ou de litiges ?",
        "poids": 1.5,
        "options": {
            "Très faible": 10,
            "Faible": 8,
            "Modéré": 5,
            "Élevé": 3,
            "Très élevé": 1,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# CALCUL DU SCORE
# ═══════════════════════════════════════════════════════════════════════════

def calculer_score_localisation(reponses: dict[str, str]) -> dict:
    """
    Calcule le score de localisation à partir des réponses de l'utilisateur.

    Args:
        reponses: dict {critere_id: option_choisie}

    Returns:
        dict avec le score global, les scores par critère, et une appréciation.
    """
    scores_details = []
    total_pondere = 0.0
    total_poids = 0.0

    for critere_id, critere_info in CRITERES.items():
        option = reponses.get(critere_id)
        if option is None:
            continue

        score = critere_info["options"].get(option, 5)
        poids = critere_info["poids"]

        total_pondere += score * poids
        total_poids += poids

        scores_details.append({
            "Critère": critere_info["label"],
            "Réponse": option,
            "Score": score,
            "Poids": poids,
            "Score pondéré": round(score * poids, 1),
        })

    score_global = round(total_pondere / total_poids, 1) if total_poids > 0 else 0

    # Appréciation qualitative
    if score_global >= 8.5:
        appreciation = "🟢 Excellent emplacement"
        couleur = "#00c853"
    elif score_global >= 7.0:
        appreciation = "🟢 Bon emplacement"
        couleur = "#64dd17"
    elif score_global >= 5.5:
        appreciation = "🟡 Emplacement correct"
        couleur = "#ffd600"
    elif score_global >= 4.0:
        appreciation = "🟠 Emplacement à risque modéré"
        couleur = "#ff9100"
    else:
        appreciation = "🔴 Emplacement à risque élevé"
        couleur = "#ff1744"

    return {
        "score_global": score_global,
        "appreciation": appreciation,
        "couleur": couleur,
        "details": scores_details,
        "scores_radar": {
            critere_info["label"]: reponses.get(cid, None)
            for cid, critere_info in CRITERES.items()
        },
        "valeurs_radar": {
            critere_info["label"]: critere_info["options"].get(reponses.get(cid, ""), 0)
            for cid, critere_info in CRITERES.items()
        },
    }
