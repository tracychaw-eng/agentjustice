"""
Environment abstraction for AgentBeats.

Provides a reset()/step() interface for iterating through evaluation tasks.
"""
import pandas as pd
import json
import ast
from pathlib import Path
from typing import List, Optional, Iterator, Union

from .types import Task, AdversarialItem


class EvaluationEnvironment:
    """
    Environment for loading and iterating through evaluation tasks.
    
    Supports both canonical dataset (CSV) and adversarial dataset (JSONL).
    """
    
    def __init__(self, dataset_path: Union[str, Path]):
        """
        Initialize environment with dataset path.
        
        Args:
            dataset_path: Path to CSV or JSONL file
        """
        self.dataset_path = Path(dataset_path)
        self.tasks: List[Task] = []
        self.current_index: int = 0
        self._loaded = False
    
    def load(self) -> "EvaluationEnvironment":
        """Load tasks from dataset file."""
        if self.dataset_path.suffix == ".csv":
            self._load_csv()
        elif self.dataset_path.suffix == ".jsonl":
            self._load_jsonl()
        else:
            raise ValueError(f"Unsupported file format: {self.dataset_path.suffix}")
        
        self._loaded = True
        return self
    
    def _load_csv(self):
        """Load tasks from CSV file (canonical dataset)."""
        df = pd.read_csv(self.dataset_path)
        
        for idx, row in df.iterrows():
            # Parse rubric from JSON string
            rubric = self._parse_rubric(row.get("Rubric", "[]"))
            
            task = Task(
                task_id=int(row.iloc[0]) if pd.notna(row.iloc[0]) else idx,
                question=str(row.get("Question", "")),
                gold_answer=str(row.get("Answer", "")),
                rubric=rubric,
                question_type=str(row.get("Question Type", "Unknown")),
                expert_time_mins=float(row.get("Expert time (mins)", 0)),
                difficulty_level=str(row.get("Difficulty Level", "Unknown")),
                source="canonical",
            )
            self.tasks.append(task)
    
    def _load_jsonl(self):
        """Load tasks from JSONL file (adversarial dataset)."""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    
                    # Convert AdversarialItem to Task
                    if "adversarial_id" in data:
                        item = AdversarialItem(**data)
                        task = item.to_task()
                        task.task_id = line_num
                    else:
                        # Direct Task format
                        task = Task.from_dict(data)
                        task.task_id = line_num
                    
                    self.tasks.append(task)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}")
    
    def _parse_rubric(self, rubric_str: str) -> List[dict]:
        """
        Parse rubric from string format.
        
        Handles both JSON and Python literal formats.
        """
        if not rubric_str or rubric_str == "[]":
            return []
        
        # Try JSON first
        try:
            return json.loads(rubric_str)
        except json.JSONDecodeError:
            pass
        
        # Try Python literal eval (for single-quoted strings)
        try:
            return ast.literal_eval(rubric_str)
        except (ValueError, SyntaxError):
            pass
        
        # Return empty if parsing fails
        return []
    
    def reset(self) -> Optional[Task]:
        """
        Reset environment to beginning.
        
        Returns:
            First task or None if empty
        """
        self.current_index = 0
        if self.tasks:
            return self.tasks[0]
        return None
    
    def step(self) -> Optional[Task]:
        """
        Advance to next task.
        
        Returns:
            Next task or None if exhausted
        """
        self.current_index += 1
        if self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None
    
    def current(self) -> Optional[Task]:
        """Get current task without advancing."""
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None
    
    def is_done(self) -> bool:
        """Check if all tasks have been processed."""
        return self.current_index >= len(self.tasks)
    
    def __len__(self) -> int:
        """Return number of tasks."""
        return len(self.tasks)
    
    def __iter__(self) -> Iterator[Task]:
        """Iterate through all tasks."""
        return iter(self.tasks)
    
    def get_by_difficulty(self, difficulty: str) -> List[Task]:
        """
        Get tasks filtered by difficulty level.
        
        Args:
            difficulty: "Easy", "Medium", or "Hard"
        
        Returns:
            List of tasks with matching difficulty
        """
        return [t for t in self.tasks if t.difficulty_level == difficulty]
    
    def get_by_type(self, question_type: str) -> List[Task]:
        """
        Get tasks filtered by question type.
        
        Args:
            question_type: Question type string
        
        Returns:
            List of tasks with matching type
        """
        return [t for t in self.tasks if t.question_type == question_type]
    
    def get_stats(self) -> dict:
        """Get dataset statistics."""
        difficulty_counts = {}
        type_counts = {}
        
        for task in self.tasks:
            # Count by difficulty
            diff = task.difficulty_level
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
            
            # Count by type
            qtype = task.question_type
            type_counts[qtype] = type_counts.get(qtype, 0) + 1
        
        return {
            "total_tasks": len(self.tasks),
            "by_difficulty": difficulty_counts,
            "by_type": type_counts,
            "source": self.dataset_path.name,
        }


def load_canonical_dataset(dataset_path: Union[str, Path]) -> EvaluationEnvironment:
    """
    Load the canonical dataset.
    
    Args:
        dataset_path: Path to public_updated.csv
    
    Returns:
        Loaded environment
    """
    env = EvaluationEnvironment(dataset_path)
    return env.load()


def load_adversarial_dataset(dataset_path: Union[str, Path]) -> EvaluationEnvironment:
    """
    Load the adversarial dataset.
    
    Args:
        dataset_path: Path to public_adversarial.jsonl
    
    Returns:
        Loaded environment
    """
    env = EvaluationEnvironment(dataset_path)
    return env.load()
