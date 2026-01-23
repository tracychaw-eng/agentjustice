"""
Core type definitions for AgentBeats Phase-1.

Defines dataclasses for tasks, judge outputs, and hybrid scores.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass
class Task:
    """
    A single evaluation task from the dataset.
    
    Preserves all metadata including difficulty for analysis.
    """
    task_id: int
    question: str
    gold_answer: str
    rubric: List[Dict[str, str]]
    question_type: str
    expert_time_mins: float
    difficulty_level: str  # Easy, Medium, Hard
    source: str = "canonical"  # "canonical" or "adversarial"
    
    # For adversarial tasks
    parent_id: Optional[int] = None
    transformation_type: Optional[str] = None
    expected_outcome: Optional[str] = None
    candidate_answer: Optional[str] = None  # Pre-set answer for adversarial
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "question": self.question,
            "gold_answer": self.gold_answer,
            "rubric": self.rubric,
            "question_type": self.question_type,
            "expert_time_mins": self.expert_time_mins,
            "difficulty_level": self.difficulty_level,
            "source": self.source,
            "parent_id": self.parent_id,
            "transformation_type": self.transformation_type,
            "expected_outcome": self.expected_outcome,
            "candidate_answer": self.candidate_answer,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(**data)


@dataclass
class ParsedValue:
    """A parsed numeric value from an answer."""
    value: float
    unit: Optional[str] = None
    context: Optional[str] = None
    original_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "context": self.context,
            "original_text": self.original_text,
        }


@dataclass
class CriteriaMatch:
    """Result of checking a single rubric criteria."""
    criteria: str
    matched: bool
    confidence: float
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria": self.criteria,
            "matched": self.matched,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass
class JudgeOutput:
    """
    Structured output from a judge tool.

    All judges return this format for uniform processing.
    """
    judge_name: str
    judge_version: str
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reason: str
    raw_output: Dict[str, Any]
    latency_ms: float
    prompt_hash: str
    judge_ok: bool = True  # False if judge call failed (network, timeout, parse error)

    # Optional judge-specific fields
    criteria_matches: List[CriteriaMatch] = field(default_factory=list)
    parsed_model_values: List[ParsedValue] = field(default_factory=list)
    parsed_gold_values: List[ParsedValue] = field(default_factory=list)
    tolerance_used: Optional[float] = None
    diff_ratio: Optional[float] = None
    violated: Optional[bool] = None  # For contradiction judge - None means unknown/error
    contradiction_details: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None  # For numeric judge: extraction_failed | alignment_failed | tolerance_failed | none
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge_name": self.judge_name,
            "judge_version": self.judge_version,
            "score": self.score,
            "confidence": self.confidence,
            "reason": self.reason,
            "raw_output": self.raw_output,
            "latency_ms": self.latency_ms,
            "prompt_hash": self.prompt_hash,
            "judge_ok": self.judge_ok,
            "criteria_matches": [c.to_dict() for c in self.criteria_matches],
            "parsed_model_values": [v.to_dict() for v in self.parsed_model_values],
            "parsed_gold_values": [v.to_dict() for v in self.parsed_gold_values],
            "tolerance_used": self.tolerance_used,
            "diff_ratio": self.diff_ratio,
            "violated": self.violated,
            "contradiction_details": self.contradiction_details,
            "failure_reason": self.failure_reason,
        }


@dataclass
class HybridScore:
    """
    Final hybrid score computed from multiple judges.
    
    Includes consistency checks and penalty breakdown.
    """
    exact_match: bool
    semantic_score: float
    numeric_score: float
    contradiction_violated: bool
    consistency_penalty: float
    contradiction_penalty: float
    hedging_penalty: float
    final_score: float
    confidence: float
    consistency_flags: List[str] = field(default_factory=list)
    error_taxonomy: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exact_match": self.exact_match,
            "semantic_score": self.semantic_score,
            "numeric_score": self.numeric_score,
            "contradiction_violated": self.contradiction_violated,
            "consistency_penalty": self.consistency_penalty,
            "contradiction_penalty": self.contradiction_penalty,
            "hedging_penalty": self.hedging_penalty,
            "final_score": self.final_score,
            "confidence": self.confidence,
            "consistency_flags": self.consistency_flags,
            "error_taxonomy": self.error_taxonomy,
        }


@dataclass
class JudgeCall:
    """Record of a single judge tool invocation."""
    judge: str
    input_payload: Dict[str, Any]
    output_payload: Dict[str, Any]
    latency_ms: float
    judge_version: str
    prompt_hash: str
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge": self.judge,
            "input_payload": self.input_payload,
            "output_payload": self.output_payload,
            "latency_ms": self.latency_ms,
            "judge_version": self.judge_version,
            "prompt_hash": self.prompt_hash,
            "error": self.error,
        }


@dataclass
class TaskTrace:
    """
    Complete audit trace for a single task evaluation.
    
    Contains all information needed for replay and inspection.
    """
    timestamp: str
    task_id: int
    difficulty_level: str
    question_type: str
    expert_time_mins: float
    question: str
    gold_answer: str
    rubric: List[Dict[str, str]]
    model_answer: str
    judge_calls: List[JudgeCall]
    intermediate_signals: Dict[str, Any]
    hybrid_score: HybridScore
    error_taxonomy: List[str]
    source: str = "canonical"
    
    # For adversarial
    transformation_type: Optional[str] = None
    expected_outcome: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "difficulty_level": self.difficulty_level,
            "question_type": self.question_type,
            "expert_time_mins": self.expert_time_mins,
            "question": self.question,
            "gold_answer": self.gold_answer,
            "rubric": self.rubric,
            "model_answer": self.model_answer,
            "judge_calls": [j.to_dict() for j in self.judge_calls],
            "intermediate_signals": self.intermediate_signals,
            "hybrid_score": self.hybrid_score.to_dict(),
            "error_taxonomy": self.error_taxonomy,
            "source": self.source,
            "transformation_type": self.transformation_type,
            "expected_outcome": self.expected_outcome,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class RunManifest:
    """
    Manifest for a complete evaluation run.
    
    Contains all configuration and hashes for reproducibility.
    """
    run_id: str
    timestamp: str
    dataset_path: str
    dataset_hash: str
    judge_versions: Dict[str, str]
    prompt_hashes: Dict[str, str]
    scorer_config: Dict[str, float]
    random_seed: int
    llm_config: Dict[str, Any]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_path": self.dataset_path,
            "dataset_hash": self.dataset_hash,
            "judge_versions": self.judge_versions,
            "prompt_hashes": self.prompt_hashes,
            "scorer_config": self.scorer_config,
            "random_seed": self.random_seed,
            "llm_config": self.llm_config,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AdversarialItem:
    """
    A single adversarial test item derived from canonical data.
    """
    adversarial_id: str
    parent_id: int
    difficulty_level: str
    question_type: str
    expert_time_mins: float
    question: str
    gold_answer: str
    rubric: List[Dict[str, str]]
    candidate_answer: str
    transformation_type: str
    expected_outcome: str  # "pass", "fail", or specific score band
    notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "adversarial_id": self.adversarial_id,
            "parent_id": self.parent_id,
            "difficulty_level": self.difficulty_level,
            "question_type": self.question_type,
            "expert_time_mins": self.expert_time_mins,
            "question": self.question,
            "gold_answer": self.gold_answer,
            "rubric": self.rubric,
            "candidate_answer": self.candidate_answer,
            "transformation_type": self.transformation_type,
            "expected_outcome": self.expected_outcome,
            "notes": self.notes,
        }
    
    def to_task(self) -> Task:
        """Convert to Task for evaluation."""
        return Task(
            task_id=-1,  # Will be assigned during evaluation
            question=self.question,
            gold_answer=self.gold_answer,
            rubric=self.rubric,
            question_type=self.question_type,
            expert_time_mins=self.expert_time_mins,
            difficulty_level=self.difficulty_level,
            source="adversarial",
            parent_id=self.parent_id,
            transformation_type=self.transformation_type,
            expected_outcome=self.expected_outcome,
            candidate_answer=self.candidate_answer,
            notes=self.notes,
        )
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
