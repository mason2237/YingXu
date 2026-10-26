"""Guard screen selection: never attribute a different display's HDR to this one."""
import unittest
from yingxu.web_ui.display_status import display_for_screen


class DisplaySelectionTests(unittest.TestCase):
    def test_sdr_window_does_not_borrow_hdr_monitor(self):
        hdr = {'screenName':'DISPLAY1', 'hdrEnabled':True}
        sdr = {'screenName':'DISPLAY2', 'hdrEnabled':False}
        self.assertIs(display_for_screen({'displays':[hdr,sdr]},'display2'),sdr)

    def test_unknown_screen_is_not_reported_as_hdr(self):
        self.assertEqual(display_for_screen({'displays':[{'screenName':'DISPLAY1','hdrEnabled':True}]},'Unknown'),{})

    def test_mixed_cloned_targets_are_conservative(self):
        status = {'displays':[{'screenName':'DISPLAY1','hdrEnabled':True}, {'screenName':'DISPLAY1','hdrEnabled':False}]}
        self.assertFalse(display_for_screen(status,'DISPLAY1')['hdrEnabled'])

    def test_legacy_unknown_status_stays_unknown(self):
        self.assertIsNone(display_for_screen({'displays':[{'hdrEnabled':None}]},'Screen').get('hdrEnabled'))
