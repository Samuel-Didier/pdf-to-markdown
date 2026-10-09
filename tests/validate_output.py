#!/usr/bin/env python3
"""Valide les sorties .md et .txt d'un dossier (défaut : outputs/).

Utilisation :
    python tests/validate_output.py [dossier]

Retourne 0 si aucune erreur n'est détectée, 1 sinon.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
from validation import valider_dossier  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dossier = Path(argv[0]).expanduser().resolve() if argv else ROOT_DIR / "outputs"
    if not dossier.is_dir():
        print(f"Dossier introuvable : {dossier}", file=sys.stderr)
        return 1

    resultats = valider_dossier(dossier)
    if not resultats:
        print(f"Aucun fichier .md trouvé dans {dossier}")
        return 1

    echec = False
    for nom, (erreurs, avertissements) in resultats.items():
        print(f"[{'ECHEC' if erreurs else 'OK'}] {nom}")
        for erreur in erreurs:
            print(f"    erreur : {erreur}")
        for avertissement in avertissements:
            print(f"    avertissement : {avertissement}")
        echec = echec or bool(erreurs)
    return 1 if echec else 0


if __name__ == "__main__":
    sys.exit(main())
