"""The reviewed wheel supplies the same module under its actual distribution name."""
from PyInstaller.utils.hooks import copy_metadata

datas=copy_metadata('webrtcvad-wheels')
