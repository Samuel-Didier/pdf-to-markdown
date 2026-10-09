"""Tests unitaires : python -m unittest discover tests (ou pytest tests)"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

import convert  # noqa: E402
from validation import valider_paire  # noqa: E402


class TestNormalisation(unittest.TestCase):
    def test_coupure_de_mot_en_fin_de_ligne(self):
        self.assertEqual(convert.corriger_texte("la grammai-\nre française"), "la grammaire française")

    def test_mot_compose_connu_garde_son_trait_d_union(self):
        self.assertEqual(convert.corriger_texte("il est peut-\nêtre venu"), "il est peut-être venu")

    def test_mot_compose_present_ailleurs_garde_son_trait_d_union(self):
        texte = "un porte-\nmonnaie noir, puis le porte-monnaie rouge"
        self.assertEqual(convert.corriger_texte(texte), "un porte-monnaie noir, puis le porte-monnaie rouge")

    def test_suffixe_pronominal_garde_son_trait_d_union(self):
        self.assertEqual(convert.corriger_texte("celui-\nci est là"), "celui-ci est là")

    def test_ligatures_et_espaces_insecables(self):
        self.assertEqual(convert.corriger_texte("\ufb01chier\u00a0:"), "fichier :")

    def test_motif_avec_numero_de_page(self):
        self.assertEqual(convert.normaliser_motif("Page 3 / 41"), convert.normaliser_motif("Page 12 / 41"))

    def test_retrait_motifs_preserve_les_tableaux(self):
        motifs = {convert.normaliser_motif("Minigrammaire")}
        texte = "Minigrammaire\nContenu utile\n| Minigrammaire | x |"
        self.assertEqual(convert.retirer_motifs(texte, motifs), "Contenu utile\n| Minigrammaire | x |")


class TestCesuresInterPages(unittest.TestCase):
    def test_cesure_entre_deux_pages_est_recollee(self):
        pages = ["Il étudie la gram-", "maire française."]
        self.assertEqual(convert.assembler(pages), "Il étudie la grammaire française.")

    def test_pages_sans_cesure_restent_separees(self):
        pages = ["Première page.", "Deuxième page."]
        self.assertEqual(convert.assembler(pages), "Première page.\n\nDeuxième page.")


class TestFallbackPdfplumber(unittest.TestCase):
    def test_tableau_ajoute_seulement_si_absent_de_la_page(self):
        pages = ["Texte seul.", "| a | b |\n|---|---|\n| 1 | 2 |"]
        tableaux = {1: "| x | y |\n|---|---|\n| 3 | 4 |", 2: "| x | y |"}
        resultat = convert.ajouter_tableaux_manquants(pages, tableaux)
        self.assertIn("| x | y |", resultat[0])
        self.assertEqual(resultat[1], pages[1])


class TestValidation(unittest.TestCase):
    def test_sorties_vides_sont_en_erreur(self):
        with tempfile.TemporaryDirectory() as dossier:
            md = Path(dossier) / "a.md"
            txt = Path(dossier) / "a.txt"
            md.write_text("", encoding="utf-8")
            txt.write_text("", encoding="utf-8")
            erreurs, _ = valider_paire(md, txt)
            self.assertTrue(erreurs)


if __name__ == "__main__":
    unittest.main()
