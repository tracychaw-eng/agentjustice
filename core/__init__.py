"""Core module for AgentBeats."""
from .types import (
    Task,
    JudgeOutput,
    HybridScore,
    TaskTrace,
    JudgeCall,
    RunManifest,
    AdversarialItem,
    ParsedValue,
    CriteriaMatch,
)
from .env import (
    EvaluationEnvironment,
    load_canonical_dataset,
    load_adversarial_dataset,
)
from .hashing import (
    hash_file,
    hash_string,
    hash_dict,
    hash_prompt,
    compute_dataset_hash,
)

__all__ = [
    # Types
    "Task",
    "JudgeOutput",
    "HybridScore",
    "TaskTrace",
    "JudgeCall",
    "RunManifest",
    "AdversarialItem",
    "ParsedValue",
    "CriteriaMatch",
    # Environment
    "EvaluationEnvironment",
    "load_canonical_dataset",
    "load_adversarial_dataset",
    # Hashing
    "hash_file",
    "hash_string",
    "hash_dict",
    "hash_prompt",
    "compute_dataset_hash",
]
