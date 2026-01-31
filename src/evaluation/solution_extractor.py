"""Extract and parse solution files from BIRD-CRITIC solution archives."""

import os
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


def extract_solution_zip(zip_path: str, extract_to: Optional[str] = None) -> str:
    """Extract solution zip file to a directory.
    
    Args:
        zip_path: Path to the solution zip file (e.g., pg_sol.zip)
        extract_to: Directory to extract to. If None, extracts to same directory as zip.
    
    Returns:
        Path to the extracted directory.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"Solution zip file not found: {zip_path}")
    
    if extract_to is None:
        extract_to = zip_path.parent / zip_path.stem
    else:
        extract_to = Path(extract_to)
    
    extract_to.mkdir(parents=True, exist_ok=True)
    
    # Extract with proper encoding handling
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Use extractall with proper encoding handling
            # zipfile handles encoding internally, but we'll extract manually if needed
            zip_ref.extractall(extract_to)
    except (UnicodeDecodeError, UnicodeError) as e:
        # If extractall fails due to encoding, extract manually
        print(f"Warning: Encoding issue during zip extraction, trying manual extraction: {e}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Handle encoding in member names
                try:
                    # Try to get the member info
                    member_info = zip_ref.getinfo(member)
                    # Extract to a safe filename
                    safe_name = member.encode('cp437').decode('utf-8', errors='replace')
                    target_path = extract_to / safe_name
                except (UnicodeDecodeError, UnicodeError):
                    # Use original name if encoding fails
                    target_path = extract_to / member
                
                if member.endswith('/'):
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zip_ref.open(member) as source:
                        with open(target_path, 'wb') as target:
                            target.write(source.read())
    
    return str(extract_to)


def load_solution_jsonl(jsonl_path: str) -> List[Dict]:
    """Load solution data from a JSONL file.
    
    Args:
        jsonl_path: Path to the JSONL file containing solutions.
    
    Returns:
        List of solution dictionaries.
    """
    solutions = []
    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            with open(jsonl_path, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    solutions.append(json.loads(line))
            return solutions
        except (UnicodeDecodeError, UnicodeError):
            continue
        except json.JSONDecodeError as e:
            # If we got past encoding but JSON fails, that's a different issue
            raise ValueError(f"JSON decode error in {jsonl_path}: {e}")
    
    # If all encodings failed, try reading as binary and decoding
    try:
        with open(jsonl_path, 'rb') as f:
            content = f.read()
            # Try to decode with error handling
            text = content.decode('utf-8', errors='replace')
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                solutions.append(json.loads(line))
        return solutions
    except Exception as e:
        raise ValueError(f"Failed to read {jsonl_path} with any encoding: {e}")


def find_solution_files(extracted_dir: str) -> List[str]:
    """Find all JSONL solution files in the extracted directory.
    
    Skips macOS metadata (e.g. __MACOSX, ._*) which are not real JSONL.
    
    Args:
        extracted_dir: Directory containing extracted solution files.
    
    Returns:
        List of paths to JSONL solution files.
    """
    solution_files = []
    extracted_path = Path(extracted_dir)
    
    for jsonl_file in extracted_path.rglob("*.jsonl"):
        path_str = str(jsonl_file)
        # Skip macOS zip metadata: __MACOSX dir and ._* resource-forks
        if "__MACOSX" in path_str or jsonl_file.name.startswith("._"):
            continue
        solution_files.append(path_str)
    
    return solution_files


def load_all_solutions(solution_dir: str) -> Dict[str, Dict]:
    """Load all solutions from a solution directory and index by instance_id.
    
    Args:
        solution_dir: Directory containing solution JSONL files or path to zip file.
    
    Returns:
        Dictionary mapping instance_id to solution data.
    """
    solution_dir = Path(solution_dir)
    
    # If it's a zip file, extract it first
    if solution_dir.suffix == '.zip':
        solution_dir = Path(extract_solution_zip(str(solution_dir)))
    elif not solution_dir.exists():
        raise FileNotFoundError(f"Solution directory/zip not found: {solution_dir}")
    
    # Find all JSONL files
    jsonl_files = find_solution_files(str(solution_dir))
    
    if not jsonl_files:
        raise ValueError(f"No JSONL solution files found in {solution_dir}")
    
    # Load all solutions and index by instance_id
    solutions_by_id = {}
    for jsonl_file in jsonl_files:
        try:
            print(f"Loading solutions from: {jsonl_file}")
            solutions = load_solution_jsonl(jsonl_file)
            print(f"  Loaded {len(solutions)} solutions from this file")
            for solution in solutions:
                instance_id = solution.get("instance_id")
                if instance_id:
                    solutions_by_id[instance_id] = solution
        except Exception as e:
            print(f"Warning: Failed to load {jsonl_file}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return solutions_by_id


def merge_solutions_with_dataset(
    dataset: List[Dict],
    solutions: Dict[str, Dict],
    solution_fields: Optional[List[str]] = None
) -> List[Dict]:
    """Merge solution data into dataset instances.
    
    Args:
        dataset: List of dataset instances.
        solutions: Dictionary mapping instance_id to solution data.
        solution_fields: List of fields to merge from solutions. If None, merges all.
    
    Returns:
        List of merged dataset instances.
    """
    if solution_fields is None:
        solution_fields = ["sol_sql", "test_cases", "preprocess_sql", "clean_up_sql"]
    
    merged = []
    missing_solutions = []
    
    for instance in dataset:
        instance_id = instance.get("instance_id")
        if not instance_id:
            continue
        
        if instance_id in solutions:
            solution = solutions[instance_id]
            # Merge solution fields into instance
            for field in solution_fields:
                if field in solution:
                    instance[field] = solution[field]
            merged.append(instance)
        else:
            missing_solutions.append(instance_id)
    
    if missing_solutions:
        print(f"Warning: {len(missing_solutions)} instances missing solutions")
    
    return merged
