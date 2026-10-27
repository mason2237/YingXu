"""Reuse matching's frozen-plan checks; durable execution is a separate use case."""
from ..domain.errors import ProtocolError
from .legacy_operations import snapshot_from_review, StalePlan


class LocalPreviewer:
    def freeze(self, review):
        try:
            return snapshot_from_review(review)
        except StalePlan as error:
            raise ProtocolError('STALE_PLAN', str(error)) from error
