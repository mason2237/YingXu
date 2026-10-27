"""Compatibility construction for the GUI-independent review model."""
from pathlib import Path
from .domain.review import ReviewMatch, ReviewRow, language_of, path_key
from .domain.review import ReviewPlan as _ReviewPlan


class ReviewPlan(_ReviewPlan):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('exists', Path.exists)
        super().__init__(*args, **kwargs)
