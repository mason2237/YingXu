"""Compatibility alias; implementation lives in the replaceable adapter layer."""
import sys
from ..adapters import subtitle_imports as _implementation
sys.modules[__name__] = _implementation
