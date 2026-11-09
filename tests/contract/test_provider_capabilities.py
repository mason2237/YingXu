import unittest
from yingxu.adapters.subtitle_sites.browser_provider import BrowserSiteProvider
from yingxu.ports.subtitle_provider import InteractionMode


class ProviderCapabilityTests(unittest.TestCase):
    def test_browser_never_gets_api_or_file_authority(self):
        capabilities=BrowserSiteProvider.capabilities
        self.assertFalse(capabilities.local_files);self.assertFalse(capabilities.api_credentials)
        self.assertEqual(capabilities.search,InteractionMode.MANUAL)
        with self.assertRaises(Exception):BrowserSiteProvider().url({'url':'https://localhost/private'},'zimuku')
