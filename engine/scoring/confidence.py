"""Confidence Modifier — Based on data completeness across canonical tables."""


def compute_confidence(extraction_stats: list[dict]) -> str:
    """Compute confidence level based on data completeness.

    Args:
        extraction_stats: List of dicts with 'status' key ('complete', 'partial', 'skipped').

    Returns:
        "High", "Medium", or "Low".
    """
    total_tables = 7  # All canonical tables
    complete = sum(1 for t in extraction_stats if t.get("status") == "complete")
    partial = sum(1 for t in extraction_stats if t.get("status") == "partial")

    completeness = (complete + partial * 0.5) / total_tables

    if completeness >= 0.85:
        return "High"
    elif completeness >= 0.60:
        return "Medium"
    else:
        return "Low"
