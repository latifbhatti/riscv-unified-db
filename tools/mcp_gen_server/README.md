Minimal MCP server for reading YAML files under `gen/` and searching instruction YAMLs.

What it does:
- Tool `list_gen_yaml`: lists YAML files under `gen/` relative to repo root.
- Tool `read_gen_yaml`: reads one YAML file (validated path) and returns parsed data.
- Tool `search_instructions`: searches instruction YAMLs by filename/path substring, required keys, and extensions.

Prereqs:
- Python 3.10+.
- A virtual environment with `mcp` and `pyyaml` installed.

Setup:
1) Create venv and install deps
   - `python3 -m venv .venv_mcp`
   - `. .venv_mcp/bin/activate`
   - `pip install "mcp[cli]" pyyaml`

Run the server:
- From repo root: `. .venv_mcp/bin/activate && python3 tools/mcp_gen_server/server.py`
- The server speaks MCP over stdio. Use an MCP-compatible client (e.g., Codex) to connect.

Local validation:
- `. .venv_mcp/bin/activate && python3 tools/mcp_gen_server/client_demo.py`

Search tool:
- Name: `search_instructions`
- Args:
  - `term` (string, optional): substring to match in filename/path
  - `keys` (array<string>, optional): top-level YAML keys required to exist
  - `extensions` (array<string>, optional): extension symbols to match (either in `definedBy` or from `inst/<ext>/...` path)
  - `limit` (int, default 50): max results
- Returns: structuredContent `{ count, results: [...] }` plus JSON text content for compatibility.

Tools exposed:
- `list_gen_yaml` args: none. Returns list of repo-relative paths.
- `read_gen_yaml` args: `{ "path": "gen/.../file.yaml" }`.
  - Only allows paths inside `gen/` and ending in `.yaml`/`.yml`.

Notes:
- Paths are normalized and validated to avoid directory traversal.
- Large files are returned as structured JSON (parsed YAML). If you need raw text,
  you can adjust the `read_gen_yaml` tool to add a `raw` flag.
