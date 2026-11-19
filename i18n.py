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
    "tab_jobs": ("Jobs", "Jobs"),
    "tab_layers": ("Couches", "Layers"),
    "tab_options": ("Options", "Options"),
    "btn_save_profile": ("Sauvegarder profil", "Save profile"),
    "btn_load_profile": ("Charger profil", "Load profile"),
    "btn_generate": ("Générer", "Generate"),
    "btn_close": ("Fermer", "Close"),
    # --- Jobs tab --------------------------------------------------------
    "grp_rules": ("Règles de conception", "Design rules"),
    "grp_schematic": ("Schématique", "Schematic"),
    "grp_routing": ("Routage", "PCB layout"),
    "grp_drilling": ("Perçage", "Drilling"),
    "grp_bom": ("Nomenclature", "Bill of materials"),
    "grp_fab": ("Fichiers de fabrication", "Fabrication files"),
    "grp_meca": ("Mécanique", "Mechanical"),
    "job_pcb_layers": ("Une couche par fichier", "One file per layer"),
    "job_pcb_layers_tip": (
        "Un fichier par couche cochée dans l'onglet Couches, dans chacun des formats cochés "
        "(Gerber, PDF, SVG, DXF) : release/01_PCB/GRB, PDF, SVG, DXF.\n"
        "Décoché : aucun fichier par couche, Gerbers compris.",
        "One file per layer ticked in the Layers tab, in each ticked format "
        "(Gerber, PDF, SVG, DXF): release/01_PCB/GRB, PDF, SVG, DXF.\n"
        "Unticked: no per-layer file at all, Gerbers included.",
    ),
    "job_erc": ("Vérification électrique du schéma (ERC)", "Schematic electrical rules check (ERC)"),
    "job_erc_tip": (
        "Lance l'ERC sur le schéma et écrit le rapport <projet>-ERC.txt dans release/03_DOCS.\n"
        "Le job est en échec si des erreurs sont détectées.",
        "Runs the ERC on the schematic and writes the report <project>-ERC.txt to release/03_DOCS.\n"
        "The job fails if errors are found.",
    ),
    "job_drc": ("Vérification des règles de conception du PCB (DRC)", "PCB design rules check (DRC)"),
    "job_drc_tip": (
        "Lance le DRC sur le PCB (y compris la cohérence schéma/PCB) et écrit le rapport "
        "<projet>-DRC.txt dans release/03_DOCS.\n"
        "Les zones ne sont pas recalculées. Le job est en échec si des erreurs sont détectées.",
        "Runs the DRC on the board (including schematic/PCB parity) and writes the report "
        "<project>-DRC.txt to release/03_DOCS.\n"
        "Zones are not refilled. The job fails if errors are found.",
    ),
    "job_pcb_implantation": ("Fichier d'implantation (PDF)", "Assembly drawing (PDF)"),
    "job_pcb_implantation_tip": (
        "Deux PDF dans release/02_PCBA :\n"
        " - <projet>-IMPLANT_TOP.pdf : F.Fab + contour (Edge.Cuts), avec cadre et cartouche\n"
        " - <projet>-IMPLANT_BOT.pdf : B.Fab, vue en miroir\n"
        "Rendu couleur ou noir et blanc selon l'onglet Options.",
        "Two PDFs in release/02_PCBA:\n"
        " - <project>-IMPLANT_TOP.pdf: F.Fab + outline (Edge.Cuts), with frame and title block\n"
        " - <project>-IMPLANT_BOT.pdf: B.Fab, mirrored view\n"
        "Colour or black & white depending on the Options tab.",
    ),
    "job_sch_pdf": ("Schéma en PDF", "Schematic (PDF)"),
    "job_sch_pdf_tip": (
        "Toutes les feuilles du schéma dans <projet>-SCH.pdf (release/03_DOCS).\n"
        "Rendu couleur ou noir et blanc selon l'onglet Options.",
        "All schematic sheets in <project>-SCH.pdf (release/03_DOCS).\n"
        "Colour or black & white depending on the Options tab.",
    ),
    "job_pcb_pdf": ("Fichier PDF avec toutes les couches", "Single PDF with all layers"),
    "job_pcb_pdf_tip": (
        "<projet>-PCB.pdf dans release/03_DOCS, avec cartouche.\n"
        "Une page par couche cochée dans l'onglet Couches, plus une page Edge.Cuts.",
        "<project>-PCB.pdf in release/03_DOCS, with title block.\n"
        "One page per layer ticked in the Layers tab, plus an Edge.Cuts page.",
    ),
    "job_drill_map_pdf": ("Plan de perçage (PDF)", "Drill map (PDF)"),
    "job_drill_map_pdf_tip": (
        "<projet>-DRILL_MAP.pdf dans release/01_PCB/PDF : contour de carte, un symbole par "
        "diamètre de perçage (rond, croix, triangle…) et tableau de perçage en haut à gauche "
        "(diamètre, nombre, PTH/NPTH, trous oblongs).\n"
        "Établi à partir des fichiers Excellon de KiCad. Nécessite Python 3 + PyMuPDF.",
        "<project>-DRILL_MAP.pdf in release/01_PCB/PDF: board outline, one symbol per drill "
        "size (circle, cross, triangle…) and a drill table at the top left (diameter, count, "
        "PTH/NPTH, slots).\n"
        "Built from KiCad's Excellon files. Requires Python 3 + PyMuPDF.",
    ),
    "opt_drill_map_outline": ("Afficher le contour de carte", "Show the board outline"),
    "opt_drill_map_outline_tip": (
        "Dessine le contour de carte (Edge.Cuts) sous les symboles de perçage.\n"
        "Décoché : seuls les symboles et le tableau sont dessinés, à la même position sur "
        "une page au format de la feuille KiCad.",
        "Draws the board outline (Edge.Cuts) under the drill symbols.\n"
        "Unticked: only the symbols and the table are drawn, at the same position on a page "
        "of the KiCad sheet size.",
    ),
    "opt_drill_map_sheet": ("Ajouter le fond de plan", "Add the drawing sheet"),
    "opt_drill_map_sheet_tip": (
        "Ajoute le fond de plan (cadre et cartouche de la feuille KiCad), comme dans les PDF "
        "des couches. Le tableau de perçage est alors décalé à l'intérieur du cadre.",
        "Adds the drawing sheet (KiCad page frame and title block), as in the layer PDFs. "
        "The drill table then moves inside the frame.",
    ),
    "job_bom_csv": ("Nomenclature (BOM, CSV)", "Bill of materials (BOM, CSV)"),
    "job_bom_csv_tip": (
        "<projet>-BOM.csv dans release/02_PCBA, séparateur « ; », composants DNP exclus.\n"
        "Colonnes, ordre, libellés et regroupement se règlent dans l'onglet BOM.",
        "<project>-BOM.csv in release/02_PCBA, ';' separator, DNP parts excluded.\n"
        "Columns, order, labels and grouping are set in the BOM tab.",
    ),
    "job_pnp_csv": ("Fichier de pick and place (CSV)", "Pick and place file (CSV)"),
    "job_pnp_csv_tip": (
        "<projet>-POS.csv dans release/02_PCBA : les deux faces dans un seul fichier, en mm, "
        "relatif à l'origine perçage/placement. Composants DNP exclus.",
        "<project>-POS.csv in release/02_PCBA: both sides in one file, in mm, relative to the "
        "drill/place origin. DNP parts excluded.",
    ),
    "job_pcb_drill": ("Fichiers de perçage Excellon (PTH / NPTH)", "Excellon drill files (PTH / NPTH)"),
    "job_pcb_drill_tip": (
        "Deux fichiers Excellon dans release/01_PCB/GRB, en mm : <projet>-PTH.drl (trous "
        "métallisés, vias compris) et <projet>-NPTH.drl (trous non métallisés).",
        "Two Excellon files in release/01_PCB/GRB, in mm: <project>-PTH.drl (plated holes, "
        "vias included) and <project>-NPTH.drl (non-plated holes).",
    ),
    "job_zip_gerber": ("Archive .zip (Gerbers + perçage)", ".zip archive (Gerbers + drill)"),
    "job_zip_gerber_tip": (
        "Regroupe les Gerbers et le fichier de perçage dans <projet>-GERBER.zip "
        "(release/01_PCB/GRB).\n"
        "Nécessite le job « Une couche par fichier » et le format Gerber (onglet Couches).",
        "Packs the Gerbers and the drill file into <project>-GERBER.zip (release/01_PCB/GRB).\n"
        "Requires the \"One file per layer\" job and the Gerber format (Layers tab).",
    ),
    "job_meca_step": ("Modèle 3D (.step)", "3D model (.step)"),
    "job_meca_step_tip": (
        "<projet>-3D.step dans release/04_MECA : carte + composants (DNP inclus), "
        "origine au centre de la carte.",
        "<project>-3D.step in release/04_MECA: board + components (DNP included), "
        "origin at the board centre.",
    ),
    # --- Layers tab ------------------------------------------------------
    "layer_formats": ("Formats :", "Formats:"),
    "fmt_gerber": ("Gerber", "Gerber"),
    "fmt_gerber_tip": (
        "Gerber X2, coordonnées 4.6 en mm, attributs de netlist, fichier job Gerber.\n"
        "Edge.Cuts toujours inclus ; extensions Protel (.gtl, .gbl, .gts, .g1…, contour en .gko).\n"
        "Les options par couche (fond de plan, contour, miroir…) ne s'appliquent pas.",
        "Gerber X2, 4.6 coordinates in mm, netlist attributes, Gerber job file.\n"
        "Edge.Cuts always included; Protel extensions (.gtl, .gbl, .gts, .g1…, outline as .gko).\n"
        "Per-layer options (drawing sheet, outline, mirror…) do not apply.",
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
        "Drawing sheet, outline and mirror apply; no inversion or rotation.",
    ),
    "fmt_dxf": ("DXF", "DXF"),
    "fmt_dxf_tip": (
        "Un DXF par couche, en mm, éléments graphiques tracés en contours.\n"
        "Fond de plan et contour s'appliquent ; kicad-cli ne gère ni miroir, ni inversion, "
        "ni rotation en DXF.",
        "One DXF per layer, in mm, graphic items plotted as contours.\n"
        "Drawing sheet and outline apply; kicad-cli supports no mirror, inversion or "
        "rotation for DXF.",
    ),
    "col_export": ("Exporter", "Export"),
    "col_layer": ("Couche", "Layer"),
    "col_background": ("Fond de\nplan", "Drawing\nsheet"),
    "col_edge": ("Contour", "Outline"),
    "col_mirror": ("Miroir", "Mirror"),
    "col_invert": ("Inverser\n(PDF)", "Invert\n(PDF)"),
    "col_rotate": ("Rotation\n180° (PDF)", "Rotate\n180° (PDF)"),
    "col_export_tip": (
        "Exporter cette couche dans tous les formats cochés.",
        "Export this layer in every ticked format.",
    ),
    "col_layer_tip": ("Nom de la couche (nom utilisateur entre parenthèses).", "Layer name (user name in brackets)."),
    "col_background_tip": (
        "Ajoute le fond de plan (cadre et cartouche de la feuille KiCad) au fichier de la couche.\n"
        "PDF, SVG et DXF.",
        "Adds the drawing sheet (KiCad page frame and title block) to the layer file.\n"
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
        "S'applique aux PDF et SVG générés par KiCad : schéma, PDF avec toutes les couches, "
        "fichiers par couche et fichier d'implantation.\n"
        "Le plan de perçage et les couches inversées restent en noir et blanc.",
        "Applies to the PDFs and SVGs generated by KiCad: schematic, single PDF with all "
        "layers, per-layer files and assembly drawing.\n"
        "The drill map and inverted layers stay black & white.",
    ),
    "opt_pdf_black": ("Noir des PDF noir et blanc", "Black of black & white PDFs"),
    "opt_pdf_black_rgb": ("RVB (comme KiCad)", "RGB (as KiCad)"),
    "opt_pdf_black_cmyk": ("CMJN : N 100 %, CMJ 0 %", "CMYK: K 100 %, CMY 0 %"),
    "opt_pdf_black_tip": (
        "Espace colorimétrique du noir des PDF en noir et blanc : tous les PDF en mode "
        "« Noir et blanc », les couches inversées et le plan de perçage.\n"
        "CMJN : le noir est écrit directement en C 0, M 0, J 0, N 100 % (le blanc en "
        "aucune encre), sans profil couleur ; un logiciel comme Illustrator lit donc du noir "
        "pur au lieu d'un noir quadri. Nécessite PyMuPDF.",
        "Colour space of the black of black & white PDFs: every PDF in \"Black & white\" "
        "mode, inverted layers and the drill map.\n"
        "CMYK: black is written directly as C 0, M 0, Y 0, K 100 % (white as no ink), "
        "without colour profile; editors such as Illustrator then read pure black instead "
        "of a four-colour black. Requires PyMuPDF.",
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
        "Aucune couche cochée dans l'onglet Couches, alors que le job « Une couche par fichier » "
        "ou « Fichier PDF avec toutes les couches » est sélectionné.",
        "No layer ticked in the Layers tab while the \"One file per layer\" or "
        "\"Single PDF with all layers\" job is selected.",
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
        "Le plan de perçage, l'inversion, la rotation et le noir CMJN des PDF nécessitent "
        "PyMuPDF, absent de :\n"
        "{python}\n\nL'installer avec :\n{python} -m pip install PyMuPDF",
        "The drill map, PDF inversion, rotation and CMYK black require PyMuPDF, missing "
        "from:\n"
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
