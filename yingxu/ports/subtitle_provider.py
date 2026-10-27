"""Provider results are untrusted hints, never verified subtitle contents.

No implementation imports a browser here. Browser-assisted providers report
manual_required; unsupported capabilities must not pretend to have succeeded.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class InteractionMode(str, Enum):
    AUTOMATIC = 'automatic'
    MANUAL = 'manual'
    UNSUPPORTED = 'unsupported'


class ProviderStatus(str, Enum):
    READY = 'ready'
    EMPTY = 'empty'
    MANUAL_REQUIRED = 'manual_required'
    UNSUPPORTED = 'unsupported'
    FAILED = 'failed'


@dataclass(frozen=True)
class ProviderCapabilities:
    search: InteractionMode
    download: InteractionMode
    resumable_download: bool = False  # Still requires per-response Range validation.


@dataclass(frozen=True)
class SearchRequest:
    title: str
    language: str = 'bilingual'


@dataclass(frozen=True)
class SubtitleCandidate:
    candidate_id: str
    provider_id: str
    title: str
    language: str = ''
    release: str = ''

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class SearchResult:
    status: ProviderStatus
    candidates: tuple[SubtitleCandidate, ...] = ()
    message: str = ''


@dataclass(frozen=True)
class DownloadSourceResult:
    status: ProviderStatus
    source_ref: str | None = None  # Adapter-owned reference; no auth secrets in UI state.
    message: str = ''


class SubtitleProvider(Protocol):
    provider_id: str
    capabilities: ProviderCapabilities

    def search(self, request: SearchRequest) -> SearchResult: ...
    def resolve_download(self, candidate_id: str) -> DownloadSourceResult: ...
