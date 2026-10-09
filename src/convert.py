#!/usr/bin/env python3
"""Convertit des fichiers PDF en Markdown (.md) et en texte brut (.txt).

Utilisation :
    python src/convert.py                        # convertit tous les PDF de inputs/
    python src/convert.py chemin/doc.pdf         # convertit un seul fichier
    python src/convert.py --images               # extrait aussi les images et les lie dans le Markdown
    python src/convert.py --tableaux-pdfplumber  # complète les pages sans tableau Markdown avec les tableaux pdfplumber
    python src/convert.py --validate             # contrôle les sorties après conversion

Sorties (dans outputs/) :
    <nom>.md                 Markdown fidèle (titres, listes, tableaux)
    <nom>.txt                texte brut
    images/<nom>/           images extraites (avec --images uniquement)
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf
import pymupdf4llm
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation import valider_paire  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT_DIR / "inputs"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "outputs"

# Bande haute / basse de la page (en proportion de la hauteur) où cherchent en-têtes et pieds de page.
ZONE_MARGE = 0.08
# Une ligne de marge est considérée répétitive si elle apparaît sur au moins ce nombre de pages
# (et au moins cette proportion du document).
REPETITION_MIN_PAGES = 3
REPETITION_RATIO = 0.4

LETTRES = "A-Za-zÀ-ÖØ-öø-ÿŒœÆæ"
TABLEAU = re.compile(r"^\|.*\|\s*$", re.MULTILINE)

# Suffixes pronominaux et démonstratifs : « celui-ci », « lui-même », « est-ce »...
# Un trait d'union devant ces mots fait partie du mot composé et n'est jamais une césure.
SUFFIXES_COMPOSES = frozenset(
    {"ci", "là", "même", "mêmes", "ce", "ils", "elle", "elles", "moi", "toi", "lui", "eux", "nous", "vous", "je", "tu"}
)
# Mots composés courants (forme avec trait d'union). Utilisé quand le mot n'apparaît pas ailleurs
# dans le document sous forme non coupée.
MOTS_COMPOSES_CONNUS = frozenset(
    {
        "peut-être",
        "est-ce",
        "au-dessus",
        "au-dessous",
        "au-delà",
        "par-dessus",
        "par-delà",
        "en-dessous",
        "là-bas",
        "sous-sol",
        "sous-marin",
        "non-sens",
        "quelque-chose",
        "bien-être",
        "grand-mère",
        "grand-père",
    }
)

logger = logging.getLogger("convert")


def configurer_logs(verbeux: bool = False) -> None:
    """Configure l'affichage des logs dans la console."""
    niveau = logging.DEBUG if verbeux else logging.INFO
    logging.basicConfig(level=niveau, format="%(levelname)-8s | %(message)s")


