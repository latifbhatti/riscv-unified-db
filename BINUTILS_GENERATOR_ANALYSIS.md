# Binutils Generator Analysis & Implementation Guide

## Overview
Analysis of binutils-gdb codebase to understand how to create a UDB→Binutils generator for RISC-V opcodes.

## Key Files Analyzed
- `backends/generators/binutils-gdb/opcodes/riscv-opc.c` - Main opcode table
- `backends/generators/binutils-gdb/opcodes/riscv-dis.c` - Operand format definitions  
- `backends/generators/binutils-gdb/include/opcode/riscv.h` - Structure definitions
- `backends/generators/binutils-gdb/include/opcode/riscv-opc.h` - MATCH/MASK macros

## Binutils Structure Discovered

### 1. Opcode Table Format (riscv-opc.c)
```c
const struct riscv_opcode riscv_opcodes[] = {
  /* name, xlen, insn_class, operands, match, mask, match_func, pinfo */
  {"add", 0, INSN_CLASS_I, "d,s,t", MATCH_ADD, MASK_ADD, match_opcode, 0},
  {"c.add", 0, INSN_CLASS_ZCA, "d,CV", MATCH_C_ADD, MASK_C_ADD, match_c_add, 0},
  // ...
};
```

### 2. MATCH/MASK Definitions (riscv-opc.h)
```c
#define MATCH_ADD 0x33
#define MASK_ADD  0xfe00707f
#define MATCH_C_ADD 0x9002
#define MASK_C_ADD  0xf003
```

### 3. Complete Operand Format System

#### Deterministic 3-Layer Mapping:
1. **Format Character** (`'d'`, `'Cs'`, etc.) 
2. **Field Name** (`RD`, `CRS1S`, etc.)
3. **Bit Position + Size** (shift=7, mask=0x1f)

#### Standard Operands:
- `d` = Destination register (RD, bits 11-7)
- `s` = Source register 1 (RS1, bits 19-15)  
- `t` = Source register 2 (RS2, bits 24-20)
- `j` = Jump immediate
- `o` = Offset immediate

#### Compressed Operands (C prefix):
- `Cs` = Compressed source x8-x15 (CRS1S, bits 9-7 + 8)
- `Ct` = Compressed source x8-x15 (CRS2S, bits 4-2 + 8)
- `CV` = Compressed source full range (CRS2, bits 6-2)
- `Cc` = Stack pointer constraint
- `CD` = Compressed float dest x8-x15
- `CT` = Compressed float source
- `Ck` = Load word immediate offset
- `Cl` = Load doubleword immediate offset  
- `CM` = Store word SP immediate offset
- `CN` = Store doubleword SP immediate offset

#### Vector Operands (V prefix):
- `Vd` = Vector destination (VD, bits 11-7)
- `Vs` = Vector source 1 (VS1, bits 19-15)
- `Vt` = Vector source 2 (VS2, bits 24-20)

#### Float Operands:
- `D` = Float destination
- `S` = Float source 1  
- `T` = Float source 2

## Extension Mapping Challenges

### Simple Mappings:
- UDB `definedBy: I` → Binutils `INSN_CLASS_I` ✅
- UDB `definedBy: M` → Binutils `INSN_CLASS_M` ✅

### Complex Mappings:
- UDB `anyOf: [C, Zca]` → Binutils `INSN_CLASS_ZCA` (prefers specific)
- UDB `anyOf: [M, Zmmul]` → Binutils `INSN_CLASS_ZMMUL` (prefers minimal)
- UDB `allOf: [D, Zfh]` → Binutils `INSN_CLASS_ZFHMIN_AND_D_INX`
- UDB `allOf: [Zbb, not: Zbkb]` → Binutils `INSN_CLASS_ZBB_OR_ZBKB` (complex logic)

### Binutils Extension Classes:
```c
INSN_CLASS_I, INSN_CLASS_M, INSN_CLASS_A, INSN_CLASS_F, INSN_CLASS_D,
INSN_CLASS_ZCA, INSN_CLASS_ZBA, INSN_CLASS_ZBB, INSN_CLASS_ZMMUL,
INSN_CLASS_ZBB_OR_ZBKB, INSN_CLASS_D_AND_ZFA, INSN_CLASS_ZFHMIN_AND_D_INX,
// ... many more
```

## Implementation Strategy

### Phase 1: Operand Mapping Engine

