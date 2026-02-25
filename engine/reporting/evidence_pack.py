"""Evidence pack generator — ZIP containing all audit artifacts.

Contents:
- scorecard.json
- red_flags.json
- confidence_report.json
- Raw data JSONs
- PDF report
"""

import zipfile
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def create_evidence_pack(run_output_dir: str, zip_path: str) -> str:
    """Create a ZIP evidence pack from all audit outputs.

    Args:
        run_output_dir: Directory containing all run outputs.
        zip_path: Path to save the ZIP file.

    Returns:
        Path to the generated ZIP.
    """
    output_dir = Path(run_output_dir)
    zip_file_path = Path(zip_path)
    zip_file_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "evidence_pack.zip":
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)

    logger.info("evidence_pack_created", path=str(zip_file_path))
    return str(zip_file_path)