def trouver_pdfs(dossier: Path) -> list[Path]:
    """Retourne la liste triée des fichiers PDF présents dans un dossier (non récursif)."""
    if not dossier.is_dir():
        raise FileNotFoundError(f"Dossier d'entrée introuvable : {dossier}")
    return sorted(p for p in dossier.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def valider_pdf(chemin: Path) -> Path:
    """Vérifie qu'un chemin désigne bien un fichier PDF existant."""
    chemin = chemin.expanduser().resolve()
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    if chemin.suffix.lower() != ".pdf":
        raise ValueError(f"Le fichier n'est pas un PDF : {chemin}")
    return chemin


# ---------------------------------------------------------------------------
# Normalisation du texte
# ---------------------------------------------------------------------------

def normaliser_unicode(texte: str) -> str:
    """Ligatures (NFKC : ﬁ -> fi), espaces insécables -> espace simple, espaces de fin de ligne retirées."""
    texte = unicodedata.normalize("NFKC", texte)
    for espace in ("\u00a0", "\u202f", "\u2007"):
        texte = texte.replace(espace, " ")
    texte = texte.replace("\u00ad", "")  # trait d'union conditionnel invisible
    return re.sub(r"[ \t]+\n", "\n", texte)


def recoller_cesures(texte: str) -> str:
    """Recolle les mots coupés en fin de ligne par un trait d'union de césure.

    « grammai-⏎re » devient « grammaire ». Un trait d'union qui fait partie d'un mot composé
    n'est pas une césure et est conservé (« peut-⏎être » devient « peut-être ») lorsque :
    - la forme avec trait d'union apparaît ailleurs dans le texte sans coupure ;
    - ou le mot figure dans MOTS_COMPOSES_CONNUS ;
    - ou le second élément est un suffixe pronominal (« celui-⏎ci », « lui-⏎même »).
    """
    formes_presentes = {m.group(0).lower() for m in re.finditer(rf"[{LETTRES}]+-[{LETTRES}]+", texte)}

    def decider(m: re.Match[str]) -> str:
        gauche, droite = m.group(1), m.group(2)
        compose = f"{gauche}-{droite}".lower()
        if compose in formes_presentes or compose in MOTS_COMPOSES_CONNUS or droite.lower() in SUFFIXES_COMPOSES:
            return f"{gauche}-{droite}"
        return gauche + droite

    return re.sub(rf"([{LETTRES}]+)-\n([a-zà-ÿœæ]+)", decider, texte)


def corriger_texte(texte: str) -> str:
    """Normalisation Unicode puis recollage des césures."""
    return recoller_cesures(normaliser_unicode(texte))


def joindre_pages(pages: list[str]) -> str:
    """Assemble les pages en un seul texte.

    Si une page se termine par une césure (« gram- ») et que la suivante commence par une minuscule,
    les deux pages sont reliées par un simple saut de ligne : la césure est alors recollée par
    recoller_cesures. Sinon les pages sont séparées par une ligne vide.
    """
    morceaux = [page.strip("\n") for page in pages if page.strip()]
    if not morceaux:
        return ""
    resultat = morceaux[0]
    for suivante in morceaux[1:]:
        if re.search(rf"[{LETTRES}]-\s*$", resultat) and re.match(r"\s*[a-zà-ÿœæ]", suivante):
            resultat = resultat.rstrip() + "\n" + suivante.lstrip()
        else:
            resultat = resultat.rstrip() + "\n\n" + suivante.lstrip()
    return resultat


def assembler(pages: list[str]) -> str:
    """Joint les pages puis applique la normalisation complète au document entier."""
    return corriger_texte(joindre_pages(pages))


def normaliser_motif(ligne: str) -> str:
    """Forme canonique d'une ligne pour détecter les répétitions.

    Les chiffres sont remplacés par '#' pour que "Page 3 / 41" et "Page 12 / 41"
    correspondent au même motif.
    """
    ligne = unicodedata.normalize("NFKC", ligne)
    ligne = re.sub(r"^[#*\s]+|[*\s]+$", "", ligne)
    ligne = re.sub(r"\d+", "#", ligne)
    ligne = re.sub(r"\s+", " ", ligne)
    return ligne.lower()


# ---------------------------------------------------------------------------
# En-têtes et pieds de page répétitifs
# ---------------------------------------------------------------------------

def lignes_de_marge(page: pymupdf.Page) -> list[str]:
    """Retourne les lignes situées dans la bande haute ou basse de la page."""
    hauteur = page.rect.height
    lignes: list[str] = []
    for bloc in page.get_text("blocks"):
        y0, y1, texte = bloc[1], bloc[3], bloc[4]
        if y1 < hauteur * ZONE_MARGE or y0 > hauteur * (1 - ZONE_MARGE):
            lignes.extend(ligne for ligne in texte.splitlines() if ligne.strip())
    return lignes


def detecter_motifs_repetitifs(doc: pymupdf.Document) -> set[str]:
    """Repère les motifs présents en marge (haut/bas) sur une part significative des pages."""
    compteur: Counter[str] = Counter()
    for page in doc:
        compteur.update({normaliser_motif(ligne) for ligne in lignes_de_marge(page)})
    seuil = max(REPETITION_MIN_PAGES, int(doc.page_count * REPETITION_RATIO))
    motifs = {motif for motif, nb in compteur.items() if motif and nb >= seuil}
    logger.debug("%d motif(s) répétitif(s) en en-tête/pied de page", len(motifs))
    return motifs


def retirer_motifs(texte: str, motifs: set[str]) -> str:
    """Supprime les lignes courtes dont le motif figure dans `motifs`.

    Les lignes de tableau Markdown (commençant par '|') ne sont jamais supprimées.
    """
    if not motifs:
        return texte
    gardees = []
    for ligne in texte.splitlines():
        ligne_nue = ligne.strip()
        if (
            ligne_nue
            and len(ligne_nue) <= 120
            and not ligne_nue.startswith("|")
            and normaliser_motif(ligne_nue) in motifs
        ):
            continue
        gardees.append(ligne)
    return "\n".join(gardees)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extraire_pages_markdown(
    doc: pymupdf.Document,
    nom: str,
    dossier_images: Path | None,
    motifs: set[str],
) -> list[str]:
    """Convertit chaque page en Markdown avec pymupdf4llm, sans en-têtes/pieds répétitifs.

    Si dossier_images est fourni, les images sont écrites dans ce dossier et les
    liens Markdown sont rendus relatifs au dossier outputs/ (images/<nom>/...).
    """
    options: dict = {"page_chunks": True}
    if dossier_images is not None:
        dossier_images.mkdir(parents=True, exist_ok=True)
        options.update(write_images=True, image_path=str(dossier_images), image_format="png", dpi=150)

    pages = pymupdf4llm.to_markdown(doc, **options)
    textes = [retirer_motifs(page["text"], motifs) for page in pages]
    if dossier_images is not None:
        # Liens relatifs : le .md est dans outputs/, les images dans outputs/images/<nom>/
        textes = [texte.replace(dossier_images.as_posix(), f"images/{nom}") for texte in textes]
    return textes


def extraire_pages_texte(doc: pymupdf.Document, motifs: set[str]) -> list[str]:
    """Extrait le texte brut de chaque page, sans en-têtes/pieds répétitifs."""
    return [
        retirer_motifs(page.get_text(), motifs)
        for page in tqdm(doc, desc="Pages (texte)", unit="page", leave=False)
    ]


def normaliser_cellule(valeur: object) -> str:
    """Rend une cellule de tableau sur une seule ligne, avec les pipes échappés."""
    if valeur is None:
        return ""
    texte = corriger_texte(str(valeur)).replace("\n", " ").strip()
    return re.sub(r"\s+", " ", texte).replace("|", "\\|")


def tableau_en_markdown(lignes: list[list[str]]) -> str:
    """Construit un tableau Markdown à partir de lignes déjà normalisées (1re ligne = en-tête)."""
    largeur = max(len(ligne) for ligne in lignes)
    lignes = [ligne + [""] * (largeur - len(ligne)) for ligne in lignes]
    rendu = ["| " + " | ".join(lignes[0]) + " |", "|" + "---|" * largeur]
    rendu += ["| " + " | ".join(ligne) + " |" for ligne in lignes[1:]]
    return "\n".join(rendu)


def extraire_tableaux_pdfplumber(pdf: Path) -> dict[int, str]:
    """Tableaux sans bordures complètes (ex. comparatifs « Incorrect / Correct »), par numéro de page.

    Utilise la stratégie « text » de pdfplumber (alignement des colonnes).
    """
    import pdfplumber  # import local : dépendance utilisée seulement avec --tableaux-pdfplumber

    tableaux_par_page: dict[int, str] = {}
    with pdfplumber.open(pdf) as document:
        for numero, page in enumerate(document.pages, start=1):
            blocs: list[str] = []
            for tableau in page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"}):
                lignes = [
                    [normaliser_cellule(cellule) for cellule in ligne]
                    for ligne in tableau
                    if ligne and any(cellule for cellule in ligne)
                ]
                if len(lignes) >= 2:
                    blocs.append(tableau_en_markdown(lignes))
            if blocs:
                tableaux_par_page[numero] = "\n\n".join(blocs)
    logger.debug("tableaux pdfplumber détectés sur %d page(s) de %s", len(tableaux_par_page), pdf.name)
    return tableaux_par_page


def ajouter_tableaux_manquants(pages_md: list[str], tableaux: dict[int, str]) -> list[str]:
    """Ajoute le tableau pdfplumber d'une page uniquement si pymupdf4llm n'a produit aucun tableau sur cette page.

    Ainsi, un tableau déjà correctement rendu n'est jamais dupliqué. Le tableau ajouté est placé
    en fin de la page concernée (et non en fin de document).
    """
    resultat = list(pages_md)
    for numero, tableau in tableaux.items():
        indice = numero - 1
        if 0 <= indice < len(resultat) and not TABLEAU.search(resultat[indice]):
            resultat[indice] = resultat[indice].rstrip() + "\n\n" + tableau + "\n"
    return resultat


# ---------------------------------------------------------------------------
# Conversion d'un fichier et CLI
# ---------------------------------------------------------------------------

def convertir_pdf(
    pdf: Path,
    dossier_sortie: Path,
    avec_images: bool,
    tableaux_pdfplumber: bool = False,
) -> tuple[Path, Path]:
    """Convertit un PDF et écrit les fichiers .md et .txt correspondants.

    Retourne les chemins (md, txt) produits.
    """
    nom = pdf.stem
    chemin_md = dossier_sortie / f"{nom}.md"
    chemin_txt = dossier_sortie / f"{nom}.txt"
    dossier_images = dossier_sortie / "images" / nom if avec_images else None

    with pymupdf.open(pdf) as doc:
        if doc.needs_pass:
            raise ValueError("PDF protégé par mot de passe, conversion impossible")
        logger.debug("%d page(s) détectée(s) dans %s", doc.page_count, pdf.name)

        motifs = detecter_motifs_repetitifs(doc)
        pages_md = extraire_pages_markdown(doc, nom, dossier_images, motifs)
        pages_txt = extraire_pages_texte(doc, motifs)
        nb_pages = doc.page_count

    if tableaux_pdfplumber:
        tableaux = extraire_tableaux_pdfplumber(pdf)
        if len(pages_md) == nb_pages:
            pages_md = ajouter_tableaux_manquants(pages_md, tableaux)
        else:
            logger.warning(
                "%s : %d page(s) Markdown pour %d page(s) PDF, fallback pdfplumber ignoré",
                pdf.name,
                len(pages_md),
                nb_pages,
            )

    markdown = assembler(pages_md)
    if dossier_images is not None:
        markdown = markdown  # liens déjà relatifs (remplacement fait page par page)
    texte = assembler(pages_txt)

    chemin_md.write_text(markdown, encoding="utf-8")
    chemin_txt.write_text(texte, encoding="utf-8")
    logger.info("OK  %s -> %s, %s", pdf.name, chemin_md.name, chemin_txt.name)
    if dossier_images is not None:
        nb_images = sum(1 for _ in dossier_images.glob("*.png"))
        logger.info("    %d image(s) extraite(s) dans %s", nb_images, dossier_images)
    return chemin_md, chemin_txt


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convertit des PDF en Markdown et texte brut.")
    parser.add_argument("pdf", nargs="?", type=Path, help="Fichier PDF à convertir (sinon tout le dossier inputs/)")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Dossier des PDF (défaut : inputs/)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Dossier de sortie (défaut : outputs/)")
    parser.add_argument("--images", action="store_true", help="Extrait les images et les lie dans le Markdown")
    parser.add_argument(
        "--tableaux-pdfplumber",
        action="store_true",
        help="Complète les pages sans tableau Markdown avec les tableaux détectés par pdfplumber",
    )
    parser.add_argument("--validate", action="store_true", help="Contrôle les .md/.txt produits après conversion")
    parser.add_argument("-v", "--verbose", action="store_true", help="Affiche les logs de débogage")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée. Retourne 0 si tout s'est bien passé, 1 sinon."""
    args = analyser_arguments(argv)
    configurer_logs(args.verbose)

    try:
        if args.pdf is not None:
            pdfs = [valider_pdf(args.pdf)]
        else:
            pdfs = trouver_pdfs(args.input_dir.expanduser().resolve())
    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        return 1

    if not pdfs:
        logger.warning("Aucun fichier PDF trouvé dans %s", args.input_dir)
        return 0

    dossier_sortie = args.output_dir.expanduser().resolve()
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    logger.info("%d PDF à convertir, sorties dans %s", len(pdfs), dossier_sortie)

    succes, echecs = 0, []
    for pdf in tqdm(pdfs, desc="Conversion", unit="pdf"):
        try:
            chemin_md, chemin_txt = convertir_pdf(pdf, dossier_sortie, args.images, args.tableaux_pdfplumber)
            if args.validate:
                erreurs, avertissements = valider_paire(chemin_md, chemin_txt)
                for avertissement in avertissements:
                    logger.warning("%s : %s", pdf.name, avertissement)
                if erreurs:
                    raise ValueError("validation échouée : " + " ; ".join(erreurs))
            succes += 1
        except Exception as exc:  # on continue avec les autres fichiers
            logger.error("ECHEC %s : %s", pdf.name, exc)
            logger.debug("Détail de l'erreur", exc_info=True)
            echecs.append(pdf.name)

    logger.info("Terminé : %d réussi(s), %d échec(s)", succes, len(echecs))
    if echecs:
        logger.error("Fichiers en échec : %s", ", ".join(echecs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
