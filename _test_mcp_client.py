"""Quick test script to verify MCP server tools are visible and callable."""

import asyncio
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import django
django.setup()

from mcp.client.sse import sse_client
from mcp import ClientSession


def get_test_run_id():
    """Get a run_id from a completed audit (sync, before async context)."""
    from core.models import Audit
    audit = Audit.objects.filter(status="success").first()
    return str(audit.run_id) if audit else None


async def main():
    # Get test data before entering async context
    test_run_id = get_test_run_id()

    print("Connecting to MCP server at http://localhost:8001/sse ...")

    async with sse_client("http://localhost:8001/sse") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"\n✅ Connected! Found {len(tools.tools)} tools:\n")
            for tool in tools.tools:
                print(f"  📦 {tool.name}")
                print(f"     {tool.description[:100]}...")
                print(f"     Params: {[p for p in tool.inputSchema.get('properties', {}).keys()]}")
                print()

            # Test get_scorecard with a known audit
            if test_run_id:
                print(f"Testing get_scorecard with audit {test_run_id[:8]}...")
                result = await session.call_tool(
                    "get_scorecard",
                    {"run_id": test_run_id},
                )
                data = json.loads(result.content[0].text)
                print(f"\n✅ get_scorecard result:")
                print(f"   Account: {data.get('account_name')}")
                print(f"   Score: {data.get('composite_score')}")
                print(f"   Risk: {data.get('risk_band')}")
                print(f"   Capital: {data.get('capital_implication')}")
                print(f"   Red flags: {data.get('red_flag_count')}")
                print(f"   Confidence: {data.get('confidence')}")
                print(f"   Domains: {list(data.get('domain_scores', {}).keys())}")
            else:
                print("   No completed audits found to test with.")

            print("\n✅ MCP server is fully operational!")


if __name__ == "__main__":
    asyncio.run(main())
