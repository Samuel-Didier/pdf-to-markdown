"""Contrôles de qualité des sorties .md et .txt.

Utilisé par `convert.py --validate` et par `tests/validate_output.py`.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

# Nombre minimal de mots attendu dans une sortie non vide.
MOTS_MINIMUM = 50
# Une ligne (hors tableaux) répétée plus de fois que cela signale un en-tête ou pied de page non filtré.
REPETITIONS_MAXIMUM = 20

LIGATURES = re.compile(r"[\ufb00-\ufb06]")
ESPACES_INSECABLES = re.compile(r"[\u00a0\u202f\u2007]")
MOT_COUPE = re.compile(r"[a-zà-ÿœæ]-\n[a-zà-ÿœæ]")
TITRE = re.compile(r"^#{1,6} \S", re.MULTILINE)
TABLEAU = re.compile(r"^\|.*\|\s*$", re.MULTILINE)


def _cle_repetition(ligne: str) -> str:
    """Forme canonique d'une ligne : les chiffres sont remplacés par '#'."""
    return re.sub(r"\d+", "#", ligne.strip().lower())


def verifier_repetitions(texte: str, nom: str) -> list[str]:
    """Signale les lignes répétées trop souvent (hors lignes de tableau)."""
    compteur = Counter(
        _cle_repetition(ligne)
        for ligne in texte.splitlines()
        if len(ligne.strip()) >= 5 and not ligne.strip().startswith("|")
    )
    erreurs = []
    for cle, nb in compteur.most_common(5):
        if nb > REPETITIONS_MAXIMUM:
            erreurs.append(
                f"{nom} : la ligne « {cle[:80]} » apparaît {nb} fois "
                "(en-tête ou pied de page probablement non filtré)"
            )
    return erreurs


def valider_paire(md: Path, txt: Path) -> tuple[list[str], list[str]]:
    """Valide une paire de sorties. Retourne (erreurs, avertissements).

    Une erreur rend la conversion en échec ; un avertissement est seulement affiché.
    """
    erreurs: list[str] = []
    avertissements: list[str] = []

    for chemin in (md, txt):
        if not chemin.is_file():
            erreurs.append(f"fichier absent : {chemin.name}")
    if erreurs:
        return erreurs, avertissements

    texte_md = md.read_text(encoding="utf-8")
    texte_txt = txt.read_text(encoding="utf-8")

    for nom, texte in ((md.name, texte_md), (txt.name, texte_txt)):
        if not texte.strip():
            erreurs.append(f"{nom} est vide")
            continue
        nb_mots = len(texte.split())
        if nb_mots < MOTS_MINIMUM:
            erreurs.append(f"{nom} : {nb_mots} mot(s), minimum attendu {MOTS_MINIMUM}")
        if LIGATURES.search(texte):
            erreurs.append(f"{nom} : ligatures non normalisées")
        if ESPACES_INSECABLES.search(texte):
            erreurs.append(f"{nom} : espaces insécables non nettoyées")
        nb_coupes = len(MOT_COUPE.findall(texte))
        if nb_coupes:
            avertissements.append(f"{nom} : {nb_coupes} coupure(s) de mot en fin de ligne restante(s)")

    erreurs.extend(verifier_repetitions(texte_md, md.name))
    if not TITRE.search(texte_md) and not TABLEAU.search(texte_md):
        avertissements.append(f"{md.name} : aucune structure Markdown (titre ou tableau) détectée")
    return erreurs, avertissements


def valider_dossier(dossier: Path) -> dict[str, tuple[list[str], list[str]]]:
    """Valide chaque .md d'un dossier avec son .txt homonyme."""
    return {
        md.name: valider_paire(md, md.with_suffix(".txt"))
        for md in sorted(dossier.glob("*.md"))
    }
