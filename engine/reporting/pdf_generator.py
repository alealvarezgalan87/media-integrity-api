"""HTML to PDF conversion using WeasyPrint."""

from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def html_to_pdf(html_path: str, pdf_path: str) -> str:
    """Convert an HTML file to PDF using WeasyPrint.

    Args:
        html_path: Path to the HTML file.
        pdf_path: Path to save the PDF output.

    Returns:
        Path to the generated PDF.
    """
    from weasyprint import HTML

    path = Path(pdf_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    html_path = str(Path(html_path).resolve())
    HTML(filename=html_path).write_pdf(pdf_path)

    logger.info("pdf_generated", path=pdf_path)
    return pdf_path
