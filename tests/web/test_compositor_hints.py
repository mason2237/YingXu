"""The optional redraw channel must never acquire filesystem capabilities."""
import unittest
from PySide6.QtCore import QObject
from yingxu.web_ui.native_window import CompositorHints


class CompositorSurfaceTests(unittest.TestCase):
    def test_only_boolean_redraw_slot_and_readonly_state_are_exposed(self):
        parent = QObject()
        hints = CompositorHints(parent)
        meta = hints.metaObject()
        methods = {bytes(meta.method(i).methodSignature()).decode() for i in range(meta.methodOffset(),meta.methodCount())}
        self.assertEqual(methods, {'changed(bool)','setOverlayActive(bool)'})
        state = meta.property(meta.indexOfProperty('overlayActive'))
        self.assertTrue(state.isReadable())
        self.assertFalse(state.isWritable())
