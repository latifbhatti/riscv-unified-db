#!/usr/bin/env python3
import sys
import os
import glob
from db_const import *
from itertools import groupby
from operator import itemgetter
import json
import yaml


# Save the current working directory
original_cwd = os.getcwd()

# Change the working directory to the location of parse.py and constants.py
module_path = os.path.abspath(os.path.join('..', 'riscv-opcodes'))
os.chdir(module_path)

# Ensure that the directory containing parse.py is in sys.path
sys.path.append(module_path)

# Now import the parse.py module, which will also import constants.py
from parse import *
from shared_utils import *

# After importing, change back to the original working directory
os.chdir(original_cwd)

def create_inst_dict(file_filter, include_pseudo=False, include_pseudo_ops=[]):
    '''
    This function return a dictionary containing all instructions associated
    with an extension defined by the file_filter input. The file_filter input
    needs to be rv* file name with out the 'rv' prefix i.e. '_i', '32_i', etc.

    Each node of the dictionary will correspond to an instruction which again is
    a dictionary. The dictionary contents of each instruction includes:
        - variables: list of arguments used by the instruction whose mapping
          exists in the arg_lut dictionary
        - encoding: this contains the 32-bit encoding of the instruction where
          '-' is used to represent position of arguments and 1/0 is used to
          reprsent the static encoding of the bits
        - extension: this field contains the rv* filename from which this
          instruction was included
        - match: hex value representing the bits that need to match to detect
          this instruction
        - mask: hex value representin the bits that need to be masked to extract
          the value required for matching.

    In order to build this dictionary, the function does 2 passes over the same
    rv<file_filter> file. The first pass is to extract all standard
    instructions. In this pass, all pseudo ops and imported instructions are
    skipped. For each selected line of the file, we call process_enc_line
    function to create the above mentioned dictionary contents of the
    instruction. Checks are performed in this function to ensure that the same
    instruction is not added twice to the overall dictionary.

    In the second pass, this function parses only pseudo_ops. For each pseudo_op
    this function checks if the dependent extension and instruction, both, exist
    before parsing it. The pseudo op is only added to the overall dictionary if
    the dependent instruction is not present in the dictionary, else it is
    skipped.


    '''
    opcodes_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../riscv-opcodes/extensions')

    instr_dict = {}

    # file_names contains all files to be parsed in the riscv-opcodes directory
    file_names = []
    for fil in file_filter:
        file_names += glob.glob(f'{opcodes_dir}/{fil}')
    file_names.sort(reverse=True)
    # first pass if for standard/regular instructions
    logging.debug('Collecting standard instructions first')
    for f in file_names:
        logging.debug(f'Parsing File: {f} for standard instructions')
        with open(f) as fp:
            lines = (line.rstrip()
                     for line in fp)  # All lines including the blank ones
            lines = list(line for line in lines if line)  # Non-blank lines
            lines = list(
                line for line in lines
                if not line.startswith("#"))  # remove comment lines

        # go through each line of the file
        for line in lines:
            # if the an instruction needs to be imported then go to the
            # respective file and pick the line that has the instruction.
            # The variable 'line' will now point to the new line from the
            # imported file

            # ignore all lines starting with $import and $pseudo
            if '$import' in line or '$pseudo' in line:
                continue
            logging.debug(f'     Processing line: {line}')

            # call process_enc_line to get the data about the current
            # instruction
            (name, single_dict) = process_enc_line(line, f)
            ext_name = os.path.basename(f)

            # if an instruction has already been added to the filtered
            # instruction dictionary throw an error saying the given
            # instruction is already imported and raise SystemExit
            if name in instr_dict:
                var = instr_dict[name]["extension"]
                if same_base_isa(ext_name, var):
                    # disable same names on the same base ISA
                    err_msg = f'instruction : {name} from '
                    err_msg += f'{ext_name} is already '
                    err_msg += f'added from {var} in same base ISA'
                    logging.error(err_msg)
                    raise SystemExit(1)
                elif instr_dict[name]['encoding'] != single_dict['encoding']:
                    # disable same names with different encodings on different base ISAs
                    err_msg = f'instruction : {name} from '
                    err_msg += f'{ext_name} is already '
                    err_msg += f'added from {var} but each have different encodings in different base ISAs'
                    logging.error(err_msg)
                    raise SystemExit(1)
                instr_dict[name]['extension'].extend(single_dict['extension'])
            else:
              for key in instr_dict:
                  item = instr_dict[key]
                  if overlaps(item['encoding'], single_dict['encoding']) and \
                    not extension_overlap_allowed(ext_name, item['extension'][0]) and \
                    not instruction_overlap_allowed(name, key) and \
                    same_base_isa(ext_name, item['extension']):
                      # disable different names with overlapping encodings on the same base ISA
                      err_msg = f'instruction : {name} in extension '
                      err_msg += f'{ext_name} overlaps instruction {key} '
                      err_msg += f'in extension {item["extension"]}'
                      logging.error(err_msg)
                      raise SystemExit(1)

            if name not in instr_dict:
                # update the final dict with the instruction
                instr_dict[name] = single_dict

    # second pass if for pseudo instructions
    logging.debug('Collecting pseudo instructions now')
    for f in file_names:
        logging.debug(f'Parsing File: {f} for pseudo_ops')
        with open(f) as fp:
            lines = (line.rstrip()
                     for line in fp)  # All lines including the blank ones
            lines = list(line for line in lines if line)  # Non-blank lines
            lines = list(
                line for line in lines
                if not line.startswith("#"))  # remove comment lines

        # go through each line of the file
        for line in lines:

            # ignore all lines not starting with $pseudo
            if '$pseudo' not in line:
                continue
            logging.debug(f'     Processing line: {line}')

            # use the regex pseudo_regex from constants.py to find the dependent
            # extension, dependent instruction, the pseudo_op in question and
            # its encoding
            (ext, orig_inst, pseudo_inst, line) = pseudo_regex.findall(line)[0]
            ext_file = f'{opcodes_dir}/{ext}'

            # check if the file of the dependent extension exist. Throw error if
            # it doesn't
            if not os.path.exists(ext_file):
                ext1_file = f'{opcodes_dir}/unratified/{ext}'
                if not os.path.exists(ext1_file):
                    logging.error(f'Pseudo op {pseudo_inst} in {f} depends on {ext} which is not available')
                    raise SystemExit(1)
                else:
                    ext_file = ext1_file

            # check if the dependent instruction exist in the dependent
            # extension. Else throw error.
            found = False
            for oline in open(ext_file):
                if not re.findall(f'^\\s*{orig_inst}\\s+',oline):
                    continue
                else:
                    found = True
                    break
            if not found:
                logging.error(f'Orig instruction {orig_inst} not found in {ext}. Required by pseudo_op {pseudo_inst} present in {f}')
                raise SystemExit(1)


            (name, single_dict) = process_enc_line(pseudo_inst + ' ' + line, f)
            # add the pseudo_op to the dictionary only if the original
            # instruction is not already in the dictionary.
            if orig_inst.replace('.','_') not in instr_dict \
                    or include_pseudo \
                    or name in include_pseudo_ops:

                # update the final dict with the instruction
                if name not in instr_dict:
                    single_dict['original_instruction'] = orig_inst
                    single_dict['original_instruction'] = single_dict['original_instruction'].replace('.','_')
                    instr_dict[name] = single_dict
                    logging.debug(f'        including pseudo_ops:{name}')
                else:
                    if(single_dict['match'] != instr_dict[name]['match']):
                        instr_dict[name + '_pseudo'] = single_dict

                    # if a pseudo instruction has already been added to the filtered
                    # instruction dictionary but the extension is not in the current
                    # list, add it
                    else:
                        ext_name = single_dict['extension']

                    if (ext_name not in instr_dict[name]['extension']) & (name + '_pseudo' not in instr_dict):
                        instr_dict[name]['extension'].extend(ext_name)
            else:
                logging.debug(f'        Skipping pseudo_op {pseudo_inst} since original instruction {orig_inst} already selected in list')

    # third pass if for imported instructions
    logging.debug('Collecting imported instructions')
    for f in file_names:
        logging.debug(f'Parsing File: {f} for imported ops')
        with open(f) as fp:
            lines = (line.rstrip()
                     for line in fp)  # All lines including the blank ones
            lines = list(line for line in lines if line)  # Non-blank lines
            lines = list(
                line for line in lines
                if not line.startswith("#"))  # remove comment lines

        # go through each line of the file
        for line in lines:
            # if the an instruction needs to be imported then go to the
            # respective file and pick the line that has the instruction.
            # The variable 'line' will now point to the new line from the
            # imported file

            # ignore all lines starting with $import and $pseudo
            if '$import' not in line :
                continue
            logging.debug(f'     Processing line: {line}')

            (import_ext, reg_instr) = imported_regex.findall(line)[0]
            import_ext_file = f'{opcodes_dir}/{import_ext}'

            # check if the file of the dependent extension exist. Throw error if
            # it doesn't
            if not os.path.exists(import_ext_file):
                ext1_file = f'{opcodes_dir}/unratified/{import_ext}'
                if not os.path.exists(ext1_file):
                    logging.error(f'Instruction {reg_instr} in {f} cannot be imported from {import_ext}')
                    raise SystemExit(1)
                else:
                    ext_file = ext1_file
            else:
                ext_file = import_ext_file

            # check if the dependent instruction exist in the dependent
            # extension. Else throw error.
            found = False
            for oline in open(ext_file):
                if not re.findall(f'^\\s*{reg_instr}\\s+',oline):
                    continue
                else:
                    found = True
                    break
            if not found:
                logging.error(f'imported instruction {reg_instr} not found in {ext_file}. Required by {line} present in {f}')
                logging.error(f'Note: you cannot import pseudo/imported ops.')
                raise SystemExit(1)

            # call process_enc_line to get the data about the current
            # instruction
            (name, single_dict) = process_enc_line(oline, f)

            # if an instruction has already been added to the filtered
            # instruction dictionary throw an error saying the given
            # instruction is already imported and raise SystemExit
            if name in instr_dict:
                var = instr_dict[name]["extension"]
                if instr_dict[name]['encoding'] != single_dict['encoding']:
                    err_msg = f'imported instruction : {name} in '
                    err_msg += f'{os.path.basename(f)} is already '
                    err_msg += f'added from {var} but each have different encodings for the same instruction'
                    logging.error(err_msg)
                    raise SystemExit(1)
                instr_dict[name]['extension'].extend(single_dict['extension'])
            else:
                # update the final dict with the instruction
                instr_dict[name] = single_dict
    return instr_dict

