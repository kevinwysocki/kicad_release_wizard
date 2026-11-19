"""Minimal FR/EN translation layer.

French is used when the active locale is French, English otherwise.
Set KICAD_RELEASE_WIZARD_LANG=fr|en to force a language.
"""

import locale
import os

# key: (fr, en)
STRINGS = {
    # --- Dialog / header -------------------------------------------------
    "title": ("Kicad Release Wizard", "Kicad Release Wizard"),
    "header": (
        "Projet : {project}\nDossier : {folder}\nProfil : {profile}",
        "Project: {project}\nFolder: {folder}\nProfile: {profile}",
    ),
    "tab_jobs": ("Jobs", "Jobs"),
    "tab_layers": ("Couches", "Layers"),
    "tab_options": ("Options", "Options"),
    "btn_save_profile": ("Sauvegarder profil", "Save profile"),
    "btn_load_profile": ("Charger profil", "Load profile"),
    "btn_generate": ("Générer", "Generate"),
    "btn_close": ("Fermer", "Close"),
    # --- Jobs tab --------------------------------------------------------
    "jobs_info": (
        "Cocher les éléments à produire. Survoler une case pour plus de détails. "
        "Tout est écrit dans le dossier release/ du projet.",
        "Tick the items to produce. Hover a checkbox for details. "
        "Everything is written to the project's release/ folder.",
    ),
    "job_erc": ("Vérification électrique du schéma (ERC)", "Schematic electrical rules check (ERC)"),
    "job_erc_tip": (
        "Lance l'ERC sur le schéma et écrit le rapport <projet>_ERC.txt dans release/03_DOCS.\n"
        "Le job est en échec si des erreurs sont détectées.",
        "Runs the ERC on the schematic and writes the report <project>_ERC.txt to release/03_DOCS.\n"
        "The job fails if errors are found.",
    ),
    "job_drc": ("Vérification des règles de conception du PCB (DRC)", "PCB design rules check (DRC)"),
    "job_drc_tip": (
        "Lance le DRC sur le PCB (y compris la cohérence schéma/PCB) et écrit le rapport "
        "<projet>_DRC.txt dans release/03_DOCS.\n"
        "Les zones ne sont pas recalculées. Le job est en échec si des erreurs sont détectées.",
        "Runs the DRC on the board (including schematic/PCB parity) and writes the report "
        "<project>_DRC.txt to release/03_DOCS.\n"
        "Zones are not refilled. The job fails if errors are found.",
    ),
    "job_pcb_implantation": ("Plans d'assemblage (implantation) en PDF", "Assembly drawings (PDF)"),
    "job_pcb_implantation_tip": (
        "Deux PDF dans release/02_PCBA :\n"
        " - <projet>_IMPLANT_TOP.pdf : F.Fab + fond de plan (Dwgs.User) + contour (Edge.Cuts)\n"
        " - <projet>_IMPLANT_BOT.pdf : B.Fab, vue en miroir\n"
        "Rendu couleur ou noir et blanc selon l'onglet Options.",
        "Two PDFs in release/02_PCBA:\n"
        " - <project>_IMPLANT_TOP.pdf: F.Fab + drawing layer (Dwgs.User) + outline (Edge.Cuts)\n"
        " - <project>_IMPLANT_BOT.pdf: B.Fab, mirrored view\n"
        "Colour or black & white depending on the Options tab.",
    ),
    "job_sch_pdf": ("Schéma complet en PDF", "Full schematic (PDF)"),
    "job_sch_pdf_tip": (
        "Toutes les feuilles du schéma dans <projet>_SCH.pdf (release/03_DOCS).\n"
        "Rendu couleur ou noir et blanc selon l'onglet Options.",
        "All schematic sheets in <project>_SCH.pdf (release/03_DOCS).\n"
        "Colour or black & white depending on the Options tab.",
    ),
    "job_pcb_pdf": ("PCB en un seul PDF (une page par couche)", "PCB as a single PDF (one page per layer)"),
    "job_pcb_pdf_tip": (
        "<projet>_PCB.pdf dans release/03_DOCS, avec cartouche.\n"
        "Une page par couche cochée dans l'onglet Couches, plus une page Edge.Cuts.",
        "<project>_PCB.pdf in release/03_DOCS, with title block.\n"
        "One page per layer ticked in the Layers tab, plus an Edge.Cuts page.",
    ),
    "job_drill_map_pdf": ("Plan de perçage en PDF", "Drill map (PDF)"),
    "job_drill_map_pdf_tip": (
        "<projet>_DRILL_MAP.pdf dans release/01_PCB/PDF : un repère vectoriel par trou, "
        "aux coordonnées absolues, plus les mires caméra (cercles F.Cu de Ø4 mm).\n"
        "Nécessite Python 3 + PyMuPDF.",
        "<project>_DRILL_MAP.pdf in release/01_PCB/PDF: one vector mark per hole at absolute "
        "coordinates, plus camera fiducials (Ø4 mm F.Cu circles).\n"
        "Requires Python 3 + PyMuPDF.",
    ),
    "job_bom_csv": ("Nomenclature (BOM) en CSV", "Bill of materials (BOM) as CSV"),
    "job_bom_csv_tip": (
        "<projet>_BOM.csv dans release/02_PCBA, séparateur « ; », composants DNP exclus.\n"
        "Colonnes, ordre, libellés et regroupement se règlent dans l'onglet BOM.",
        "<project>_BOM.csv in release/02_PCBA, ';' separator, DNP parts excluded.\n"
        "Columns, order, labels and grouping are set in the BOM tab.",
    ),
    "job_pnp_csv": ("Fichier de placement (pick & place) en CSV", "Pick & place file (CSV)"),
    "job_pnp_csv_tip": (
        "<projet>_POS.csv dans release/02_PCBA : les deux faces dans un seul fichier, en mm, "
        "relatif à l'origine perçage/placement. Composants DNP exclus.",
        "<project>_POS.csv in release/02_PCBA: both sides in one file, in mm, relative to the "
        "drill/place origin. DNP parts excluded.",
    ),
    "job_pcb_drill": ("Fichier de perçage (Excellon)", "Drill file (Excellon)"),
    "job_pcb_drill_tip": (
        "Fichier Excellon dans release/01_PCB/GRB, trous métallisés et non métallisés combinés, en mm.",
        "Excellon file in release/01_PCB/GRB, plated and non-plated holes combined, in mm.",
    ),
    "job_zip_gerber": ("Archive ZIP pour le fabricant (Gerbers + perçage)", "ZIP archive for the fab house (Gerbers + drill)"),
    "job_zip_gerber_tip": (
        "Regroupe les Gerbers et le fichier de perçage dans <projet>_GERBER.zip "
        "(release/01_PCB/GRB).\n"
        "Nécessite le format Gerber coché dans l'onglet Couches.",
        "Packs the Gerbers and the drill file into <project>_GERBER.zip (release/01_PCB/GRB).\n"
        "Requires the Gerber format ticked in the Layers tab.",
    ),
    "job_meca_step": ("Modèle 3D STEP", "3D model (STEP)"),
    "job_meca_step_tip": (
        "<projet>_STEP.step dans release/04_MECA : carte + composants (DNP inclus), "
        "origine au centre de la carte.",
        "<project>_STEP.step in release/04_MECA: board + components (DNP included), "
        "origin at the board centre.",
    ),
    # --- Layers tab ------------------------------------------------------
    "layers_info": (
        "Chaque couche cochée dans « Exporter » est générée dans chacun des formats cochés "
        "ci-dessous, un fichier par couche (dossiers release/01_PCB/GRB, PDF, SVG, DXF). "
        "Elle apparaît aussi dans le job « PCB en un seul PDF ».\n"
        "Survoler un format ou un en-tête de colonne pour plus de détails ; cliquer sur "
        "l'en-tête d'une colonne à cases pour tout cocher ou tout décocher.",
        "Each layer ticked in \"Export\" is generated in each format ticked below, one file "
        "per layer (folders release/01_PCB/GRB, PDF, SVG, DXF). It is also part of the "
        "\"PCB as a single PDF\" job.\n"
        "Hover a format or a column header for details; click a checkbox column header "
        "to tick or untick the whole column.",
    ),
    "layer_formats": ("Formats :", "Formats:"),
    "fmt_gerber": ("Gerber", "Gerber"),
    "fmt_gerber_tip": (
        "Gerber X2, coordonnées 4.6 en mm, attributs de netlist, fichier job Gerber.\n"
        "Edge.Cuts toujours inclus ; extensions normalisées (.GTL, .GBL, .GTS, .G1…).\n"
        "Les options par couche (fond de plan, contour, miroir…) ne s'appliquent pas.",
        "Gerber X2, 4.6 coordinates in mm, netlist attributes, Gerber job file.\n"
        "Edge.Cuts always included; normalised extensions (.GTL, .GBL, .GTS, .G1…).\n"
        "Per-layer options (drawing layer, outline, mirror…) do not apply.",
    ),
    "fmt_pdf": ("PDF", "PDF"),
    "fmt_pdf_tip": (
        "Un PDF par couche, sans cartouche. Toutes les options par couche s'appliquent.",
        "One PDF per layer, without title block. All per-layer options apply.",
    ),
    "fmt_svg": ("SVG", "SVG"),
    "fmt_svg_tip": (
        "Un SVG par couche, format de page, sans cartouche.\n"
        "Fond de plan, contour et miroir s'appliquent ; pas d'inversion ni de rotation.",
        "One SVG per layer, page size, without title block.\n"
        "Drawing layer, outline and mirror apply; no inversion or rotation.",
    ),
    "fmt_dxf": ("DXF", "DXF"),
    "fmt_dxf_tip": (
        "Un DXF par couche, en mm, éléments graphiques tracés en contours.\n"
        "Fond de plan et contour s'appliquent ; kicad-cli ne gère ni miroir, ni inversion, "
        "ni rotation en DXF.",
        "One DXF per layer, in mm, graphic items plotted as contours.\n"
        "Drawing layer and outline apply; kicad-cli supports no mirror, inversion or "
        "rotation for DXF.",
    ),
    "col_export": ("Exporter", "Export"),
    "col_layer": ("Couche", "Layer"),
    "col_background": ("Fond de plan", "Drawing layer"),
    "col_edge": ("Contour", "Outline"),
    "col_mirror": ("Miroir", "Mirror"),
    "col_invert": ("Inverser\n(PDF)", "Invert\n(PDF)"),
    "col_rotate": ("Rotation 180°\n(PDF)", "Rotate 180°\n(PDF)"),
    "col_export_tip": (
        "Exporter cette couche dans tous les formats cochés.",
        "Export this layer in every ticked format.",
    ),
    "col_layer_tip": ("Nom de la couche (nom utilisateur entre parenthèses).", "Layer name (user name in brackets)."),
    "col_background_tip": (
        "Ajoute la couche Dwgs.User (cadre, cotes, notes) au fichier de la couche.\n"
        "PDF, SVG et DXF.",
        "Adds the Dwgs.User layer (frame, dimensions, notes) to the layer file.\n"
        "PDF, SVG and DXF.",
    ),
    "col_edge_tip": (
        "Ajoute le contour de carte (Edge.Cuts) au fichier de la couche.\nPDF, SVG et DXF.",
        "Adds the board outline (Edge.Cuts) to the layer file.\nPDF, SVG and DXF.",
    ),
    "col_mirror_tip": (
        "Génère la couche en miroir (coché par défaut pour les couches B.*).\nPDF et SVG.",
        "Plots the layer mirrored (ticked by default for B.* layers).\nPDF and SVG.",
    ),
    "col_invert_tip": (
        "PDF uniquement : inverse noir/blanc à l'intérieur du contour de carte "
        "(film négatif, ex. vernis).\n"
        "Le PDF de cette couche est alors toujours en noir et blanc.",
        "PDF only: swaps black/white inside the board outline (negative film, e.g. solder mask).\n"
        "This layer's PDF is then always black & white.",
    ),
    "col_rotate_tip": (
        "PDF uniquement : tourne la page de 180° après génération.",
        "PDF only: rotates the page by 180° after generation.",
    ),
    # --- BOM tab ---------------------------------------------------------
    "tab_bom": ("BOM", "BOM"),
    "bom_info": (
        "Champs disponibles dans les symboles du projet. Chaque ligne cochée devient une colonne "
        "du CSV, dans l'ordre du tableau (de haut en bas = de gauche à droite).\n"
        "Le libellé est l'en-tête de colonne ; « Grouper » regroupe sur une ligne les "
        "composants dont tous les champs groupés sont identiques.",
        "Fields available in the project's symbols. Each ticked row becomes a CSV column, in "
        "table order (top to bottom = left to right).\n"
        "The label is the column header; \"Group\" merges into one line the parts whose "
        "grouped fields are all identical.",
    ),
    "bom_col_include": ("Inclure", "Include"),
    "bom_col_field": ("Champ", "Field"),
    "bom_col_label": ("Libellé de colonne", "Column label"),
    "bom_col_group": ("Grouper", "Group"),
    "bom_col_include_tip": ("Ajouter ce champ comme colonne du CSV.", "Add this field as a CSV column."),
    "bom_col_field_tip": (
        "Nom du champ. ${…} = champ calculé par KiCad (n° de ligne, quantité, DNP…).",
        "Field name. ${…} = field computed by KiCad (line number, quantity, DNP…).",
    ),
    "bom_col_label_tip": ("En-tête de la colonne dans le CSV (modifiable).", "Column header in the CSV (editable)."),
    "bom_col_group_tip": (
        "Regrouper les composants qui ont la même valeur pour ce champ "
        "(et pour tous les autres champs groupés).",
        "Group parts that share the same value for this field (and for all other grouped fields).",
    ),
    "bom_btn_up": ("Monter", "Move up"),
    "bom_btn_up_tip": ("Déplacer le champ sélectionné vers la gauche du CSV.", "Move the selected field to the left in the CSV."),
    "bom_btn_down": ("Descendre", "Move down"),
    "bom_btn_down_tip": ("Déplacer le champ sélectionné vers la droite du CSV.", "Move the selected field to the right in the CSV."),
    "bom_btn_reset": ("Réinitialiser", "Reset"),
    "bom_btn_reset_tip": (
        "Relire les champs du schéma et revenir à la sélection par défaut.",
        "Re-read the schematic fields and restore the default selection.",
    ),
    # --- Options tab -----------------------------------------------------
    "opt_color_mode": ("Rendu des PDF / SVG", "PDF / SVG rendering"),
    "opt_color": ("Couleur (couleurs des couches par défaut)", "Colour (default layer colours)"),
    "opt_bw": ("Noir et blanc", "Black & white"),
    "opt_color_mode_tip": (
        "S'applique aux PDF et SVG générés par KiCad : schéma, PCB en un seul PDF, fichiers "
        "par couche et plans d'assemblage.\n"
        "Le plan de perçage et les couches inversées restent en noir et blanc.",
        "Applies to the PDFs and SVGs generated by KiCad: schematic, PCB as a single PDF, "
        "per-layer files and assembly drawings.\n"
        "The drill map and inverted layers stay black & white.",
    ),
    # --- Messages --------------------------------------------------------
    "dlg_save_profile": ("Sauvegarder un profil", "Save a profile"),
    "dlg_load_profile": ("Charger un profil", "Load a profile"),
    "wildcard_json": (
        "Profils JSON (*.json)|*.json|Tous les fichiers (*.*)|*.*",
        "JSON profiles (*.json)|*.json|All files (*.*)|*.*",
    ),
    "msg_profile_saved": ("Profil sauvegardé :\n{path}", "Profile saved:\n{path}"),
    "msg_profile_loaded": ("Profil chargé :\n{path}", "Profile loaded:\n{path}"),
    "msg_profile_read_error": ("Impossible de lire le profil :\n{path}\n\n{error}", "Unable to read profile:\n{path}\n\n{error}"),
    "msg_profile_title": ("Kicad Release Wizard - Profil", "Kicad Release Wizard - Profile"),
    "msg_error": ("Erreur", "Error"),
    "msg_no_layer": (
        "Aucune couche cochée dans l'onglet Couches, alors qu'un format de couche ou le job "
        "« PCB en un seul PDF » est sélectionné.",
        "No layer ticked in the Layers tab while a layer format or the "
        "\"PCB as a single PDF\" job is selected.",
    ),
    "msg_no_bom_field": (
        "Aucun champ coché dans l'onglet BOM alors que la nomenclature est demandée.",
        "No field ticked in the BOM tab while the BOM is requested.",
    ),
    "msg_outline_error": (
        "Impossible de lire le contour de la carte (Edge.Cuts), nécessaire à l'inversion :\n{error}",
        "Unable to read the board outline (Edge.Cuts), required for the inversion:\n{error}",
    ),
    "msg_python_not_found": (
        "Python 3 introuvable. Installer Python 3 (python.org) puis relancer, ou indiquer "
        "l'interpréteur dans la variable d'environnement KICAD_RELEASE_WIZARD_PYTHON.",
        "Python 3 not found. Install Python 3 (python.org) and retry, or set the interpreter "
        "in the KICAD_RELEASE_WIZARD_PYTHON environment variable.",
    ),
    "msg_pymupdf_missing": (
        "Le plan de perçage, l'inversion et la rotation des PDF nécessitent PyMuPDF, absent de :\n"
        "{python}\n\nL'installer avec :\n{python} -m pip install PyMuPDF",
        "The drill map, PDF inversion and rotation require PyMuPDF, missing from:\n"
        "{python}\n\nInstall it with:\n{python} -m pip install PyMuPDF",
    ),
    "run_title": ("Kicad Release Wizard - Génération", "Kicad Release Wizard - Generation"),
    "run_running": (
        "Génération en cours… (le DRC peut prendre plusieurs minutes sur une grosse carte)",
        "Generating… (the DRC may take several minutes on a large board)",
    ),
    "run_ok": ("Terminé : tous les jobs ont réussi.", "Done: all jobs succeeded."),
    "run_failed": (
        "Terminé avec des erreurs (code {code}) : voir le journal ci-dessous.",
        "Finished with errors (code {code}): see the log below.",
    ),
    "run_stopped": ("Arrêté.", "Stopped."),
    "btn_stop": ("Arrêter", "Stop"),
    "btn_open_release": ("Ouvrir le dossier release", "Open release folder"),
    "msg_kicad_cli_not_found": ("kicad-cli introuvable", "kicad-cli not found"),
    # --- Console (.cmd, ASCII only) --------------------------------------
}


def _locale_names():
    """Yield candidate locale names, most relevant first."""
    try:
        import wx

        loc = wx.GetLocale()  # KiCad's UI language when available
        if loc:
            yield loc.GetCanonicalName()
        info = wx.Locale.GetLanguageInfo(wx.Locale.GetSystemLanguage())
        if info:
            yield info.CanonicalName
    except Exception:
        pass
    try:
        yield locale.getlocale()[0]
    except Exception:
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        yield os.environ.get(var)


def detect_language():
    forced = (os.environ.get("KICAD_RELEASE_WIZARD_LANG") or "").strip().lower()
    if forced in ("fr", "en"):
        return forced
    for name in _locale_names():
        if name:
            return "fr" if name.lower().startswith("fr") else "en"
    return "en"


LANG = detect_language()


def tr(key, **kwargs):
    fr, en = STRINGS[key]
    text = fr if LANG == "fr" else en
    return text.format(**kwargs) if kwargs else text
