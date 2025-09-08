# Bug Reproduction: Partially Configured Systems Crash

## Successfully Reproduced on origin/main

### Environment
- Branch: origin/main (commit 292b34f2)
- No code modifications, pure origin/main state

### Steps to Reproduce

1. Created a partially configured test configuration:

```yaml
# cfgs/test_partial_bug.yaml
---
$schema: config_schema.json#
kind: architecture configuration
type: partially configured  # <-- KEY: This is partially configured
name: test_partial_bug
description: |
  A test partially configured system to reproduce the implemented_functions bug
  on origin/main branch without the fix.

params:
  MXLEN: 32

mandatory_extensions:
  - name: "I"
    version: ">= 2.1"
  - name: "Zicsr"
    version: ">= 2.0"
  - name: "M"
    version: ">= 2.0"
```

2. Executed the HTML generation command:
```bash
./do gen:html[test_partial_bug]
```

### Result: CRASH

```
/home/afonsoo/riscv-unified-db/tools/ruby-gems/udb/lib/udb/cfg_arch.rb:977:in `transitive_implemented_instructions': 
transitive_implemented_instructions is only defined for fully configured systems (ArgumentError)
```

### Root Cause

The error occurs in `backends/cfg_html_doc/adoc_gen.rake:34` which directly calls:
```ruby
cfg_arch.transitive_implemented_instructions
```

This method explicitly checks and raises an error for non-fully configured systems:
```ruby
def transitive_implemented_instructions
  unless @config.fully_configured?
    raise ArgumentError, "transitive_implemented_instructions is only defined for fully configured systems"
  end
  # ...
end
```

### The Problem

1. **Backend assumes fully configured**: The HTML documentation generator backend doesn't check configuration type
2. **Methods are config-type specific**: Methods like `transitive_implemented_instructions` only work for fully configured systems
3. **No fallback**: There's no graceful degradation for partially configured systems

### What the Fix Addresses

The fix in commit a4711afc adds:

1. **Guard clauses**: Check `fully_configured?` before calling restricted methods
2. **Appropriate fallbacks**: Use `not_prohibited_instructions` for partial configs, `possible_instructions` for unconfigured
3. **Function safety**: `implemented_functions` returns empty array instead of crashing
4. **Backend compatibility**: PRM backend checks config type and uses appropriate methods

### Impact Without Fix

- Cannot generate documentation for partially configured systems
- Cannot use partially configured systems during development
- Blocks iterative design and configuration refinement

### Verification

This bug is 100% reproducible on origin/main with any partially configured system.
The fix allows the same command to complete successfully.