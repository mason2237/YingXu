"""No network or media write authority."""
from pathlib import Path
from typing import Protocol


class MediaIdentityReader(Protocol):
    def read(self,path:Path,*,include_hash:bool,should_stop=None)->dict: ...
