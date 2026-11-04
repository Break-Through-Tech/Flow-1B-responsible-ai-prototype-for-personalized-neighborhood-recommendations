"""Shared tool backend. Ranking stays in the existing recommendation engine."""

from pathlib import Path

from .contracts import Request
from .engine import SCORERS, Recommender


class RecommendationTools:
    """Lazy, server-scoped snapshot; ethics remains usable when data is unavailable."""

    def __init__(self, data_dir: str | Path, scorer: str = "mean"):
        if scorer not in SCORERS:
            raise ValueError(f"scorer must be one of {', '.join(SCORERS)}.")
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.scorer = scorer
        self._engine: Recommender | None = None

    def recommend(self, arguments: dict) -> dict:
        # Validate before opening files. Do not silently discard unsupported fields.
        Request.parse(arguments)
        if self._engine is None:
            self._engine = Recommender(self.data_dir, scorer=self.scorer)
        return self._engine.recommend(arguments)