def load_json_instructions(json_file_path):
    with open(json_file_path, 'r') as json_file:
        json_instr_dict = json.load(json_file)
    return json_instr_dict

def merge_instruction_dicts(dict1, dict2):
    merged_dict = dict1.copy()  # Start with dict1's keys and values
    for key, value in dict2.items():
        if key in merged_dict:
            # Handle duplicate keys if necessary
            pass  # For now, we'll ignore duplicates; you can define your policy here
        else:
            merged_dict[key] = value
    return merged_dict

def report_missing_instructions(missing_in_dict1, missing_in_dict2, file_path):
    with open(file_path, 'w') as file:
        if missing_in_dict1:
            file.write("Instructions missing in the first dictionary:\n")
            for instr in missing_in_dict1:
                file.write(f"  {instr}\n")
        else:
            file.write("No instructions missing in the first dictionary.\n")

        if missing_in_dict2:
            file.write("Instructions missing in the second dictionary:\n")
            for instr in missing_in_dict2:
                file.write(f"  {instr}\n")
        else:
            file.write("No instructions missing in the second dictionary.\n")


def compare_instruction_sets(dict1, dict2):
    set1 = set(dict1.keys())
    set2 = set(dict2.keys())

    missing_in_dict1 = set2 - set1
    missing_in_dict2 = set1 - set2

    return missing_in_dict1, missing_in_dict2


