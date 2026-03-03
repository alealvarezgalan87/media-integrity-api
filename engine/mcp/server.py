"""MCP Server for Media Integrity Engine.

HTTP transport (SSE) so Growth Signal or any MCP client can call
our tools over the network.

Usage:
    python -m engine.mcp.server          # starts on port 8001
    python -m engine.mcp.server --port 9000
"""

import json

import structlog
from mcp.server.fastmcp import FastMCP

logger = structlog.get_logger(__name__)

# Create the MCP server
mcp = FastMCP(
    "Media Integrity Engine",
    instructions=(
        "Media Structural Integrity Engine™ — audit Google Ads accounts "
        "for structural integrity, scoring, and risk assessment."
    ),
)


@mcp.tool()
async def run_media_audit(
    account_id: str,
    date_start: str,
    date_end: str,
    organization_id: str = "",
) -> str:
    """Run a full media integrity audit for a Google Ads account.

    Extracts data from Google Ads (and GA4 if linked), normalizes metrics,
    computes 5 domain scores + composite score, detects red flags, and
    generates reports.

    Args:
        account_id: Google Ads customer ID (e.g. "123-456-7890" or "1234567890").
        date_start: Audit period start date in YYYY-MM-DD format.
        date_end: Audit period end date in YYYY-MM-DD format.
        organization_id: Optional organization UUID. Uses default org if empty.

    Returns:
        JSON with composite_score, risk_band, capital_implication,
        red_flag_count, confidence, and domain_scores breakdown.
    """
    import asyncio

    from engine.mcp.tools import run_media_audit_sync

    logger.info(
        "mcp_tool_call",
        tool="run_media_audit",
        account_id=account_id,
        date_start=date_start,
        date_end=date_end,
    )

    # Run the sync function in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: run_media_audit_sync(
            account_id=account_id,
            date_start=date_start,
            date_end=date_end,
            organization_id=organization_id or None,
        ),
    )

    logger.info(
        "mcp_tool_result",
        tool="run_media_audit",
        status=result.get("status", "unknown"),
        score=result.get("composite_score"),
    )

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_audit_status(run_id: str) -> str:
    """Check the status of a running or completed audit.

    Args:
        run_id: The UUID of the audit (returned by run_media_audit).

    Returns:
        JSON with run_id, status, and scorecard if completed.
    """
    import asyncio

    from engine.mcp.tools import get_audit_status_sync

    logger.info("mcp_tool_call", tool="get_audit_status", run_id=run_id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: get_audit_status_sync(run_id=run_id),
    )

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def get_scorecard(run_id: str) -> str:
    """Retrieve the full scorecard for a completed audit.

    Returns composite score, risk band, capital implication,
    confidence level, 5 domain scores, and red flag summary.

    Args:
        run_id: The UUID of the audit.

    Returns:
        JSON scorecard with all scoring details.
    """
    import asyncio

    from engine.mcp.tools import get_scorecard_sync

    logger.info("mcp_tool_call", tool="get_scorecard", run_id=run_id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: get_scorecard_sync(run_id=run_id),
    )

    return json.dumps(result, indent=2, default=str)
