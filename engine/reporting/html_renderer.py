"""Jinja2 HTML renderer — Injects scorecard data into HTML templates."""

from pathlib import Path

import jinja2
import structlog

logger = structlog.get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_report_html(scorecard: dict, template_name: str = "report_base.html") -> str:
    """Render the audit report as HTML from scorecard data.

    Args:
        scorecard: The scorecard dictionary with all audit data.
        template_name: Name of the Jinja2 template to use.

    Returns:
        Rendered HTML string.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )

    template = env.get_template(template_name)
    has_ga4 = _has_ga4_data(scorecard)
    html = template.render(
        scorecard=scorecard,
        has_pmax=_has_pmax_data(scorecard),
        has_ga4=has_ga4,
        ga4_data=scorecard.get("_ga4_raw_data", {}),
    )

    logger.info("html_rendered", template=template_name, has_ga4=has_ga4)
    return html


def save_html(html: str, output_path: str) -> str:
    """Save rendered HTML to file.

    Args:
        html: Rendered HTML string.
        output_path: Path to save the HTML file.

    Returns:
        Path to the saved file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(path)


def _has_pmax_data(scorecard: dict) -> bool:
    """Check if scorecard contains PMax-specific data."""
    # TODO: Check for PMax data in domain scores or tables
    return True


def _has_ga4_data(scorecard: dict) -> bool:
    """Check if scorecard contains GA4 data for report sections."""
    ga4 = scorecard.get("_ga4_raw_data", {})
    return bool(ga4 and any(ga4.get(k) for k in ["channel_revenue", "paid_vs_organic", "attribution"]))
