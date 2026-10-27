"""Compatibility alias; implementation lives in the replaceable adapter layer."""
import sys
from ..adapters import subtitle_downloads as _implementation
sys.modules[__name__] = _implementation
