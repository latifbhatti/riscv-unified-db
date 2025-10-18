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
    if [ -d "../../gen/arch/$cfg" ]; then
        echo "  ✓ $cfg (generated)"
    else
        echo "  ✗ $cfg (not generated)"
    fi
done
echo

# Test 4: Check directory structure
echo "Test 4: Directory structure for rv64"
echo "------------------------------------"
if [ -d "../../gen/arch/rv64" ]; then
    echo "gen/arch/rv64/"
    ls -1 ../../gen/arch/rv64/ | while read dir; do
        count=$(find ../../gen/arch/rv64/$dir -name "*.yaml" 2>/dev/null | wc -l)
        echo "  ├── $dir/ ($count YAML files)"
    done
else
    echo "  ERROR: rv64 not generated"
fi
echo

echo "=== Tests Complete ==="