def pop_parent_with_origin_instruction(yaml_content, instr_dict):
    keys_to_pop = []
    for key, value in instr_dict.items():
        if isinstance(value, dict) and 'original_instruction' in value:
            keys_to_pop.append(key)
    
    for key in keys_to_pop:
        key_with_dots = key.replace('_', '.')
        key_with_underscores = key.replace('.', '_')
        
        if key in yaml_content:
            yaml_content.pop(key)
        elif key_with_dots in yaml_content:
            yaml_content.pop(key_with_dots)
        elif key_with_underscores in yaml_content:
            yaml_content.pop(key_with_underscores)
    
    return yaml_content

def combine_imm_fields(imm_fields):
    '''
    Combine multiple immediate fields into a single representation.

    Args:
    imm_fields (list): List of immediate field strings

    Returns:
    str: Combined immediate field representation
    '''
    if not imm_fields:
        return ''
    
    all_bits = set()
    for field in imm_fields:
        if '[' in field and ']' in field:
            range_str = field.split('[')[1].split(']')[0]
            parts = range_str.split('|')
            for part in parts:
                if ':' in part:
                    start, end = map(int, part.split(':'))
                    all_bits.update(range(min(start, end), max(start, end) + 1))
                else:
                    all_bits.add(int(part))
        elif field == 'imm':
            return 'imm'  # If there's a generic 'imm', just return it
    
    if all_bits:
        min_bit, max_bit = min(all_bits), max(all_bits)
        return f'imm[{max_bit}:{min_bit}]'
    else:
        return 'imm'    

