"""Red Flag Detection Engine — Declarative rules from YAML config.

Rules are loaded from config/scoring_rules.yaml.
Each rule has: id, severity, domain, condition, title, description, recommendation.
"""

import operator
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
import structlog

logger = structlog.get_logger(__name__)

OPERATORS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

CONDITION_PATTERN = re.compile(
    r"^(\w+)\s*(>=|<=|!=|==|>|<)\s*(.+)$"
)


@dataclass
class RedFlag:
    """A detected red flag."""

    id: str
    severity: str
    domain: str
    rule_id: str
    title: str
    description: str
    evidence: dict
    recommendation: str
    triggered_by: str


def load_rules(config_path: str | None = None) -> list[dict]:
    """Load red flag rules from Django ORM (preferred) or YAML config (fallback).

    In normal operation, rules are passed as a parameter to evaluate_rules()
    by the Celery task, which loads them from the Django ORM.
    This function is only used as a fallback for standalone engine usage.
    """
    try:
        from core.models import RedFlagRule
        db_rules = list(
            RedFlagRule.objects.filter(enabled=True).values(
                "id", "severity", "domain", "condition",
                "title", "description", "recommendation",
            )
        )
        if db_rules:
            return db_rules
    except Exception:
        pass

    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "scoring_rules.yaml")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config.get("rules", [])


def _parse_value(raw: str):
    """Parse a condition value string into a Python value."""
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _evaluate_single_condition(condition: str, metrics: dict) -> tuple[bool, str | None]:
    """Safely evaluate a single atomic condition against metrics.

    Returns (triggered: bool, metric_key: str | None).
    """
    match = CONDITION_PATTERN.match(condition.strip())
    if not match:
        logger.warning("unparseable_condition", condition=condition)
        return False, None

    metric_key = match.group(1)
    op_str = match.group(2)
    threshold = _parse_value(match.group(3))

    if metric_key not in metrics:
        return False, metric_key

    actual = metrics[metric_key]
    if actual is None:
        return False, metric_key

    op_func = OPERATORS.get(op_str)
    if op_func is None:
        logger.warning("unknown_operator", operator=op_str)
        return False, metric_key

    try:
        return op_func(actual, threshold), metric_key
    except TypeError:
        return False, metric_key


def _evaluate_condition(condition: str, metrics: dict) -> tuple[bool, str | None]:
    """Evaluate a condition that may contain 'and'/'or' operators.

    Supports compound conditions like:
      "avg_quality_score > 7 and nonbrand_avg_quality_score < 5"
      "days_since_refresh > 90 or match_rate < 0.30"

    Returns (triggered: bool, first_metric_key: str | None).
    """
    condition = condition.strip()

    # Split on ' or ' first (lower precedence)
    if " or " in condition:
        parts = [p.strip() for p in condition.split(" or ")]
        first_key = None
        for part in parts:
            triggered, key = _evaluate_condition(part, metrics)
            if first_key is None and key:
                first_key = key
            if triggered:
                return True, key or first_key
        return False, first_key

    # Split on ' and ' (higher precedence)
    if " and " in condition:
        parts = [p.strip() for p in condition.split(" and ")]
        first_key = None
        for part in parts:
            triggered, key = _evaluate_condition(part, metrics)
            if first_key is None and key:
                first_key = key
            if not triggered:
                return False, first_key
        return True, first_key

    # Atomic condition
    return _evaluate_single_condition(condition, metrics)


def evaluate_rules(metrics: dict, rules: list[dict] | None = None) -> list[RedFlag]:
    """Evaluate all red flag rules against the provided metrics.

    Args:
        metrics: Dictionary of computed metrics to evaluate.
        rules: Optional list of rule definitions. Loads from config if not provided.

    Returns:
        List of triggered RedFlag instances.
    """
    if rules is None:
        rules = load_rules()

    triggered = []

    for rule in rules:
        condition = rule.get("condition", "")
        is_triggered, metric_key = _evaluate_condition(condition, metrics)

        if is_triggered:
            # Collect evidence from all metrics referenced in the condition
            evidence = {"condition": condition}
            for m_key in re.findall(r'\b(\w+)\s*(?:>|<|>=|<=|==|!=)', condition):
                if m_key in metrics:
                    evidence[m_key] = metrics[m_key]
            if not any(k != "condition" for k in evidence):
                evidence["metric"] = metric_key
                evidence["actual_value"] = metrics.get(metric_key)
            flag = RedFlag(
                id=rule["id"],
                severity=rule.get("severity", "medium"),
                domain=rule.get("domain", "unknown"),
                rule_id=rule["id"],
                title=rule.get("title", ""),
                description=rule.get("description", ""),
                evidence=evidence,
                recommendation=rule.get("recommendation", ""),
                triggered_by=condition,
            )
            triggered.append(flag)
            logger.info("red_flag_triggered", rule_id=rule["id"], severity=flag.severity)
        else:
            logger.debug("rule_not_triggered", rule_id=rule["id"])

    return triggered
