# pdf-to-markdown

Outil de conversion fidèle de fichiers PDF en Markdown (.md) et en texte brut (.txt).

## Objectif

Placer un PDF dans le dossier `inputs/`, lancer la conversion, et récupérer dans `outputs/` :

- un fichier `.md` qui conserve la structure du document (titres, listes, tableaux, paragraphes) ;
- un fichier `.txt` contenant le texte brut.

## Architecture

```
pdf-to-markdown/
├── inputs/          # PDF à convertir (non versionnés)
├── outputs/         # Fichiers .md et .txt générés (non versionnés)
├── src/
│   └── convert.py   # Script de conversion PDF -> Markdown / texte brut
├── requirements.txt # Dépendances Python
├── README.md
└── .gitignore
```

## Workflow

1. Déposer le ou les fichiers PDF dans `inputs/`.
2. Lancer le script de conversion.
3. Récupérer les résultats dans `outputs/` (un `.md` et un `.txt` par PDF).

## Installation

Prérequis : Python 3.9 ou supérieur.

```bash
pip install -r requirements.txt
```

Les dépendances sont : `pymupdf`, `pymupdf4llm` et `tqdm`.

## Utilisation

Convertir tous les PDF présents dans `inputs/` :

```bash
python src/convert.py
```

Convertir un seul fichier :

```bash
python src/convert.py chemin/vers/document.pdf
```

Extraire aussi les images (elles sont enregistrées dans `outputs/images/<nom_pdf>/` et liées dans le Markdown) :

```bash
python src/convert.py --images
```

Autres options : `--input-dir` (dossier source), `--output-dir` (dossier de sortie) et `-v` / `--verbose` (logs de débogage).

Le script affiche un journal dans la console et retourne le code 1 si au moins un fichier n'a pas pu être converti.

## Statut

Projet en cours de mise en place.
