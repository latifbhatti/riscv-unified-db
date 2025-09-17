#!/usr/bin/env bash
set -euo pipefail

# Launch Codex with MCP server overrides (absolute paths).
# This does NOT require the venv to be activated; it uses the venv's python directly.

codex \
  -c 'mcp_servers.riscv_gen.command="/home/afonsoo/riscv-unified-db/.venv_mcp/bin/python3"' \
  -c 'mcp_servers.riscv_gen.args=["/home/afonsoo/riscv-unified-db/tools/mcp_gen_server/server.py"]' \
  -c 'mcp_servers.riscv_gen.cwd="/home/afonsoo/riscv-unified-db"' \
  -c 'mcp_servers.riscv_gen.startup_timeout_ms=20000' \
  -c 'mcp_servers.riscv_gen.env.PYTHONUNBUFFERED="1"'

