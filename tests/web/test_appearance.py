"""Appearance contract uses a temporary INI; never touches the user's settings."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QCoreApplication, QObject, QSettings, Signal, Qt
from yingxu.web_ui.appearance import AppearanceBridge, DEFAULTS, SETTINGS_KEY, bootstrap_source


class StyleHints(QObject):
    colorSchemeChanged = Signal(object)
    def colorScheme(self): return Qt.ColorScheme.Light


class AppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = QSettings(str(Path(self.directory.name) / 'appearance.ini'), QSettings.Format.IniFormat)
        self.hints = StyleHints()
        self.bridge = AppearanceBridge(self.hints, settings=self.settings)
        self.events = []
        self.bridge.changed.connect(lambda value: self.events.append(json.loads(value)))

    def update(self, patch): return json.loads(self.bridge.update(json.dumps(patch)))

    def test_defaults_are_enhanced_and_system_following(self):
        self.assertEqual(self.bridge.preferences, DEFAULTS)
        self.assertEqual(self.bridge.state()['resolvedTheme'], 'light')
        self.assertFalse(self.events)

    def test_only_appearance_methods_are_exposed(self):
        meta = self.bridge.metaObject()
        methods = {bytes(meta.method(i).methodSignature()).decode() for i in range(meta.methodOffset(), meta.methodCount())}
        self.assertEqual(methods, {'changed(QString)', 'getState()', 'update(QString)'})

    def test_all_preferences_survive_new_controller(self):
        values = dict(theme='dark', glassEnabled=False, strength='standard', particlesEnabled=False, reducedMotion=True, mistEnabled=False)
        self.assertTrue(self.update(values)['ok'])
        restored = AppearanceBridge(self.hints, settings=self.settings)
        self.assertEqual(restored.preferences, values)
        self.assertEqual(restored.state()['resolvedTheme'], 'dark')
        self.assertEqual(len(self.events), 1)

    def test_invalid_updates_are_atomic_and_never_add_capabilities(self):
        patches = [[], {}, None, {'path': 'C:/secret'}, {'theme': 'dark', 'file.write': True},
                   {'theme': '<script>'}, {'theme': []}, {'strength': 'max'}, {'glassEnabled': 1}, {'reducedMotion': 'false'}, {'mistEnabled': 1}]
        for patch in patches:
            with self.subTest(patch=patch):
                self.assertFalse(self.update(patch)['ok'])
                self.assertEqual(self.bridge.preferences, DEFAULTS)
        self.assertFalse(self.events)
        self.assertIsNone(self.settings.value(SETTINGS_KEY))

    def test_previous_five_field_settings_gain_the_default_vapor_preference(self):
        previous = {key: value for key,value in DEFAULTS.items() if key != 'mistEnabled'}
        previous['theme'] = 'dark'
        self.settings.setValue(SETTINGS_KEY,json.dumps(previous))
        restored = AppearanceBridge(self.hints,settings=self.settings)
        self.assertTrue(restored.preferences['mistEnabled'])
        self.assertEqual(restored.state()['resolvedTheme'],'dark')

    def test_repeated_preference_update_emits_once(self):
        self.update({'theme': 'dark'})
        self.update({'theme': 'dark'})
        self.assertEqual(len(self.events), 1)

    def test_failed_save_reports_error_and_keeps_previous_state(self):
        class FailingSettings:
            def value(self, *args): return ''
            def setValue(self, *args): pass
            def sync(self): pass
            def status(self): return QSettings.Status.AccessError
        bridge = AppearanceBridge(self.hints, settings=FailingSettings())
        response = json.loads(bridge.update('{"theme":"dark"}'))
        self.assertFalse(response['ok'])
        self.assertEqual(response['error'], 'SAVE_FAILED')
        self.assertEqual(bridge.preferences, DEFAULTS)

    def test_system_changes_follow_only_when_selected(self):
        self.hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        self.assertEqual(self.bridge.state()['resolvedTheme'], 'dark')
        self.update({'theme': 'light'})
        self.hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
        self.hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        self.assertEqual(self.bridge.state()['resolvedTheme'], 'light')
        self.assertEqual(self.bridge.state()['systemTheme'], 'dark')
        self.update({'theme': 'system'})
        self.assertEqual(self.bridge.state()['resolvedTheme'], 'dark')

    def test_corrupt_or_oversized_data_never_breaks_startup(self):
        for value in ('{', '{"theme":"malicious"}', '[1]'):
            self.settings.setValue(SETTINGS_KEY, value)
            restored = AppearanceBridge(self.hints, settings=self.settings)
            self.assertEqual(restored.preferences, DEFAULTS)
        self.assertFalse(json.loads(self.bridge.update('x' * 2049))['ok'])

    def test_bootstrap_is_before_first_paint_and_main_frame_only(self):
        self.update({'theme': 'dark'})
        script = self.bridge.script()
        self.assertFalse(script.runsOnSubFrames())
        self.assertIn('DocumentCreation', str(script.injectionPoint()))
        self.assertIn('"resolvedTheme":"dark"', script.sourceCode())
        self.assertIn('observer.disconnect()', bootstrap_source(self.bridge.state()))
