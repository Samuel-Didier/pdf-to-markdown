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
├── src/             # Code de conversion
├── README.md
└── .gitignore
```

## Workflow

1. Déposer le ou les fichiers PDF dans `inputs/`.
2. Lancer le script de conversion.
3. Récupérer les résultats dans `outputs/` (un `.md` et un `.txt` par PDF).

## Installation

À compléter selon la stack retenue (Python, Node.js ou PHP).

## Statut

Projet en cours de mise en place.
