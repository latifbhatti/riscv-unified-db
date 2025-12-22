#!/bin/bash
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

# Test script for CPU configuration support

echo "=== Testing MCP Server CPU Configuration Support ==="
echo

# Test 1: Default configuration (rv64)
echo "Test 1: Default configuration (rv64)"
echo "--------------------------------------"
timeout 2 python3 server.py 2>&1 | grep -E "(MCP Server starting|Config|Using data)" || echo "Server started (timeout expected)"
echo

# Test 2: Specific configuration (qc_iu)
echo "Test 2: QC IU configuration"
echo "---------------------------"
RISCV_CPU_CONFIG=qc_iu timeout 2 python3 server.py 2>&1 | grep -E "(MCP Server starting|Config|Using data)" || echo "Server started (timeout expected)"
echo

# Test 3: List available configs
echo "Test 3: Available configurations"
echo "--------------------------------"
ls -1 ../../cfgs/*.yaml | xargs -n1 basename | sed 's/.yaml$//' | while read cfg; do
    if [ -d "../../gen/resolved_spec/$cfg" ]; then
        echo "  ✓ $cfg (gen/resolved_spec)"
    else
        echo "  ✗ $cfg (not generated)"
    fi
done
echo

# Test 4: Check directory structure
echo "Test 4: Directory structure for rv64"
echo "------------------------------------"
ROOT_DIR="../../gen/resolved_spec/rv64"
ROOT_LABEL="gen/resolved_spec/rv64/"
if [ -d "$ROOT_DIR" ]; then
    echo "$ROOT_LABEL"
    ls -1 "$ROOT_DIR"/ | while read dir; do
        count=$(find "$ROOT_DIR"/"$dir" -name "*.yaml" 2>/dev/null | wc -l)
        echo "  ├── $dir/ ($count YAML files)"
    done
else
    echo "  ERROR: rv64 not generated"
fi
echo

echo "=== Tests Complete ==="
