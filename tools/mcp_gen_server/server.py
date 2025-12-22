#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
import re
from mcp.server.lowlevel.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = REPO_ROOT / "gen"

# CPU Configuration
CPU_CONFIG = os.environ.get("RISCV_CPU_CONFIG", "rv64")
FORCE_REGEN = os.environ.get("FORCE_REGEN", "").lower() in ("1", "true", "yes")
DEBUG = os.environ.get("MCP_DEBUG", "").lower() in ("1", "true", "yes")
DISABLE_CACHE = os.environ.get("MCP_DISABLE_CACHE", "").lower() in (
    "1",
    "true",
    "yes",
)

_YAML_CACHE: Dict[Path, tuple[float, Dict[str, Any]]] = {}
_PATH_CACHE: Dict[str, List[Path]] = {}


def _debug(msg: str) -> None:
    if DEBUG:
        print(msg, file=sys.stderr)


CONFIG_GEN_DIR = GEN_DIR / "resolved_spec" / CPU_CONFIG


def generate_cpu_config(config_name: str, force: bool = False) -> bool:
    """
    Generate ISA data for a specific CPU configuration using Ruby resolver

    Returns:
        True if successful or already exists, False on error
    """
    gen_dir = GEN_DIR / "resolved_spec" / config_name

    # Check if already generated
    if gen_dir.exists() and not force:
        print(f"Config '{config_name}' already generated at {gen_dir}", file=sys.stderr)
        return True

    # Verify config file exists
    config_file = REPO_ROOT / "cfgs" / f"{config_name}.yaml"
    if not config_file.exists():
        print(f"ERROR: Config file not found: {config_file}", file=sys.stderr)
        return False

    try:
        print(f"Generating ISA data for config '{config_name}'...", file=sys.stderr)

        env = os.environ.copy()
        env["CFG"] = config_name

        result = subprocess.run(
            ["bundle", "exec", "rake", "gen:resolved_arch"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            print(f"ERROR: Ruby generation failed", file=sys.stderr)
            print(f"STDOUT: {result.stdout}", file=sys.stderr)
            print(f"STDERR: {result.stderr}", file=sys.stderr)
            return False

        if not gen_dir.exists():
            print(
                f"ERROR: Expected generated data missing at {gen_dir}",
                file=sys.stderr,
            )
            return False

        print(f"Success: {result.stdout.strip()}", file=sys.stderr)
        return True

    except subprocess.TimeoutExpired:
        print(f"ERROR: Generation timed out (>5 minutes)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False


def _cache_stats() -> Dict[str, Any]:
    return {
        "enabled": not DISABLE_CACHE,
        "yaml_entries": len(_YAML_CACHE),
        "path_entries": len(_PATH_CACHE),
    }


def _find_config_path(config_name: str) -> str | None:
    cfg_dir = REPO_ROOT / "cfgs"
    for ext in (".yaml", ".yml"):
        cand = cfg_dir / f"{config_name}{ext}"
        if cand.exists():
            return str(cand.relative_to(REPO_ROOT))
    return None


def _list_config_entries() -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    cfg_dir = REPO_ROOT / "cfgs"
    if cfg_dir.exists():
        for pat in ("*.yaml", "*.yml"):
            for p in cfg_dir.glob(pat):
                name = p.stem
                entry = entries.setdefault(name, {"name": name})
                entry["config_path"] = str(p.relative_to(REPO_ROOT))
    root_dir = GEN_DIR / "resolved_spec"
    if root_dir.exists():
        for p in root_dir.iterdir():
            if not p.is_dir():
                continue
            name = p.name
            entry = entries.setdefault(name, {"name": name})
            entry.setdefault("data_dirs", [])
            entry["data_dirs"].append(str(p.relative_to(REPO_ROOT)))
    for entry in entries.values():
        entry.setdefault("config_path", None)
        data_dirs = entry.get("data_dirs", [])
        entry["gen_dir"] = data_dirs[0] if data_dirs else None
        entry["data_root"] = "resolved_spec" if data_dirs else None
        entry["generated"] = bool(data_dirs)
        entry.setdefault("data_dirs", [])
        entry["active"] = entry["name"] == CPU_CONFIG
        entry["default"] = entry["name"] == "rv64"
    return sorted(entries.values(), key=lambda x: x["name"])


def _ensure_in_gen(path: Path) -> Path:
    # Normalize and ensure the path is inside gen/
    p = (REPO_ROOT / path).resolve()
    if not str(p).startswith(str(GEN_DIR.resolve())):
        raise ValueError("Path must be inside 'gen/'")
    if not p.suffix.lower() in {".yaml", ".yml"}:
        raise ValueError("Path must end with .yaml or .yml")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    return p


def _iter_yaml_paths(root: Path) -> List[Path]:
    if not root.exists():
        return []
    key = str(root.resolve())
    if not DISABLE_CACHE and key in _PATH_CACHE:
        return _PATH_CACHE[key]
    paths: List[Path] = []
    for walk_root, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".yaml", ".yml")):
                paths.append(Path(walk_root) / f)
    paths.sort(key=lambda p: str(p))
    if not DISABLE_CACHE:
        _PATH_CACHE[key] = paths
    return paths


async def list_gen_yaml(args: Dict[str, Any] | None = None):
    args = args or {}
    subdir = args.get("subdir")
    limit = args.get("limit")

    root = CONFIG_GEN_DIR
    if subdir is not None:
        if not isinstance(subdir, str):
            raise ValueError("'subdir' must be a string")
        sub_path = Path(subdir)
        if sub_path.is_absolute() or ".." in sub_path.parts:
            raise ValueError("'subdir' must be a relative path under the config dir")
        root = (CONFIG_GEN_DIR / sub_path).resolve()
        if not str(root).startswith(str(CONFIG_GEN_DIR.resolve())):
            raise ValueError("'subdir' must be within the config dir")

    paths = [str(p.relative_to(REPO_ROOT)) for p in _iter_yaml_paths(root)]
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError("'limit' must be an integer")
        if limit < 1:
            raise ValueError("'limit' must be >= 1")
        paths = paths[:limit]
    return [TextContent(type="text", text=json.dumps(paths))]


async def read_gen_yaml(args: Dict[str, Any]):
    rel = args.get("path")
    if not isinstance(rel, str):
        raise ValueError("'path' arg must be a string")
    p = _ensure_in_gen(Path(rel))
    data = _load_yaml(p)
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


async def list_configs(_: Dict[str, Any] | None = None):
    return {"configs": _list_config_entries()}


async def get_config(_: Dict[str, Any] | None = None):
    data_root = "resolved_spec"
    return {
        "config": CPU_CONFIG,
        "config_path": _find_config_path(CPU_CONFIG),
        "gen_dir": str(CONFIG_GEN_DIR.relative_to(REPO_ROOT)),
        "data_root": data_root,
        "generated": CONFIG_GEN_DIR.exists(),
        "force_regen": FORCE_REGEN,
        "cache": _cache_stats(),
    }


async def server_stats(_: Dict[str, Any] | None = None):
    data_root = "resolved_spec"
    return {
        "config": CPU_CONFIG,
        "gen_dir": str(CONFIG_GEN_DIR.relative_to(REPO_ROOT)),
        "data_root": data_root,
        "generated": CONFIG_GEN_DIR.exists(),
        "counts": {
            "yaml": len(_iter_yaml_paths(CONFIG_GEN_DIR)),
            "instructions": len(_iter_instruction_yaml_paths()),
            "csrs": len(_iter_csr_yaml_paths()),
            "extensions": len(_iter_extension_yaml_paths()),
        },
        "cache": _cache_stats(),
    }


def _iter_instruction_yaml_paths() -> List[Path]:
    inst_dir = CONFIG_GEN_DIR / "inst"
    return _iter_yaml_paths(inst_dir)


def _iter_csr_yaml_paths() -> List[Path]:
    csr_dir = CONFIG_GEN_DIR / "csr"
    return _iter_yaml_paths(csr_dir)


def _iter_extension_yaml_paths() -> List[Path]:
    ext_dir = CONFIG_GEN_DIR / "ext"
    return _iter_yaml_paths(ext_dir)


def _extract_defined_by(data: dict) -> List[str]:
    defined = data.get("definedBy")
    if defined is None:
        return []
    if isinstance(defined, str):
        return [defined]
    if isinstance(defined, list):
        return [str(x) for x in defined]
    if isinstance(defined, dict):
        # handle anyOf / allOf patterns
        for k in ("anyOf", "allOf", "oneOf"):
            if k in defined and isinstance(defined[k], list):
                return [str(x) for x in defined[k]]
    return []


def _extension_in_path(rel_parts: List[str]) -> str | None:
    # Find segment right after 'inst' as a heuristic extension name
    for i, part in enumerate(rel_parts):
        if part == "inst" and i + 1 < len(rel_parts):
            return rel_parts[i + 1]
    return None


async def search_instructions(args: Dict[str, Any]):
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(
        isinstance(e, str) for e in extensions
    ):
        raise ValueError("'extensions' must be a list of strings")

    ext_set = {e for e in extensions}
    results: List[dict[str, Any]] = []
    count = 0

    for p in _iter_instruction_yaml_paths():
        rel = p.relative_to(REPO_ROOT)
        rel_str = str(rel)
        # Basic filename/path term match
        if term:
            namepart = p.stem.lower()
            if term.lower() not in namepart and term.lower() not in rel_str.lower():
                continue

        try:
            data = _load_yaml(p)
        except Exception:
            continue

        # Keys existence filter
        if keys and not all(k in data for k in keys):
            continue

        defined_by = _extract_defined_by(data)
        ext_from_path = _extension_in_path(
            rel.relative_to(GEN_DIR).parts if rel.is_relative_to(GEN_DIR) else rel.parts
        )

        # Extension filter
        if ext_set:
            present = set(defined_by)
            if ext_from_path:
                present.add(ext_from_path)
            if present.isdisjoint(ext_set):
                continue

        info = {
            "path": rel_str,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "assembly": data.get("assembly"),
            "encoding": (
                {"match": data.get("encoding", {}).get("match")}
                if isinstance(data.get("encoding"), dict)
                else None
            ),
            "definedBy": defined_by,
            "extensionInPath": ext_from_path,
        }
        results.append(info)
        count += 1
        if count >= limit:
            break

    # Return structured content (dict). The server decorator will also emit JSON text.
    return {"count": count, "results": results}


# ----- Functions (IDL) helpers -----


def _find_funcs_adoc() -> tuple[Path | None, Path | None]:
    funcs_doc = None
    all_funcs = None
    cfg_root = GEN_DIR / "cfg_html_doc"
    if not cfg_root.exists():
        return None, None
    for root, dirs, files in os.walk(cfg_root):
        root_p = Path(root)
        # prefer antora/modules/funcs/pages/funcs.adoc
        if (
            root_p.name == "pages"
            and "funcs" in root_p.parts
            and "modules" in root_p.parts
        ):
            cand = root_p / "funcs.adoc"
            if cand.exists():
                funcs_doc = cand
        if root_p.name == "funcs" and root_p.parent.name == "adoc":
            cand_all = root_p / "all_funcs.adoc"
            if cand_all.exists():
                all_funcs = cand_all
    return funcs_doc, all_funcs


def _parse_all_funcs_names(all_funcs_path: Path) -> list[str]:
    names: list[str] = []
    try:
        with open(all_funcs_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("* ") and "`" in line:
                    # format: * `name`
                    back = re.findall(r"`([^`]+)\`?", line)
                    if back:
                        names.append(back[0])
    except Exception:
        pass
    return names


def _parse_funcs_sections(funcs_path: Path) -> dict[str, str]:
    sections: dict[str, str] = {}
    try:
        with open(funcs_path, encoding="utf-8") as fh:
            content = fh.read()
        # Split on level 2 headings "== name" (start of line)
        parts = re.split(r"^==\s+", content, flags=re.M)
        # parts[0] is preamble; subsequent parts are "Name\n<body>"
        for part in parts[1:]:
            lines = part.splitlines()
            if not lines:
                continue
            header = lines[0].strip()
            name = header.split()[0]
            body = "\n".join(lines[1:]).strip()
            sections[name] = body
    except Exception:
        pass
    return sections


async def list_functions(_: Dict[str, Any] | None = None):
    funcs_doc, all_funcs = _find_funcs_adoc()
    names: list[str] = []
    if all_funcs:
        names = _parse_all_funcs_names(all_funcs)
    else:
        # fallback: parse sections to get names
        if funcs_doc:
            sections = _parse_funcs_sections(funcs_doc)
            names = sorted(sections.keys())
    return {"functions": names}


async def read_function_doc(args: Dict[str, Any]):
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")
    funcs_doc, all_funcs = _find_funcs_adoc()
    sections = _parse_funcs_sections(funcs_doc) if funcs_doc else {}
    body = sections.get(name)
    if body is None:
        # try to find header line that starts with the name followed by space or '(' (e.g., 'implemented? (generated)')
        for k, v in sections.items():
            if k.startswith(name):
                body = v
                name = k
                break
    return {"name": name, "doc": body, "source": str(funcs_doc) if funcs_doc else None}


async def search_functions(args: Dict[str, Any]):
    term = args.get("term")
    if not isinstance(term, str) or not term:
        raise ValueError("'term' is required")
    funcs_doc, all_funcs = _find_funcs_adoc()
    sections = _parse_funcs_sections(funcs_doc) if funcs_doc else {}
    out: list[dict[str, str | None]] = []
    for k, v in sections.items():
        if term.lower() in k.lower() or (v and term.lower() in v.lower()):
            out.append({"name": k, "snippet": v[:300] if v else None})
    return {"count": len(out), "results": out}


async def find_function_usages(args: Dict[str, Any]):
    name = args.get("name")
    limit = int(args.get("limit") or 50)
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")
    pat = re.compile(re.escape(name) + r"\s*\(")
    hits: list[dict[str, str]] = []
    count = 0
    # scan instruction YAMLs
    for p in _iter_instruction_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        for key in ("operation()", "sail()"):
            val = data.get(key)
            if isinstance(val, str) and (name in val):  # quick filter
                # crude snippet around first occurrence
                idx = val.find(name)
                snippet = val[max(0, idx - 60) : idx + 120]
                hits.append(
                    {
                        "path": str(p.relative_to(REPO_ROOT)),
                        "key": key,
                        "snippet": snippet,
                    }
                )
                count += 1
                if count >= limit:
                    return {"count": count, "results": hits}
    return {"count": count, "results": hits}


# ----- CSR tools -----


def _csr_extensions(data: dict) -> set[str]:
    exts: set[str] = set()
    top = data.get("definedBy")
    if isinstance(top, str):
        exts.add(top)
    elif isinstance(top, list):
        exts.update(str(x) for x in top)
    fields = data.get("fields")
    if isinstance(fields, dict):
        for fld in fields.values():
            if isinstance(fld, dict) and "definedBy" in fld:
                db = fld.get("definedBy")
                if isinstance(db, str):
                    exts.add(db)
                elif isinstance(db, list):
                    exts.update(str(x) for x in db)
    return exts


async def search_csrs(args: Dict[str, Any]):
    term = args.get("term")
    keys = args.get("keys") or []
    extensions = args.get("extensions") or []
    limit = int(args.get("limit") or 50)

    if term is not None and not isinstance(term, str):
        raise ValueError("'term' must be a string if provided")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError("'keys' must be a list of strings")
    if not isinstance(extensions, list) or not all(
        isinstance(e, str) for e in extensions
    ):
        raise ValueError("'extensions' must be a list of strings")

    ext_set = set(extensions)
    results: List[dict[str, Any]] = []
    count = 0
    for p in _iter_csr_yaml_paths():
        rel = str(p.relative_to(REPO_ROOT))
        if term:
            if term.lower() not in p.stem.lower() and term.lower() not in rel.lower():
                continue
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        if keys and not all(k in data for k in keys):
            continue
        csr_exts = _csr_extensions(data)
        if ext_set and csr_exts.isdisjoint(ext_set):
            continue
        info = {
            "path": rel,
            "kind": data.get("kind"),
            "name": data.get("name"),
            "long_name": data.get("long_name"),
            "address": data.get("address"),
            "priv_mode": data.get("priv_mode"),
            "definedBy": list(csr_exts),
        }
        results.append(info)
        count += 1
        if count >= limit:
            break
    return {"count": count, "results": results}


# ----- Extension tools and associations -----


def _load_yaml(path: Path) -> dict:
    mtime: float | None = None
    if not DISABLE_CACHE:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            _YAML_CACHE.pop(path, None)
            raise
        cached = _YAML_CACHE.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        _debug(f"YAML load failed for {path}: {exc}")
        raise
    if not DISABLE_CACHE and mtime is not None:
        _YAML_CACHE[path] = (mtime, data)
    return data


async def list_extensions(_: Dict[str, Any] | None = None):
    items: list[dict[str, Any]] = []
    for p in _iter_extension_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        if data.get("kind") == "extension" and isinstance(data.get("name"), str):
            items.append(
                {
                    "path": str(p.relative_to(REPO_ROOT)),
                    "name": data.get("name"),
                    "long_name": data.get("long_name"),
                }
            )
    # De-dup by name, favor shortest path
    by_name: dict[str, dict[str, Any]] = {}
    for it in items:
        n = it["name"]
        if n not in by_name or len(it["path"]) < len(by_name[n]["path"]):
            by_name[n] = it
    extensions = sorted(by_name.values(), key=lambda x: x["name"])
    return {"count": len(extensions), "extensions": extensions}


async def read_extension(args: Dict[str, Any]):
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")
    for p in _iter_extension_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        if data.get("kind") == "extension" and data.get("name") == name:
            return {
                "path": str(p.relative_to(REPO_ROOT)),
                "extension": data,
            }
    return {"path": None, "extension": None}


async def extension_summary(args: Dict[str, Any]):
    name = args.get("name")
    limit = int(args.get("limit") or 2000)
    if not isinstance(name, str) or not name:
        raise ValueError("'name' is required")
    # Extension metadata
    ext_meta = await read_extension({"name": name})
    # Instructions
    insts: list[dict[str, Any]] = []
    for p in _iter_instruction_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        defined_by = set(_extract_defined_by(data))
        rel_parts = (
            p.relative_to(GEN_DIR).parts if str(p).startswith(str(GEN_DIR)) else p.parts
        )
        ext_from_path = _extension_in_path(list(rel_parts))
        if name in defined_by or (ext_from_path == name):
            insts.append(
                {
                    "path": str(p.relative_to(REPO_ROOT)),
                    "name": data.get("name"),
                    "assembly": data.get("assembly"),
                    "encoding": (
                        data.get("encoding", {}).get("match")
                        if isinstance(data.get("encoding"), dict)
                        else None
                    ),
                }
            )
            if len(insts) >= limit:
                break
    # CSRs
    csrs: list[dict[str, Any]] = []
    for p in _iter_csr_yaml_paths():
        try:
            data = _load_yaml(p)
        except Exception:
            continue
        csr_exts = _csr_extensions(data)
        if name in csr_exts:
            csrs.append(
                {
                    "path": str(p.relative_to(REPO_ROOT)),
                    "name": data.get("name"),
                    "address": data.get("address"),
                    "priv_mode": data.get("priv_mode"),
                }
            )
            if len(csrs) >= limit:
                break
    return {
        "extension": name,
        "metadata": ext_meta,
        "instructions": {"count": len(insts), "items": insts},
        "csrs": {"count": len(csrs), "items": csrs},
    }


async def main() -> None:
    # Pre-generate the CPU configuration if needed
    print(f"MCP Server starting with CPU config: {CPU_CONFIG}", file=sys.stderr)

    # Check if config exists
    if not CONFIG_GEN_DIR.exists() or FORCE_REGEN:
        print(
            f"Config '{CPU_CONFIG}' not found, attempting to generate...",
            file=sys.stderr,
        )
        if not generate_cpu_config(CPU_CONFIG, force=FORCE_REGEN):
            print(f"", file=sys.stderr)
            print(f"ERROR: Failed to generate config '{CPU_CONFIG}'", file=sys.stderr)
            print(f"", file=sys.stderr)
            print(f"Workaround: Pre-generate using rake:", file=sys.stderr)
            print(f"  cd {REPO_ROOT}", file=sys.stderr)
            print(f"  bundle install", file=sys.stderr)
            print(f"  bundle exec rake gen:resolved_arch CFG={CPU_CONFIG}", file=sys.stderr)
            print(f"", file=sys.stderr)
            print(f"Available pre-generated configs:", file=sys.stderr)
            root_dir = GEN_DIR / "resolved_spec"
            if root_dir.exists():
                for cfg in sorted(root_dir.iterdir()):
                    if cfg.is_dir():
                        print(f"  ✓ {cfg.name}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Using pre-generated config at: {CONFIG_GEN_DIR}", file=sys.stderr)

    server = Server("gen-yaml-mcp")

    @server.list_tools()
    async def _list_tools() -> List[Tool]:
        return [
            Tool(
                name="list_gen_yaml",
                description=(
                    "List YAML files under gen/resolved_spec/<config>/ as repo-relative paths"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subdir": {
                            "type": "string",
                            "description": "optional subdir under config (e.g. inst/, csr/, ext/)",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5000,
                        },
                    },
                },
            ),
            Tool(
                name="read_gen_yaml",
                description="Read and parse a YAML under gen/; returns JSON string",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "repo-relative path under gen/",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="list_configs",
                description="List available CPU configs and whether data is generated",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_config",
                description="Return active CPU config and cache status",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="server_stats",
                description="Return counts for the active config and cache stats",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="search_instructions",
                description=(
                    "Search instruction YAMLs by filename and keys; optionally filter by defining extensions"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "substring to match in filename/path",
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "top-level YAML keys that must exist",
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "extension symbols to match (definedBy or path)",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                },
            ),
            Tool(
                name="list_functions",
                description="List IDL function names from generated docs (funcs/all_funcs)",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="read_function_doc",
                description="Read function documentation section by name",
                inputSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            ),
            Tool(
                name="search_functions",
                description="Search function docs for a term (name or content)",
                inputSchema={
                    "type": "object",
                    "properties": {"term": {"type": "string"}},
                    "required": ["term"],
                },
            ),
            Tool(
                name="find_function_usages",
                description="Find instruction YAMLs whose operation()/sail() reference the function",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="search_csrs",
                description="Search CSR YAMLs by name/path, filter by top-level keys and extensions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "keys": {"type": "array", "items": {"type": "string"}},
                        "extensions": {"type": "array", "items": {"type": "string"}},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 50,
                        },
                    },
                },
            ),
            Tool(
                name="list_extensions",
                description="List extension YAMLs (name + path)",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="read_extension",
                description="Read extension YAML by name",
                inputSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            ),
            Tool(
                name="extension_summary",
                description="Summarize an extension: its instructions and CSRs",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
                    },
                    "required": ["name"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: Dict[str, Any] | None):
        args = arguments or {}
        if name == "list_gen_yaml":
            return await list_gen_yaml(args)
        if name == "read_gen_yaml":
            return await read_gen_yaml(args)
        if name == "list_configs":
            return await list_configs(args)
        if name == "get_config":
            return await get_config(args)
        if name == "server_stats":
            return await server_stats(args)
        if name == "search_instructions":
            return await search_instructions(args)
        if name == "list_functions":
            return await list_functions(args)
        if name == "read_function_doc":
            return await read_function_doc(args)
        if name == "search_functions":
            return await search_functions(args)
        if name == "find_function_usages":
            return await find_function_usages(args)
        if name == "search_csrs":
            return await search_csrs(args)
        if name == "list_extensions":
            return await list_extensions(args)
        if name == "read_extension":
            return await read_extension(args)
        if name == "extension_summary":
            return await extension_summary(args)
        raise ValueError(f"Unknown tool: {name}")

    # Run over stdio transport (for MCP clients like Codex)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
