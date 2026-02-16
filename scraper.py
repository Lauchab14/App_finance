"""
Module de web scraping pour extraire les données d'annonces immobilières.
Supporte : Centris, DuProprio, LesPACs.
Méthode : requests + BeautifulSoup (scraping basique).
Si le scraping échoue, l'utilisateur pourra saisir les données manuellement.
"""

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ═══════════════════════════════════════════════════════════════════════════
# DÉTECTION DE PLATEFORME
# ═══════════════════════════════════════════════════════════════════════════

def detecter_plateforme(url: str) -> str | None:
    """Détecte la plateforme immobilière à partir de l'URL."""
    domaine = urlparse(url).netloc.lower()
    if "centris" in domaine:
        return "centris"
    elif "duproprio" in domaine:
        return "duproprio"
    elif "lespacs" in domaine:
        return "lespacs"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# EXTRACTION GÉNÉRIQUE
# ═══════════════════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}


def _nettoyer_prix(texte: str) -> float | None:
    """Extrait un prix numérique d'un texte."""
    if not texte:
        return None
    # Supprimer tout sauf chiffres, virgules et points
    chiffres = re.sub(r"[^\d,.]", "", texte)
    chiffres = chiffres.replace(",", "").replace(" ", "")
    try:
        return float(chiffres)
    except (ValueError, TypeError):
        return None


def _telecharger_page(url: str) -> BeautifulSoup | None:
    """Télécharge et parse une page HTML."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER CENTRIS
# ═══════════════════════════════════════════════════════════════════════════

def scraper_centris(url: str) -> dict:
    """Tente d'extraire les données d'une annonce Centris."""
    resultat = {
        "plateforme": "Centris",
        "url": url,
        "prix": None,
        "type_immeuble": None,
        "nb_logements": None,
        "adresse": None,
        "ville": None,
        "revenus_bruts": None,
        "depenses": None,
        "erreur": None,
    }

    soup = _telecharger_page(url)
    if soup is None:
        resultat["erreur"] = (
            "Impossible de charger la page Centris. "
            "Le site utilise du JavaScript dynamique. "
            "Veuillez saisir les données manuellement."
        )
        return resultat

    # Tentative d'extraction du prix
    prix_el = soup.find("span", class_=re.compile(r"price|prix", re.I))
    if prix_el:
        resultat["prix"] = _nettoyer_prix(prix_el.get_text())

    # Tentative d'extraction de l'adresse
    adresse_el = soup.find("h2", class_=re.compile(r"address|adresse", re.I))
    if adresse_el:
        resultat["adresse"] = adresse_el.get_text(strip=True)

    # Si on n'a pas trouvé le prix, chercher dans les meta tags
    if resultat["prix"] is None:
        meta_price = soup.find("meta", {"property": "og:price:amount"})
        if meta_price:
            resultat["prix"] = _nettoyer_prix(meta_price.get("content", ""))

    # Tentative titre
    title = soup.find("title")
    if title:
        titre_texte = title.get_text()
        # Essayer d'extraire le type d'immeuble du titre
        for mot in ["Duplex", "Triplex", "Quadruplex", "Quintuplex", "Immeuble", "Plex"]:
            if mot.lower() in titre_texte.lower():
                resultat["type_immeuble"] = mot
                break

    if resultat["prix"] is None and resultat["adresse"] is None:
        resultat["erreur"] = (
            "Le scraping de Centris a partiellement échoué (contenu dynamique). "
            "Veuillez compléter les données manuellement."
        )

    return resultat


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER DUPROPRIO
# ═══════════════════════════════════════════════════════════════════════════

def scraper_duproprio(url: str) -> dict:
    """Tente d'extraire les données d'une annonce DuProprio."""
    resultat = {
        "plateforme": "DuProprio",
        "url": url,
        "prix": None,
        "type_immeuble": None,
        "nb_logements": None,
        "adresse": None,
        "ville": None,
        "revenus_bruts": None,
        "depenses": None,
        "erreur": None,
    }

    soup = _telecharger_page(url)
    if soup is None:
        resultat["erreur"] = (
            "Impossible de charger la page DuProprio. "
            "Veuillez saisir les données manuellement."
        )
        return resultat

    # Prix
    prix_el = soup.find("div", class_=re.compile(r"price|listing-price", re.I))
    if not prix_el:
        prix_el = soup.find("span", class_=re.compile(r"price", re.I))
    if prix_el:
        resultat["prix"] = _nettoyer_prix(prix_el.get_text())

    # Adresse
    adresse_el = soup.find("h1", class_=re.compile(r"address|listing-location", re.I))
    if adresse_el:
        resultat["adresse"] = adresse_el.get_text(strip=True)

    # Meta tags comme fallback
    if resultat["prix"] is None:
        meta_price = soup.find("meta", {"property": "og:price:amount"})
        if meta_price:
            resultat["prix"] = _nettoyer_prix(meta_price.get("content", ""))

    if resultat["adresse"] is None:
        meta_title = soup.find("meta", {"property": "og:title"})
        if meta_title:
            resultat["adresse"] = meta_title.get("content", "")

    # Type d'immeuble
    title = soup.find("title")
    if title:
        titre_texte = title.get_text()
        for mot in ["Duplex", "Triplex", "Quadruplex", "Quintuplex", "Immeuble", "Plex"]:
            if mot.lower() in titre_texte.lower():
                resultat["type_immeuble"] = mot
                break

    if resultat["prix"] is None and resultat["adresse"] is None:
        resultat["erreur"] = (
            "Le scraping de DuProprio a partiellement échoué. "
            "Veuillez compléter les données manuellement."
        )

    return resultat


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER LESPACS
# ═══════════════════════════════════════════════════════════════════════════

def scraper_lespacs(url: str) -> dict:
    """Tente d'extraire les données d'une annonce LesPACs."""
    return {
        "plateforme": "LesPACs",
        "url": url,
        "prix": None,
        "type_immeuble": None,
        "nb_logements": None,
        "adresse": None,
        "ville": None,
        "revenus_bruts": None,
        "depenses": None,
        "erreur": (
            "LesPACs n'est plus actif pour l'immobilier résidentiel. "
            "Veuillez saisir les données manuellement."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════

def extraire_donnees(url: str) -> dict:
    """Fonction principale : détecte la plateforme et extrait les données."""
    plateforme = detecter_plateforme(url)

    if plateforme == "centris":
        return scraper_centris(url)
    elif plateforme == "duproprio":
        return scraper_duproprio(url)
    elif plateforme == "lespacs":
        return scraper_lespacs(url)
    else:
        return {
            "plateforme": "Inconnue",
            "url": url,
            "prix": None,
            "type_immeuble": None,
            "nb_logements": None,
            "adresse": None,
            "ville": None,
            "revenus_bruts": None,
            "depenses": None,
            "erreur": (
                f"Plateforme non reconnue. "
                f"Plateformes supportées : Centris, DuProprio, LesPACs. "
                f"Veuillez saisir les données manuellement."
            ),
        }