1. **Extract Binutils Operand Definitions**:
   ```python
   # From riscv-dis.c analysis
   OPERAND_MAP = {
       # Standard
       'd': {'field': 'RD', 'bits': '11-7', 'type': 'gpr'},
       's': {'field': 'RS1', 'bits': '19-15', 'type': 'gpr'},  
       't': {'field': 'RS2', 'bits': '24-20', 'type': 'gpr'},
       
       # Compressed  
       'Cs': {'field': 'CRS1S', 'bits': '9-7', 'type': 'gpr', 'range': 'x8-x15'},
       'Ct': {'field': 'CRS2S', 'bits': '4-2', 'type': 'gpr', 'range': 'x8-x15'},
       'CV': {'field': 'CRS2', 'bits': '6-2', 'type': 'gpr'},
       'Cc': {'constraint': 'sp'},
       
       # Float
       'D': {'field': 'RD', 'bits': '11-7', 'type': 'fpr'},
       'S': {'field': 'RS1', 'bits': '19-15', 'type': 'fpr'},
       'T': {'field': 'RS2', 'bits': '24-20', 'type': 'fpr'},
       
       # Vector  
       'Vd': {'field': 'VD', 'bits': '11-7', 'type': 'vpr'},
       'Vs': {'field': 'VS1', 'bits': '19-15', 'type': 'vpr'},
       'Vt': {'field': 'VS2', 'bits': '24-20', 'type': 'vpr'},
   }
   ```

2. **Parse UDB Assembly → Operand List**:
   ```python
   def parse_udb_assembly(assembly_str):
       # "xd, xs1, xs2" → [('xd', 'dest'), ('xs1', 'src1'), ('xs2', 'src2')]
       # "fd, fs1, rm" → [('fd', 'dest'), ('fs1', 'src1'), ('rm', 'rounding')]
       # "fs2, imm(sp)" → [('fs2', 'src'), ('imm', 'offset'), ('sp', 'base')]
   ```

3. **Map UDB Variables → Binutils Format**:
   ```python
   def map_operands(udb_variables, udb_assembly):
       # Extract bit positions from UDB encoding.variables
       # Match with binutils operand definitions by bit position
       # Generate format string like "d,s,t" or "CT,CN(Cc)"
   ```

### Phase 2: Extension Mapping

1. **Build Extension Mapping Table**:
   ```python
   EXTENSION_MAP = {
       'I': 'INSN_CLASS_I',
       'M': 'INSN_CLASS_M', 
       # Handle complex cases
       ('anyOf', ['C', 'Zca']): 'INSN_CLASS_ZCA',  # Prefer specific
       ('anyOf', ['M', 'Zmmul']): 'INSN_CLASS_ZMMUL',  # Prefer minimal
       ('allOf', ['D', 'Zfh']): 'INSN_CLASS_ZFHMIN_AND_D_INX',
   }
   ```

2. **Parse UDB Extension Logic**:
   ```python
   def map_extension(udb_defined_by):
       # Handle simple string: "I" → "INSN_CLASS_I"
       # Handle anyOf: choose most specific extension
       # Handle allOf: look up combined class or default to first
       # Handle not: cases - manual mapping needed
   ```

### Phase 3: Code Generation  

1. **Generate MATCH/MASK Values**:
   ```python
   def generate_match_mask(udb_match_string):
       # "0000000----------000-----0110011" 
       # → MATCH: 0x33, MASK: 0xfe00707f
       match = 0
       mask = 0
       for i, bit in enumerate(udb_match_string):
           if bit == '0':
               mask |= (1 << (31-i))  # Fixed 0 bit
           elif bit == '1': 
               match |= (1 << (31-i)) # Fixed 1 bit
               mask |= (1 << (31-i))
           # '-' = variable bit, no mask
       return match, mask
   ```

2. **Generate Binutils Files**:
   ```python
   def generate_binutils_files(instructions):
       # Generate riscv-opc.h with MATCH/MASK defines
       # Generate riscv-opc.c with opcode table entries
       # Handle instruction variants and aliases
   ```

## Expected Success Rates

- **Basic R/I/S/U/J instructions**: 95%+ (deterministic mapping)
- **Float instructions**: 90%+ (systematic D/S/T mapping)
- **Compressed instructions**: 85%+ (well-defined C* formats)  
- **Vector instructions**: 80%+ (V* prefix system)
- **Complex extensions**: 70% (anyOf/allOf work, not: needs manual handling)

## Key Implementation Files

1. `backends/generators/binutils/binutils_generator.py` - Main generator
2. `backends/generators/binutils/operand_mapper.py` - Operand format mapping
3. `backends/generators/binutils/extension_mapper.py` - Extension class mapping
4. `backends/generators/binutils/code_generator.py` - File output generation

## Testing Strategy

1. Start with basic extensions (I, M, A) 
2. Compare generated MATCH/MASK values with binutils originals
3. Verify operand format strings produce correct assembly
4. Test with binutils assembler/disassembler for validation
5. Gradually expand to more complex extensions

## Conclusion

The binutils operand system is completely deterministic and well-documented. By building the proper mapping tables and parsing logic, we can achieve very high success rates for automatic UDB→Binutils conversion, handling the vast majority of RISC-V instructions without manual intervention.