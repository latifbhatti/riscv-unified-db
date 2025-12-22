#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

import asyncio
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    # Use the current Python interpreter to spawn the server (works in venvs)
    params = StdioServerParameters(
        command=sys.executable, args=["tools/mcp_gen_server/server.py"]
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            res = await session.call_tool("list_gen_yaml", {})
            print("list_gen_yaml: ", res.content[0].text[:200], "...")

            # Pick one and read it
            import json

            lst = json.loads(res.content[0].text)
            if lst:
                r = await session.call_tool("read_gen_yaml", {"path": lst[0]})
                print("read_gen_yaml sample: ", r.content[0].text[:200], "...")


if __name__ == "__main__":
    asyncio.run(main())
