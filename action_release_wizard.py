from pathlib import Path

import pcbnew
import wx

from .release_wizard_dialog import ReleaseWizardDialog


class KicadReleaseWizardPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Kicad Release Wizard"
        self.category = "Fabrication"
        self.description = "Generate KiCad release jobset and helper scripts"
        self.show_toolbar_button = True
        self.icon_file_name = str(Path(__file__).resolve().parent / "resources" / "logo.png")

    def Run(self):
        try:
            parent = wx.GetTopLevelWindows()[0]
        except Exception:
            parent = None

        # KiCad's wxLog warnings emitted while the wizard runs (e.g. "Font 'X' not
        # found; substituting ..." when the board is loaded) would pop up as message
        # boxes. They are unrelated to the wizard: silence them while it is open.
        # Wizard errors are reported with wx.MessageBox, which is not affected.
        no_log = wx.LogNull()
        try:
            dlg = ReleaseWizardDialog(parent)
            dlg.ShowModal()
            dlg.Destroy()
        finally:
            del no_log
