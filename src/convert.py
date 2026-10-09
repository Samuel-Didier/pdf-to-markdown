#!/usr/bin/env python3
"""Convertit des fichiers PDF en Markdown (.md) et en texte brut (.txt).

Utilisation :
    python src/convert.py                    # convertit tous les PDF de inputs/
    python src/convert.py chemin/doc.pdf     # convertit un seul fichier
    python src/convert.py --images           # extrait aussi les images et les lie dans le Markdown

Sorties (dans outputs/) :
    <nom>.md                  Markdown fidèle (titres, listes, tableaux)
    <nom>.txt                 texte brut
    images/<nom>/            images extraites (avec --images uniquement)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pymupdf
import pymupdf4llm
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT_DIR / "inputs"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "outputs"

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


def extraire_markdown(doc: pymupdf.Document, nom: str, dossier_images: Path | None) -> str:
    """Convertit le document en Markdown avec pymupdf4llm.

    Si dossier_images est fourni, les images sont écrites dans ce dossier et les
    liens Markdown sont rendus relatifs au dossier outputs/ (images/<nom>/...).
    """
    if dossier_images is None:
        return pymupdf4llm.to_markdown(doc)

    dossier_images.mkdir(parents=True, exist_ok=True)
    markdown = pymupdf4llm.to_markdown(
        doc,
        write_images=True,
        image_path=str(dossier_images),
        image_format="png",
        dpi=150,
    )
    # Liens relatifs : le .md est dans outputs/, les images dans outputs/images/<nom>/
    chemin_absolu = dossier_images.as_posix()
    return markdown.replace(chemin_absolu, f"images/{nom}")


def extraire_texte_brut(doc: pymupdf.Document) -> str:
    """Extrait le texte brut de chaque page via page.get_text()."""
    pages = []
    for page in tqdm(doc, desc="Pages (texte)", unit="page", leave=False):
        pages.append(page.get_text())
    return "\n\n".join(pages)


def convertir_pdf(pdf: Path, dossier_sortie: Path, avec_images: bool) -> None:
    """Convertit un PDF et écrit les fichiers .md et .txt correspondants."""
    nom = pdf.stem
    chemin_md = dossier_sortie / f"{nom}.md"
    chemin_txt = dossier_sortie / f"{nom}.txt"
    dossier_images = dossier_sortie / "images" / nom if avec_images else None

    with pymupdf.open(pdf) as doc:
        if doc.needs_pass:
            raise ValueError("PDF protégé par mot de passe, conversion impossible")
        logger.debug("%d page(s) détectée(s) dans %s", doc.page_count, pdf.name)

        markdown = extraire_markdown(doc, nom, dossier_images)
        texte = extraire_texte_brut(doc)

    chemin_md.write_text(markdown, encoding="utf-8")
    chemin_txt.write_text(texte, encoding="utf-8")
    logger.info("OK  %s -> %s, %s", pdf.name, chemin_md.name, chemin_txt.name)
    if dossier_images is not None:
        nb_images = sum(1 for _ in dossier_images.glob("*.png"))
        logger.info("    %d image(s) extraite(s) dans %s", nb_images, dossier_images)


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convertit des PDF en Markdown et texte brut.")
    parser.add_argument("pdf", nargs="?", type=Path, help="Fichier PDF à convertir (sinon tout le dossier inputs/)")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Dossier des PDF (défaut : inputs/)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Dossier de sortie (défaut : outputs/)")
    parser.add_argument("--images", action="store_true", help="Extrait les images et les lie dans le Markdown")
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
            convertir_pdf(pdf, dossier_sortie, args.images)
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