def get_variables(instr_data):
    encoding = instr_data['encoding']
    var_fields = instr_data.get('variable_fields', [])
    
    variables = {}
    for field_name in var_fields:
        if field_name in arg_lut:
            start_bit, end_bit = arg_lut[field_name]
            variables[field_name] = {
                'field_name': field_name,
                'match': encoding[31-start_bit:32-end_bit],
                'start_bit': start_bit,
                'end_bit': end_bit
            }
    return variables

def make_pseudo_list(inst_dict):
    '''
    This function goes through the instruction dictionary (inst_dict),
    finds the original instructions and their corresponding pseudoinstructions,
    and prints a list in the format: originalinstruction: pseudoinstruction
    '''
    # Initialize a dictionary to store the relationships
    pseudo_map = {}

    # Iterate through the instruction dictionary
    for original_instr_name, original_instr_data in inst_dict.items():
        original_instruction = original_instr_name
        
        # Iterate again to compare with other instructions
        for instr_name, instr_data in inst_dict.items():
            if 'original_instruction' in instr_data and original_instruction == instr_data['original_instruction']:
                # Add the instruction to the dictionary
                if original_instruction not in pseudo_map:
                    pseudo_map[original_instruction] = []
                pseudo_map[original_instruction].append(instr_name)
    return pseudo_map




