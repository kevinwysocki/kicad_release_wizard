from pathlib import Path

import pcbnew
import wx

from .release_wizard_dialog import ReleaseWizardDialog

# Name KiCad gives to the PCB editor frame (PCB_EDIT_FRAME_NAME in KiCad's sources).
PCB_EDITOR_FRAME_NAME = "PcbFrame"


def pcb_editor_frame():
    """The PCB editor window, parent of the wizard.

    wx.GetTopLevelWindows()[0] is usually KiCad's project manager: a modal dialog
    parented to it brings the project manager to the front.
    """
    frame = wx.FindWindowByName(PCB_EDITOR_FRAME_NAME)
    if frame:
        return frame
    active = wx.GetActiveWindow()  # the plugin is started from the PCB editor
    if active:
        return wx.GetTopLevelParent(active)
    for window in wx.GetTopLevelWindows():
        if window.IsShown() and window.GetName() == PCB_EDITOR_FRAME_NAME:
            return window
    return None


class KicadReleaseWizardPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Kicad Release Wizard"
        self.category = "Fabrication"
        self.description = "Generate KiCad release jobset and helper scripts"
        self.show_toolbar_button = True
        self.icon_file_name = str(Path(__file__).resolve().parent / "resources" / "logo.png")

    def Run(self):
        try:
            parent = pcb_editor_frame()
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
