<!--
SPDX-License-Identifier: BSD-3-Clause-Clear
Copyright (c) 2025 RISC-V International
-->

Minimal MCP server for reading generated YAML under
`gen/resolved_spec/<config>/` and searching ISA data.

What it does:
- Scopes queries to `gen/resolved_spec/<RISCV_CPU_CONFIG>` (default: `rv64`).
- Exposes tools to list/read YAML, search instructions/CSRs/extensions, and read
  IDL function docs.
- Adds config/status utilities (`list_configs`, `get_config`, `server_stats`).

Prereqs:
- Python 3.10+.
- A virtual environment with `mcp` and `pyyaml` installed.

Setup:
1) Container workflow (recommended)
   - `./do mcp:server` (uses `.home/.venv` and installs deps via `requirements.txt`)
   - `./do mcp:client_demo`

2) Local venv (standalone)
   - `python3 -m venv .venv_mcp`
   - `. .venv_mcp/bin/activate`
   - `pip install "mcp[cli]" pyyaml`

Run the server:
- From repo root: `./do mcp:server` (or `. .venv_mcp/bin/activate && python3 tools/mcp_gen_server/server.py`)
- The server speaks MCP over stdio. Use an MCP-compatible client (e.g., Codex) to connect.

Local validation:
- `./do mcp:client_demo` (or `. .venv_mcp/bin/activate && python3 tools/mcp_gen_server/client_demo.py`)

Search tool:
- Name: `search_instructions`
- Args:
  - `term` (string, optional): substring to match in filename/path
  - `keys` (array<string>, optional): top-level YAML keys required to exist
  - `extensions` (array<string>, optional): extension symbols to match (either in `definedBy` or from `inst/<ext>/...` path)
  - `limit` (int, default 50): max results
- Returns: structuredContent `{ count, results: [...] }` plus JSON text content for compatibility.

Tools exposed:
- `list_gen_yaml` args: `{ "subdir": "inst", "limit": 100 }` (both optional).
  Returns list of repo-relative paths under the active config.
- `read_gen_yaml` args: `{ "path": "gen/.../file.yaml" }`.
  - Only allows paths inside `gen/` and ending in `.yaml`/`.yml`.
- `search_instructions`, `search_csrs`, `list_extensions`, `read_extension`,
  `extension_summary`
- `list_functions`, `read_function_doc`, `search_functions`,
  `find_function_usages`
- `list_configs`, `get_config`, `server_stats`

Notes:
- Paths are normalized and validated to avoid directory traversal.
- Large files are returned as structured JSON (parsed YAML). If you need raw text,
  you can adjust the `read_gen_yaml` tool to add a `raw` flag.
- Env vars:
  - `RISCV_CPU_CONFIG`: select config (default `rv64`)
  - `FORCE_REGEN=1`: regenerate config on startup
  - `MCP_DISABLE_CACHE=1`: disable YAML/path caching
  - `MCP_DEBUG=1`: log YAML parse errors to stderr
