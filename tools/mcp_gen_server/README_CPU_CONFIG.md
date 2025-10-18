<!--
SPDX-License-Identifier: BSD-3-Clause-Clear
Copyright (c) 2025 RISC-V International
-->

# CPU Configuration Support for MCP Server

The MCP server now supports generating and serving ISA data for specific CPU configurations.

## Usage

### Default Configuration (RV64)

```bash
cd /home/afonso/riscv-unified-db/tools/mcp_gen_server
python server.py
```

This will use the default `rv64` configuration.

### Specify a Different CPU Configuration

Use the `RISCV_CPU_CONFIG` environment variable:

```bash
# Use the qc_iu configuration (Qualcomm IU with custom extensions)
RISCV_CPU_CONFIG=qc_iu python server.py

# Use rv32 configuration
RISCV_CPU_CONFIG=rv32 python server.py

# Use example_rv64_with_overlay
RISCV_CPU_CONFIG=example_rv64_with_overlay python server.py
```

### Force Regeneration

If you've made changes to the config files and want to regenerate:

```bash
FORCE_REGEN=1 RISCV_CPU_CONFIG=qc_iu python server.py
```

## Available Configurations

Configurations are defined in `cfgs/*.yaml`. Currently available:

- `_` - Minimal generic configuration
- `rv64` - Generic RV64 system (default)
- `rv32` - Generic RV32 system
- `qc_iu` - Qualcomm IU with Xqci and Xqccmp custom extensions
- `example_rv64_with_overlay` - Example RV64 with custom overlays
- `MC100-32` - MC100-32 processor
- `mc100-32-riscv-tests` - MC100-32 for RISC-V tests
- `mc100-32-full-example` - MC100-32 full example

## How It Works

### 1. Startup Sequence

When the MCP server starts:

1. Reads `RISCV_CPU_CONFIG` environment variable (defaults to `rv64`)
2. Checks if `gen/arch/{CPU_CONFIG}/` exists
3. If not, or if `FORCE_REGEN=1`, runs Ruby code:
   ```ruby
   require 'udb/resolver'
   resolver = Udb::Resolver.new(REPO_ROOT)
   cfg_arch = resolver.cfg_arch_for(CPU_CONFIG)
   ```
4. This generates resolved ISA data in `gen/arch/{CPU_CONFIG}/`

### 2. Data Structure

Generated data is organized as:

```
gen/arch/{CPU_CONFIG}/
├── inst/          # Instructions for this configuration
│   ├── I/         # Base Integer extension instructions
│   ├── M/         # Multiply/Divide
│   ├── A/         # Atomic
│   └── ...
├── csr/           # Control/Status Registers
│   ├── I/
│   ├── Zicsr/
│   └── ...
└── ext/           # Extension definitions
    ├── I.yaml
    ├── M.yaml
    └── ...
```

### 3. Query Scope

All MCP tool queries are automatically scoped to the selected configuration:

- `search_instructions` → searches only `gen/arch/{CPU_CONFIG}/inst/`
- `search_csrs` → searches only `gen/arch/{CPU_CONFIG}/csr/`
- `list_extensions` → lists only `gen/arch/{CPU_CONFIG}/ext/`

## Configuration Files

Configuration files in `cfgs/*.yaml` define:

- **Extensions**: Which ISA extensions are implemented
- **Parameters**: MXLEN, PHYS_ADDR_WIDTH, etc.
- **Overlays**: Custom or vendor-specific additions
- **Behavior**: Exception handling, timing, etc.

### Example: `cfgs/qc_iu.yaml`

```yaml
kind: architecture configuration
type: fully configured
name: qc_iu
arch_overlay: qc_iu
implemented_extensions:
  - { name: I, version: "2.1" }
  - { name: M, version: "2.0" }
  - { name: Xqci, version: "0.8" }     # Custom extension
  - { name: Xqccmp, version: "0.3" }   # Custom extension
params:
  MXLEN: 32
  PHYS_ADDR_WIDTH: 32
  # ... more params
```

## Benefits

### 1. Deterministic ISA Queries

LLMs can query ISA data specific to a particular CPU/SoC:

```
LLM: "What instructions are available in the qc_iu processor?"
MCP Tool: search_instructions() → Returns only I, M, B, Zca, Zcb, Xqci, Xqccmp instructions
```

### 2. Custom Extensions

Configurations can include vendor-specific extensions:

- `Xqci` - Qualcomm custom instructions
- `Xqccmp` - Qualcomm cache management
- Custom overlays for proprietary features

### 3. Parameter-Specific Behavior

Different configurations have different parameters:

- RV32 vs RV64 (MXLEN: 32 vs 64)
- Physical address widths
- PMP/PMA configuration
- Exception behavior

### 4. Compliance Testing

Use specific configs to verify compliance:

```bash
# Test against RISC-V compliance suite for specific config
RISCV_CPU_CONFIG=mc100-32-riscv-tests python server.py
```

## Troubleshooting

### Error: "Config file not found"

```
ERROR: Config file not found: /path/to/cfgs/myconfig.yaml
```

**Solution**: Check that the config exists in `cfgs/` directory.

### Error: "Ruby generation failed"

This usually means there's an issue with the config YAML or Ruby dependencies.

**Solution**:
1. Check the config YAML is valid
2. Ensure Ruby dependencies are installed: `bundle install`
3. Try generating manually: `rake gen:resolved_arch`

### Generation Times Out

Large configurations (especially with Vector extension) can take time.

**Solution**:
- Be patient (timeout is 5 minutes)
- Check system resources
- Consider pre-generating: `RISCV_CPU_CONFIG=myconfig rake gen:resolved_arch`

## Integration with Claude Code

When used with Claude Code or other MCP clients:

```json
{
  "mcpServers": {
    "riscv-rv64": {
      "command": "python",
      "args": ["/home/afonso/riscv-unified-db/tools/mcp_gen_server/server.py"],
      "env": {
        "RISCV_CPU_CONFIG": "rv64"
      }
    },
    "riscv-qc-iu": {
      "command": "python",
      "args": ["/home/afonso/riscv-unified-db/tools/mcp_gen_server/server.py"],
      "env": {
        "RISCV_CPU_CONFIG": "qc_iu"
      }
    }
  }
}
```

This allows you to query multiple configurations simultaneously!

## Examples

### Query Instructions in QC IU

```bash
RISCV_CPU_CONFIG=qc_iu python server.py
```

Then from MCP client:
```python
search_instructions({"extensions": ["Xqci"]})
# Returns Qualcomm custom instructions
```

### Compare Two Configurations

Run two servers in different terminals:

Terminal 1:
```bash
RISCV_CPU_CONFIG=rv32 python server.py
```

Terminal 2:
```bash
RISCV_CPU_CONFIG=rv64 python server.py
```

LLM can query both to compare RV32 vs RV64 differences!
