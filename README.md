# pdf-to-markdown

Outil de conversion fidèle de fichiers PDF en Markdown (.md) et en texte brut (.txt).

## Objectif

Placer un PDF dans le dossier `inputs/`, lancer la conversion, et récupérer dans `outputs/` :

- un fichier `.md` qui conserve la structure du document (titres, listes, tableaux, paragraphes) ;
- un fichier `.txt` contenant le texte brut.

## Architecture

```
pdf-to-markdown/
├── inputs/              # PDF à convertir (non versionnés)
├── outputs/             # Fichiers .md et .txt générés (non versionnés)
├── src/
│   ├── convert.py       # Script de conversion PDF -> Markdown / texte brut
│   └── validation.py    # Contrôles de qualité des sorties
├── tests/
│   ├── test_convert.py      # Tests unitaires
│   └── validate_output.py   # Validation des sorties d'un dossier
├── requirements.txt     # Dépendances Python
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

Les dépendances sont : `pymupdf`, `pymupdf4llm`, `pdfplumber` et `tqdm`.

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

Ajouter les tableaux sans bordures détectés par pdfplumber (par exemple les comparatifs « Incorrect / Correct ») en fin de Markdown, dans une section dédiée :

```bash
python src/convert.py --tableaux-pdfplumber
```

Convertir puis contrôler automatiquement les sorties :

```bash
python src/convert.py --validate
```

Autres options : `--input-dir` (dossier source), `--output-dir` (dossier de sortie) et `-v` / `--verbose` (logs de débogage).

Le script affiche un journal dans la console et retourne le code 1 si au moins un fichier n'a pas pu être converti (y compris en cas d'échec de validation).

## Traitements appliqués

- **En-têtes et pieds de page répétitifs** : les lignes situées dans la bande haute ou basse de la page et répétées sur au moins 40 % des pages (au minimum 3) sont retirées du Markdown et du texte. Les chiffres sont ignorés pour la comparaison, donc « Page 3 / 41 » et « Page 12 / 41 » sont reconnus comme le même motif. Les lignes de tableau ne sont jamais retirées.
- **Coupures de mots** : un trait d'union en fin de ligne entre deux lettres minuscules est recollé (« grammai-⏎re » devient « grammaire »).
- **Ligatures et espaces** : les ligatures (ﬁ, ﬂ...) sont décomposées et les espaces insécables sont remplacées par des espaces simples.

Limite connue : la coupure de mot entre deux pages n'est pas recollée, et un mot composé coupé en fin de ligne (« peut-⏎être ») est aussi recollé à tort ; à relire sur les documents concernés.

## Validation

Le script `tests/validate_output.py` contrôle les paires `.md` / `.txt` d'un dossier (`outputs/` par défaut) :

- sorties non vides et au moins 50 mots ;
- aucune ligue non normalisée ni espace insécable restante ;
- aucune ligne hors tableau répétée plus de 20 fois (en-tête ou pied de page non filtré) ;
- avertissements pour les coupures de mot restantes et l'absence de titre ou de tableau Markdown.

```bash
python tests/validate_output.py
python tests/validate_output.py chemin/vers/dossier
```

Tests unitaires :

```bash
python -m unittest discover tests
```

## Statut

Projet en cours de mise en place.
