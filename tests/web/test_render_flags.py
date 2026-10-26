"""The visibility workaround must preserve unrelated Chromium configuration."""
import unittest
from yingxu.web_ui.native_window import compositor_chromium_flags


class RenderFlagsTests(unittest.TestCase):
    def test_empty_flags_add_only_native_occlusion_workaround(self):
        self.assertEqual(compositor_chromium_flags(''),'--disable-features=CalculateNativeWinOcclusion')

    def test_existing_feature_switch_and_other_arguments_are_preserved(self):
        for raw in ('--disable-features=FeatureA --example="a b"',
                    '"--disable-features=FeatureA" --example="a b"',
                    '--disable-features="FeatureA" --example="a b"'):
            self.assertEqual(compositor_chromium_flags(raw),raw.replace('FeatureA','FeatureA,CalculateNativeWinOcclusion'))

    def test_repeated_configuration_is_idempotent(self):
        value = '--disable-features=FeatureA,CalculateNativeWinOcclusion --example=value'
        self.assertEqual(compositor_chromium_flags(value),value)

    def test_unrecognised_user_quoting_is_not_overwritten(self):
        value = '--disable-features="FeatureA, FeatureB" --example=value'
        self.assertEqual(compositor_chromium_flags(value),value)
