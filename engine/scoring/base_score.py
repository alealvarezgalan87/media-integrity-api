"""Abstract base for domain scores."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ScoreResult:
    """Result of a domain score computation."""

    domain: str
    value: int  # 0-100
    weight: float
    weighted_contribution: float
    key_findings: list[str]
    data_completeness: float  # 0.0-1.0
    sub_scores: dict[str, float]


class BaseDomainScore(ABC):
    """Abstract base class for all domain scores."""

    domain_name: str = ""
    weight: float = 0.0

    @abstractmethod
    def compute(self, data: dict) -> ScoreResult:
        """Compute the domain score from normalized data.

        Args:
            data: Dictionary of input metrics for this domain.

        Returns:
            ScoreResult with value (0-100), findings, and metadata.
        """
        ...

    @staticmethod
    def clamp(value: float, min_val: float = 0, max_val: float = 100) -> int:
        """Clamp a score to 0-100 range and round."""
        return round(min(max(value, min_val), max_val))
