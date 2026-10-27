"""Reuse reviewed DOM adapters and ranking; never trust page results as subtitles."""
from ...domain.errors import ProtocolError
from ...ports.subtitle_provider import InteractionMode, ProviderCapabilities
from . import candidates, subhd, zimuku
from .websites import website_for


class BrowserSiteProvider:
    capabilities = ProviderCapabilities(search=InteractionMode.MANUAL,
                                        download=InteractionMode.MANUAL, resumable_download=True)

    def plan(self, query, provider):
        site = website_for(provider)
        return {'home': site.home, 'hosts': sorted(site.hosts), 'provider': site.key,
                'submitScript': (subhd if site.provider == 'subhd' else zimuku).submit_search_script(query, site.hosts),
                'challengeScript': zimuku.verification_script(),
                'candidateScript': candidates.candidates_script(site, query)}

    def results(self, raw, provider, video_name, language='bilingual'):
        status, rows = candidates.parse_candidates(raw, website_for(provider))
        return status, candidates.rank_candidates(rows, video_name, language)

    def url(self, candidate, provider):
        site = website_for(provider)
        value = candidate.get('url')
        if not isinstance(value, str) or not zimuku.source_url(value, site.hosts):
            raise ProtocolError('UNTRUSTED_SOURCE', '候选网址不属于已登记的字幕来源。')
        return value

    def download(self,candidate,provider):
        site=website_for(provider)
        return subhd.download_script(self.url(candidate,provider),site.hosts) if site.provider=='subhd' else None
