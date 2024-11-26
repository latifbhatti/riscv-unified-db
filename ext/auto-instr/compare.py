import os
from pathlib import Path
from collections import defaultdict

def normalize_path(path_str: str) -> Path:
    """
    Normalizes a path string to an absolute Path object.
    Handles relative paths and user home directory.
    
    Args:
        path_str: Input path as string
        
    Returns:
        Path object with absolute path
    """
    # Expand user home directory if present (~/...)
    path_str = os.path.expanduser(path_str)
    
    # Convert to absolute path if relative
    if not os.path.isabs(path_str):
        path_str = os.path.abspath(path_str)
    
    return Path(path_str)

def analyze_directories(dir1_path: str, dir2_path: str) -> tuple[set, set]:
    """
    Recursively analyzes two directories and finds files present in one but missing in the other.
    Only considers filenames for matching, ignoring paths.
    
    Args:
        dir1_path: Path to first directory
        dir2_path: Path to second directory
        
    Returns:
        tuple containing:
        - set of filenames present in dir1 but missing in dir2
        - set of filenames present in dir2 but missing in dir1
    """
    # Convert and normalize paths
    dir1 = normalize_path(dir1_path)
    dir2 = normalize_path(dir2_path)
    
    # Verify directories exist
    if not dir1.is_dir():
        raise ValueError(f"Directory not found: {dir1}\nMake sure the directory exists and the path is correct.")
    if not dir2.is_dir():
        raise ValueError(f"Directory not found: {dir2}\nMake sure the directory exists and the path is correct.")
    
    # Get all files recursively from both directories
    files1 = set()
    files2 = set()
    
    # Walk through first directory
    for root, _, files in os.walk(dir1):
        for file in files:
            files1.add(file)
            
    # Walk through second directory
    for root, _, files in os.walk(dir2):
        for file in files:
            files2.add(file)
    
    # Find differences
    only_in_dir1 = files1 - files2
    only_in_dir2 = files2 - files1
    
    return only_in_dir1, only_in_dir2

def main():
    """
    Main function to run the directory comparison.
    """
    # Set your directory paths here
    dir1_path = "yaml_output"        # Change this to your first directory path
    dir2_path = "../../../derek/riscv-unified-db/arch/inst"    # Change this to your second directory path
    
    try:
        missing_from_dir2, missing_from_dir1 = analyze_directories(dir1_path, dir2_path)
        
        # Print results
        print(f"\nAnalyzing directories:")
        print(f"1: {normalize_path(dir1_path)}")
        print(f"2: {normalize_path(dir2_path)}")
        
        print("\nFiles present in first directory but missing in second:")
        if missing_from_dir2:
            for file in sorted(missing_from_dir2):
                print(f"- {file}")
        else:
            print("None")
            
        print("\nFiles present in second directory but missing in first:")
        if missing_from_dir1:
            for file in sorted(missing_from_dir1):
                print(f"- {file}")
        else:
            print("None")
            
        # Print summary
        print(f"\nSummary:")
        print(f"Files only in first directory: {len(missing_from_dir2)}")
        print(f"Files only in second directory: {len(missing_from_dir1)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()