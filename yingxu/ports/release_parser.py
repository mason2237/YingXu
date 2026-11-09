"""Optional filename parser; never receives filesystem access or writes media."""
from typing import Protocol
from ..domain.releases import ParsedRelease


class ReleaseParser(Protocol):
    def parse(self, name: str) -> ParsedRelease: ...