def make_yaml(instr_dict, pseudo_map):
    def get_yaml_long_name(instr_name):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        synopsis_file = os.path.join(current_dir, "synopsis")
        
        if os.path.exists(synopsis_file):
            with open(synopsis_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2 and parts[0].lower() == instr_name.lower():
                        return parts[1]
        
        return 'No synopsis available.'

    def get_yaml_description(instr_name):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        desc_file = os.path.join(current_dir, "description")

        if os.path.exists(desc_file):
            with open(desc_file, 'r') as f:
                lines = f.readlines()
                # Skip the first line as it's the header
                for line in lines[1:]:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2 and parts[0].lower() == instr_name.lower():
                        return parts[1]
        
        return "No description available."
        

    def get_yaml_assembly(instr_name, instr_dict):
        instr_data = instr_dict[instr_name]
        var_fields = instr_data.get('variable_fields', [])
        reg_args = []
        imm_args = []

        for field in var_fields:
            mapped_field = variable_mapping.get(field, field)
            if '!=' in mapped_field:
                # Remove '!='
                mapped_field = mapped_field.replace('!=', '')[:-1]

            if ('imm' in field) or ('offset' in field):
                imm_args.append(mapped_field)
            else:
                reg_args.append(mapped_field.replace('rs', 'xs').replace('rd', 'xd'))

        # Combine immediate fields
        combined_imm = combine_imm_fields(imm_args)
    
        # Combine all arguments, registers first then immediates
        all_args = reg_args + (['imm'] if combined_imm else [])
        # Create the assembly string
        assembly = f"{', '.join(all_args)}" if all_args else instr_name

        return assembly

    
    def process_extension(ext):
        parts = ext.split('_')
        if len(parts) == 2:
            return [parts[1].capitalize()]
        elif len(parts) == 3:
            return [parts[1].capitalize(), parts[2].capitalize()]
        else:
            return [ext.capitalize()]  # fallback for unexpected formats
        
    def parse_imm_location(field_name, imm_str):
        parts = imm_str.split('[')[1].split(']')[0].split('|')
        location_parts = []
        start_bit, end_bit = arg_lut[field_name]
        total_bits = start_bit - end_bit + 1
        current_encoding_bit = start_bit

        for part in parts:
            if ':' in part:
                part_start, part_end = map(int, part.split(':'))
                start, end = max(part_start, part_end), min(part_start, part_end)
                for i in range(start, end-1, -1):
                    real_bit = i
                    encoding_bit = current_encoding_bit
                    location_parts.append((real_bit, encoding_bit))
                    current_encoding_bit -= 1
            else:
                real_bit = int(part)
                encoding_bit = current_encoding_bit
                location_parts.append((real_bit, encoding_bit))
                current_encoding_bit -= 1

        # Sort the location_parts by real_bit in descending order
        location_parts.sort(key=lambda x: x[0], reverse=True)
        return location_parts

    def make_yaml_encoding(instr_name, instr_data):
        encoding = instr_data['encoding']
        var_fields = instr_data.get('variable_fields', [])
        match = ''.join([bit if bit != '-' else '-' for bit in encoding])

        variables = []
        imm_locations = []
        for field_name in var_fields:
            # Handle field assignments like 'rs2=rs1'
            if '=' in field_name:
                field_name, assigned_value = field_name.split('=')
                # You may need to handle the assigned_value based on your requirements
                # For example, you might want to enforce that field_name equals assigned_value

            if field_name in variable_mapping:
                mapped_name = variable_mapping[field_name]
                if ('[' in mapped_name and ']' in mapped_name and 
                    (mapped_name.startswith('imm') or mapped_name.startswith('uimm') or mapped_name.startswith('nzimm'))):
                    # This is an immediate field
                    imm_locations.extend(parse_imm_location(field_name, mapped_name))
                else:
                    # This is a regular field
                    start_bit, end_bit = arg_lut.get(field_name, (None, None))
                    if start_bit is not None and end_bit is not None:
                        variables.append({
                            'name': mapped_name,
                            'location': f'{start_bit}-{end_bit}'
                        })
                    else:
                        # Handle missing field_name in arg_lut
                        continue  # Or log an error if necessary
            else:
                # If not in variable_mapping, use the original field name and bit range
                start_bit, end_bit = arg_lut.get(field_name, (None, None))
                if start_bit is not None and end_bit is not None:
                    variables.append({
                        'name': field_name,
                        'location': f'{start_bit}-{end_bit}'
                    })
                else:
                    # Handle missing field_name in arg_lut
                    continue  # Or log an error if necessary

        last_x = 0
        # Add merged immediate field if there are any immediate parts
        if imm_locations:
            # Sort immediate parts by their real bit position (descending order)
            imm_locations.sort(key=lambda x: x[0], reverse=True)
            
            # Merge adjacent ranges based on encoding bits
            merged_parts = []
            current_range = None
            for real_bit, encoding_bit in imm_locations:
                if current_range is None:
                    current_range = [encoding_bit, encoding_bit, real_bit, real_bit]
                elif encoding_bit == current_range[1] - 1:
                    current_range[1] = encoding_bit
                    current_range[3] = real_bit
                else:
                    merged_parts.append(tuple(current_range))
                    current_range = [encoding_bit, encoding_bit, real_bit, real_bit]

            if all(x != 0 for x, y in imm_locations):
                last_x = imm_locations[-1][0]

            if current_range:
                merged_parts.append(tuple(current_range))
            
            # Convert merged parts to string representation
            imm_location = '|'.join([
                f'{start}' if start == end else f'{start}-{end}' 
                for start, end, _, _ in merged_parts
            ])
            imm_variable = {
                'name': 'imm',
                'location': imm_location
            }
            if last_x != 0:
                imm_variable['left_shift'] = last_x
            variables.append(imm_variable)

        # Sort variables in descending order based on the start of the bit range
        variables.sort(
            key=lambda x: int(x['location'].split('-')[0].split('|')[0]), 
            reverse=True
        )

        if "-" not in match:
            match = '"' + match + '"'

        # Handle '!=' in variable names
        for variable in variables:
            if '!=' in variable['name']:
                variable['not'] = variable['name'].split('!=')[1]
                variable['name'] = variable['name'].split('!=')[0]

        result = {
            'match': match,
            'variables': variables
        }

        return result
        
    def get_yaml_encoding_diff(instr_data_original, pseudo_instructions):
            
        original_vars = get_variables(instr_data_original)
        differences = {}

        for pseudo_name, pseudo_data in pseudo_instructions.items():
            pseudo_vars = get_variables(pseudo_data)
            field_differences = {}

            # Find fields that are different or unique to each instruction
            all_fields = set(original_vars.keys()) | set(pseudo_vars.keys())
            for field in all_fields:
                if field not in pseudo_vars:
                    field_differences[field] = {
                        'pseudo_value': pseudo_data['encoding'][31-original_vars[field]['start_bit']:32-original_vars[field]['end_bit']]
                    }
                elif field not in original_vars:
                    field_differences[field] = {
                        'pseudo_value': pseudo_vars[field]['match']
                    }
            if field_differences:
                differences[pseudo_name] = field_differences

        return differences

    def get_yaml_definedby(instr_data):
        defined_by = set()
        has_zb_extension = False

        for ext in instr_data['extension']:
            parts = ext.split('_')
            if len(parts) > 1:
                # Handle cases like 'rv32_d_zicsr'
                for part in parts[1:]:
                    if part.lower().startswith('zb'):
                        has_zb_extension = True
                    defined_by.add(part.capitalize())
            else:
                if ext.lower().startswith('zb'):
                    has_zb_extension = True
                defined_by.add(ext.capitalize())

        # Add 'B' extension if any 'Zb' extensions were found
        if has_zb_extension:
            defined_by.add('B')

        sorted_defined_by = sorted(defined_by)
        if len(sorted_defined_by) == 1:
            return sorted_defined_by[0]
        else:
            extensions_string = f"[{', '.join(sorted_defined_by)}]"
            return {'anyOf': extensions_string}        
            
    def get_yaml_base(instr_data):
        for ext in instr_data['extension']:
            if ext.startswith('rv32'):
                return 32
            elif ext.startswith('rv64'):
                return 64
        return None


    # Group instructions by extension
    extensions = {}
    rv32_instructions = {}
    for instr_name, instr_data in instr_dict.items():
        if instr_name.endswith('_rv32'):
            base_name = instr_name[:-5]
            rv32_instructions[base_name] = instr_name
        else:
            for ext in instr_data['extension']:
                ext_letters = process_extension(ext)
                for ext_letter in ext_letters:
                    if ext_letter not in extensions:
                        extensions[ext_letter] = {}
                    extensions[ext_letter][instr_name] = instr_data


    # Create a directory to store the YAML files
    base_dir = 'yaml_output'
    os.makedirs(base_dir, exist_ok=True)

    def create_pseudo_yaml(pseudo_name, original_name, instr_data, instr_dict, ext_dir):
        inner_content = {
            '$schema': 'inst_schema.json#',
            'kind': 'pseudoinstruction',
            'name': pseudo_name.replace('_', '.'),
            'long_name': get_yaml_long_name(pseudo_name),
            'description': get_yaml_description(pseudo_name),
            'definedBy': get_yaml_definedby(instr_data),
            'assembly': get_yaml_assembly(pseudo_name, instr_dict),
            'origin_instruction': original_name.replace('_', '.'),
            'encoding': make_yaml_encoding(pseudo_name, instr_data),
            'operation': None
        }

        yaml_string = "# yaml-language-server: $schema=../../../schemas/inst_schema.json\n\n"
        yaml_string += yaml.dump(inner_content, default_flow_style=False, sort_keys=False)
        yaml_string = yaml_string.replace("'[", "[").replace("]'","]").replace("'-","-")
        yaml_string = re.sub(r'description: (.+)', lambda m: f'description: |\n      {m.group(1)}', yaml_string)
        yaml_string = re.sub(r'operation: (.+)', lambda m: f'operation(): |\n      {""}', yaml_string)
        yaml_string = yaml_string.replace('"',"")

        # Create pseudo directory if it doesn't exist
        pseudo_dir = os.path.join(ext_dir, 'pseudo')
        os.makedirs(pseudo_dir, exist_ok=True)

        # Write to file
        filename = f'{pseudo_name.replace("_", ".")}.yaml'
        filepath = os.path.join(pseudo_dir, filename)
        with open(filepath, 'w') as outfile:
            outfile.write(yaml_string)

    # Generate and save YAML for each extension
    for ext, ext_dict in extensions.items():
        ext_dir = os.path.join(base_dir, ext)
        os.makedirs(ext_dir, exist_ok=True)
    
        for instr_name, instr_data in ext_dict.items():
            # Create the new nested structure
            inner_content = {
                '$schema': 'inst_schema.json#',
                'kind': 'instruction',
                'name': instr_name.replace('_', '.'),
                'long_name': get_yaml_long_name(instr_name),
                'description': get_yaml_description(instr_name),
                'definedBy': get_yaml_definedby(instr_data),
                'assembly': get_yaml_assembly(instr_name, instr_dict),
                'encoding': make_yaml_encoding(instr_name, instr_data),
                'access': {
                    's': 'always',
                    'u': 'always',
                    'vs': 'always',
                    'vu': 'always'
                },
                'data_independent_timing': 'false'
            }

            # Add base if it exists
            base = get_yaml_base(instr_data)
            if base is not None and not (instr_name in rv32_instructions):
                inner_content['base'] = base

            if instr_name in pseudo_map and not any('_rv' in pseudo for pseudo in pseudo_map[instr_name]):
                for pseudo in pseudo_map[instr_name]:
                    pseudo_data = instr_dict[pseudo.replace('.', '_')]
                    create_pseudo_yaml(pseudo, instr_name, pseudo_data, instr_dict, ext_dir)

            if 'original_instruction' in instr_data and not instr_name.endswith('_rv32'):
                continue

            if instr_name in pseudo_map and not any('_rv' in pseudo for pseudo in pseudo_map[instr_name]):
                inner_content['pseudoinstructions'] = []
                pseudo_instructions = {pseudo.replace('.', '_'): instr_dict[pseudo.replace('.', '_')] 
                                    for pseudo in pseudo_map[instr_name]}
                encoding_diffs = get_yaml_encoding_diff(instr_data, pseudo_instructions)

                for pseudo in pseudo_map[instr_name]:
                    assembly = get_yaml_assembly(pseudo.replace('.', '_'), instr_dict)
                    diff_info = encoding_diffs.get(pseudo.replace('.', '_'), {})
                    when_condition = get_yaml_assembly(instr_name, instr_dict).replace(assembly, "").replace(",", "")

                    if diff_info:
                        diff_str_list = []
                        for field, details in diff_info.items():
                            pseudo_value = details['pseudo_value']
                            if all(c in '01' for c in pseudo_value):
                                diff_str_list.append(f"({field} == {hex(int(pseudo_value, 2))})")
                            else:
                                diff_str_list.append(f"({field} == {pseudo_value})")
                        when_condition = " && ".join(diff_str_list)

                    inner_content['pseudoinstructions'].append({
                        'when': when_condition,
                        'to': f"{pseudo.replace('_','.')}",
                    })

            # Handle encoding for RV32 and RV64 versions
            if instr_name in rv32_instructions:
                inner_content['encoding'] = {
                    'RV32': make_yaml_encoding(rv32_instructions[instr_name], instr_dict[rv32_instructions[instr_name]]),
                    'RV64': make_yaml_encoding(instr_name, instr_data)
                }

            # Add operation field last
            inner_content['operation'] = None

            # Generate YAML string
            yaml_string = "# yaml-language-server: $schema=../../../schemas/inst_schema.json\n\n"
            yaml_string += yaml.dump(inner_content, default_flow_style=False, sort_keys=False)
            yaml_string = yaml_string.replace("'[", "[").replace("]'","]").replace("'-","-").replace("0'","0").replace("1'","1").replace("-'","-")
            yaml_string = re.sub(r'description: (.+)', lambda m: f'description: |\n      {m.group(1)}', yaml_string)
            yaml_string = re.sub(r'operation: (.+)', lambda m: f'operation(): |\n      {""}', yaml_string)
            yaml_string = yaml_string.replace('"',"")
            yaml_string = yaml_string.replace("'false'","false")
            yaml_string = re.sub(r"not: '(\d+)", r"not: \1", yaml_string)

            # Write to file
            filename = f'{instr_name.replace("_", ".")}.yaml'
            filepath = os.path.join(ext_dir, filename)
            with open(filepath, 'w') as outfile:
                outfile.write(yaml_string)

    print("Summary of all extensions saved as yaml_output/extensions_summary.yaml")


if __name__ == "__main__":
    print(f'Running with args : {sys.argv}')

    extensions = sys.argv[1:]
    for i in ['-c','-latex','-chisel','-sverilog','-rust', '-go', '-spinalhdl','-asciidoc', '-yaml']:
        if i in extensions:
            extensions.remove(i)
    print(f'Extensions selected : {extensions}')
    
    instr_dict = create_inst_dict(extensions, include_pseudo=True)
    
    # Load JSON instructions
    json_file_path = '../riscv-opcodes/instr_dict.json'  # Path to your JSON file
    json_instr_dict = load_json_instructions(json_file_path)
    
    # Compare instruction sets
    missing_in_instr_dict, missing_in_json = compare_instruction_sets(json_instr_dict, instr_dict)
    report_missing_instructions(missing_in_instr_dict, missing_in_json, 'missing_instructions.txt')
    
    # Merge instruction dictionaries
    merged_instr_dict = merge_instruction_dicts(instr_dict, json_instr_dict)
    
    pseudo_map = make_pseudo_list(merged_instr_dict)
    make_yaml(merged_instr_dict, pseudo_map)
    logging.info('YAML files generated successfully')
