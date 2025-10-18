#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

"""
Test client to demonstrate MCP server with CPU-specific ISA queries
"""
import asyncio
import json
import sys
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def test_cpu_config(config_name="rv64"):
    """Test MCP server with a specific CPU configuration"""

    print(f"\n{'='*60}")
    print(f"Testing MCP Server with CPU Config: {config_name}")
    print(f"{'='*60}\n")

    # Set environment variable for CPU config
    env = os.environ.copy()
    env["RISCV_CPU_CONFIG"] = config_name

    # Spawn the server with the config
    params = StdioServerParameters(
        command=sys.executable, args=["tools/mcp_gen_server/server.py"], env=env
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize session
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"✓ Available MCP Tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            print("\n" + "-" * 60)
            print("Test 1: Search for ADD instruction")
            print("-" * 60)

            # Search for the ADD instruction
            res = await session.call_tool(
                "search_instructions", {"term": "add", "limit": 5}
            )

            data = json.loads(res.content[0].text)
            print(f"Found {data['count']} instructions matching 'add':")
            for inst in data["results"][:3]:
                print(f"  - {inst['name']}: {inst.get('long_name', 'N/A')}")
                print(f"    Encoding: {inst.get('encoding', {}).get('match', 'N/A')}")
                print(f"    Defined by: {inst.get('definedBy', [])}")

            print("\n" + "-" * 60)
            print("Test 2: List all extensions")
            print("-" * 60)

            # List extensions
            res = await session.call_tool("list_extensions", {})
            data = json.loads(res.content[0].text)
            # The response is a list directly
            if isinstance(data, list):
                print(f"Total extensions: {len(data)}")
                print(f"Sample extensions: {[e['name'] for e in data[:10]]}")
            else:
                print(f"Total extensions: {data.get('count', 0)}")
                print(
                    f"Sample extensions: {[e['name'] for e in data.get('extensions', [])[:10]]}"
                )

            print("\n" + "-" * 60)
            print("Test 3: Get extension summary (Base Integer 'I')")
            print("-" * 60)

            # Get summary of I extension
            res = await session.call_tool(
                "extension_summary", {"name": "I", "limit": 10}
            )
            data = json.loads(res.content[0].text)
            print(f"Extension: {data.get('extension', 'N/A')}")
            print(f"Instructions: {data.get('instructions', {}).get('count', 0)}")
            print(f"CSRs: {data.get('csrs', {}).get('count', 0)}")
            print(f"\nSample instructions:")
            insts = data.get("instructions", {}).get("items", [])
            for inst in insts[:5]:
                print(f"  - {inst['name']}: {inst.get('long_name', 'N/A')}")

            print("\n" + "-" * 60)
            print("Test 4: Search for atomic instructions")
            print("-" * 60)

            # Search for atomic extension instructions
            res = await session.call_tool(
                "search_instructions", {"extensions": ["A"], "limit": 10}
            )
            data = json.loads(res.content[0].text)
            print(f"Found {data['count']} instructions in Atomic extension:")
            for inst in data["results"][:5]:
                print(f"  - {inst['name']}: {inst.get('long_name', 'N/A')}")

            print("\n" + "-" * 60)
            print("Test 5: Read specific instruction details (ADD)")
            print("-" * 60)

            # First find the path to add.yaml
            res = await session.call_tool(
                "search_instructions", {"term": "add", "limit": 1}
            )
            data = json.loads(res.content[0].text)
            if data["results"]:
                add_path = data["results"][0]["path"]
                print(f"Reading: {add_path}")

                res = await session.call_tool("read_gen_yaml", {"path": add_path})
                inst_data = json.loads(res.content[0].text)

                print(f"\nInstruction: {inst_data.get('name')}")
                print(f"Long name: {inst_data.get('long_name')}")
                print(f"Description: {inst_data.get('description', '')[:100]}...")
                print(f"Assembly: {inst_data.get('assembly')}")
                print(f"Encoding: {inst_data.get('encoding', {}).get('match')}")
                print(f"\nOperation (IDL):")
                print(f"  {inst_data.get('operation()', 'N/A')}")

            print("\n" + "=" * 60)
            print(f"All tests completed for config: {config_name}")
            print("=" * 60 + "\n")


async def compare_configs():
    """Compare two different CPU configurations"""

    print(f"\n{'='*60}")
    print("Comparing RV64 vs QC_IU Configurations")
    print(f"{'='*60}\n")

    configs = ["rv64", "qc_iu"]
    results = {}

    for config_name in configs:
        env = os.environ.copy()
        env["RISCV_CPU_CONFIG"] = config_name

        params = StdioServerParameters(
            command=sys.executable, args=["tools/mcp_gen_server/server.py"], env=env
        )

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List extensions
                res = await session.call_tool("list_extensions", {})
                data = json.loads(res.content[0].text)

                # Handle both list and dict formats
                if isinstance(data, list):
                    extensions = [e["name"] for e in data]
                    count = len(data)
                else:
                    extensions = [e["name"] for e in data.get("extensions", [])]
                    count = data.get("count", 0)

                results[config_name] = {
                    "extension_count": count,
                    "extensions": extensions,
                }

    # Compare
    print("Comparison Results:")
    print("-" * 60)
    for config, data in results.items():
        print(f"\n{config.upper()}:")
        print(f"  Total extensions: {data['extension_count']}")
        print(f"  Extensions: {', '.join(sorted(data['extensions'][:15]))}")
        if len(data["extensions"]) > 15:
            print(f"  ... and {len(data['extensions']) - 15} more")

    # Find unique extensions
    rv64_only = set(results["rv64"]["extensions"]) - set(results["qc_iu"]["extensions"])
    qc_iu_only = set(results["qc_iu"]["extensions"]) - set(
        results["rv64"]["extensions"]
    )

    if qc_iu_only:
        print(f"\n✨ Extensions unique to QC_IU (custom):")
        for ext in sorted(qc_iu_only):
            print(f"  - {ext}")

    if rv64_only:
        print(f"\n📦 Extensions in RV64 but not QC_IU:")
        print(f"  {', '.join(sorted(list(rv64_only)[:10]))}")
        if len(rv64_only) > 10:
            print(f"  ... and {len(rv64_only) - 10} more")


async def main():
    """Run all tests"""

    # Test with default RV64 config
    await test_cpu_config("rv64")

    # Test with QC IU config
    print("\n" * 2)
    await test_cpu_config("qc_iu")

    # Compare configs
    print("\n" * 2)
    await compare_configs()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
