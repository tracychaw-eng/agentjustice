"""
Hashing utilities for reproducibility.

Provides functions to hash datasets, prompts, and configurations.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Union

try:
    import xxhash
    USE_XXHASH = True
except ImportError:
    USE_XXHASH = False


def hash_file(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """
    Compute hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, xxhash64)
    
    Returns:
        Hash string prefixed with algorithm name
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if algorithm == "xxhash64" and USE_XXHASH:
        hasher = xxhash.xxh64()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    else:
        hasher = hashlib.sha256()
        algorithm = "sha256"
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    
    return f"{algorithm}:{hasher.hexdigest()}"


def hash_string(content: str, algorithm: str = "sha256") -> str:
    """
    Compute hash of a string.
    
    Args:
        content: String content to hash
        algorithm: Hash algorithm
    
    Returns:
        Hash string prefixed with algorithm name
    """
    if algorithm == "xxhash64" and USE_XXHASH:
        hasher = xxhash.xxh64()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    else:
        hasher = hashlib.sha256()
        algorithm = "sha256"
    
    hasher.update(content.encode("utf-8"))
    return f"{algorithm}:{hasher.hexdigest()}"


def hash_dict(data: Dict[str, Any], algorithm: str = "sha256") -> str:
    """
    Compute hash of a dictionary (serialized to JSON).
    
    Args:
        data: Dictionary to hash
        algorithm: Hash algorithm
    
    Returns:
        Hash string prefixed with algorithm name
    """
    # Sort keys for deterministic serialization
    content = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hash_string(content, algorithm)


def hash_prompt(prompt_template: str, version: str = "v1") -> str:
    """
    Compute hash of a prompt template.
    
    Includes version in hash for tracking prompt evolution.
    
    Args:
        prompt_template: The prompt template string
        version: Prompt version identifier
    
    Returns:
        Hash string
    """
    content = f"version:{version}\n{prompt_template}"
    return hash_string(content, "sha256")


def compute_dataset_hash(dataset_path: Union[str, Path]) -> str:
    """
    Compute hash of the canonical dataset.
    
    Args:
        dataset_path: Path to CSV file
    
    Returns:
        Hash string for manifest
    """
    return hash_file(dataset_path, "sha256")
