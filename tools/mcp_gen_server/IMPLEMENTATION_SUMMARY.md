<!--
SPDX-License-Identifier: BSD-3-Clause-Clear
Copyright (c) 2025 RISC-V International
-->

# CPU Configuration Support - Implementation Summary

## What Was Implemented

The MCP server now supports **CPU-specific ISA data access** (Option 1: Pre-generate on startup).

### Key Features

1. **Environment Variable Configuration**
   - `RISCV_CPU_CONFIG=<name>` - Select which CPU config to use
   - `FORCE_REGEN=1` - Force regeneration of config data
   - Default: `rv64`

2. **Automatic Scope Limiting**
   - All searches now scoped to `gen/resolved_spec/{CPU_CONFIG}/`
   - Instructions: `gen/resolved_spec/{CPU_CONFIG}/inst/`
   - CSRs: `gen/resolved_spec/{CPU_CONFIG}/csr/`
   - Extensions: `gen/resolved_spec/{CPU_CONFIG}/ext/`

3. **Graceful Fallback**
   - Uses pre-generated configs if available
   - Attempts generation if missing (requires Ruby dependencies)
   - Provides helpful error messages with workarounds

## Files Modified

1. **`tools/mcp_gen_server/server.py`**
   - Added `CPU_CONFIG` and `CONFIG_GEN_DIR` globals
   - Added `generate_cpu_config()` function
   - Modified all `_iter_*_yaml_paths()` functions to search only in config dir
   - Updated `main()` to check/generate config on startup

## Files Created

1. **`tools/mcp_gen_server/README_CPU_CONFIG.md`**
   - Complete usage guide
   - Configuration examples
   - Troubleshooting tips

2. **`tools/mcp_gen_server/gen_config.rb`**
   - Helper script for Ruby-based generation
   - Requires bundler dependencies

3. **`tools/mcp_gen_server/test_config.sh`**
   - Test script to verify functionality

4. **`tools/mcp_gen_server/IMPLEMENTATION_SUMMARY.md`**
   - This file

## Usage Examples

### Use Default (RV64)
```bash
python3 tools/mcp_gen_server/server.py
```

### Use QC IU Configuration
```bash
RISCV_CPU_CONFIG=qc_iu python3 tools/mcp_gen_server/server.py
```

### Pre-generate a Config
```bash
cd /home/afonso/riscv-unified-db
bundle install  # If not already done
bundle exec rake gen:resolved_arch CFG=<config>
```

## Test Results

✅ **Passing Tests:**
- Server starts with default rv64 config
- Server switches to qc_iu config via environment variable
- All queries scoped to selected config directory
- Graceful error handling for missing configs
- Helpful error messages listing available configs

⚠️ **Known Limitation:**
- Automatic generation requires Ruby bundler dependencies
- Workaround: Pre-generate configs using `bundle exec rake gen:resolved_arch CFG=<config>`

## Impact on LLM Deterministic Access

### Before
- LLM queries all ISA data (mixed configs)
- No way to specify target CPU/SoC
- Results include instructions from all extensions

### After
- LLM queries data for specific CPU configuration
- Can compare multiple configs by running multiple servers
- Results accurately reflect what's available on target hardware

### Example Use Case

**Query:** "What atomic instructions are available on the QC IU processor?"

**Before:**
```
Search all instructions → Returns all atomic instructions from spec
(Includes some not implemented in QC IU)
```

**After:**
```bash
RISCV_CPU_CONFIG=qc_iu python server.py
search_instructions({"extensions": ["A"]})
→ Returns only atomic instructions implemented in QC IU config
```

## Available Configurations

Currently pre-generated:
- ✓ `_` - Minimal generic
- ✓ `rv64` - Generic RV64 (default)
- ✓ `qc_iu` - Qualcomm IU with Xqci/Xqccmp
- ✓ `example_rv64_with_overlay` - Example with overlays

Can be generated:
- `rv32` - Generic RV32
- `MC100-32` - MC100-32 processor
- `mc100-32-riscv-tests` - MC100-32 for tests
- `mc100-32-full-example` - MC100-32 full example

## Architecture

```
┌─────────────────────────────────────────┐
│  MCP Server Startup                     │
│  ┌──────────────────────────────────┐   │
│  │ Read RISCV_CPU_CONFIG env var    │   │
│  │ (default: rv64)                  │   │
│  └──────────┬───────────────────────┘   │
│             │                            │
│             ▼                            │
│  ┌──────────────────────────────────┐   │
│  │ Check gen/resolved_spec/{CONFIG}/ exists  │   │
│  └──────────┬───────────────────────┘   │
│             │                            │
│      ┌──────┴──────┐                    │
│      │             │                    │
│    Exists      Missing                  │
│      │             │                    │
│      │             ▼                    │
│      │    ┌────────────────────┐        │
│      │    │ Attempt generation │        │
│      │    │ (bundle exec ruby) │        │
│      │    └────────┬───────────┘        │
│      │             │                    │
│      │      ┌──────┴──────┐             │
│      │      │             │             │
│      │    Success      Fail             │
│      │      │             │             │
│      │      │             ▼             │
│      │      │    ┌────────────────┐     │
│      │      │    │ Show error +   │     │
│      │      │    │ workarounds    │     │
│      │      │    │ EXIT           │     │
│      │      │    └────────────────┘     │
│      │      │                           │
│      ▼      ▼                           │
│  ┌──────────────────────────────────┐   │
│  │ Set CONFIG_GEN_DIR               │   │
│  │ Start MCP server                 │   │
│  │ All queries scoped to CONFIG     │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Integration Example

### Claude Code MCP Configuration

```json
{
  "mcpServers": {
    "riscv-rv64": {
      "command": "python3",
      "args": ["/path/to/riscv-unified-db/tools/mcp_gen_server/server.py"],
      "env": {
        "RISCV_CPU_CONFIG": "rv64"
      }
    },
    "riscv-qc-iu": {
      "command": "python3",
      "args": ["/path/to/riscv-unified-db/tools/mcp_gen_server/server.py"],
      "env": {
        "RISCV_CPU_CONFIG": "qc_iu"
      }
    }
  }
}
```

This allows an LLM to query both configurations simultaneously and compare!

## Future Enhancements

Possible improvements (not implemented):

1. **MCP Tool to Switch Configs**
   - Dynamic config switching without restarting server
   - `set_cpu_config({"config": "rv32"})`

2. **Config Comparison Tool**
   - `compare_configs({"configs": ["rv32", "rv64"]})`
   - Returns differences in extensions, parameters

3. **Binary Decoding Tool**
   - `decode_instruction({"binary": "0x00c58533", "config": "rv64"})`
   - Returns decoded instruction details

4. **Dependency Resolution**
   - `get_dependencies({"instruction": "mul"})`
   - Returns required extensions and parameters

## Conclusion

Option 1 implementation is complete and working! The MCP server now provides **deterministic, CPU-specific ISA queries** while remaining simple and maintainable.

The key insight: **Pre-generated configs** work better than runtime generation for this use case, as ISA data changes infrequently and generation is heavyweight.
