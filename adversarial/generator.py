"""
Adversarial Dataset Generator.

Generates public_adversarial.jsonl from canonical dataset.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
import random

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATASET_PATH, ADVERSARIAL_PATH
from core.types import Task, AdversarialItem
from core.env import load_canonical_dataset
from adversarial.transforms import TransformationType, AdversarialTransformations


class AdversarialGenerator:
    """
    Generates adversarial test items from canonical dataset.
    
    Ensures coverage across:
    - All transformation types
    - All difficulty levels
    """
    
    def __init__(
        self,
        min_per_transform: int = 2,
        min_per_difficulty: int = 3,
        random_seed: int = 42
    ):
        """
        Initialize generator.
        
        Args:
            min_per_transform: Minimum items per transformation type
            min_per_difficulty: Minimum items per difficulty level
            random_seed: Random seed for reproducibility
        """
        self.min_per_transform = min_per_transform
        self.min_per_difficulty = min_per_difficulty
        self.random_seed = random_seed
        random.seed(random_seed)
    
    def generate(
        self,
        tasks: List[Task]
    ) -> List[AdversarialItem]:
        """
        Generate adversarial items from tasks.
        
        Args:
            tasks: Canonical tasks to derive from
        
        Returns:
            List of adversarial items
        """
        adversarial_items = []
        transform_types = AdversarialTransformations.all_types()
        
        # Group tasks by difficulty
        by_difficulty = {
            "Easy": [t for t in tasks if t.difficulty_level == "Easy"],
            "Medium": [t for t in tasks if t.difficulty_level == "Medium"],
            "Hard": [t for t in tasks if t.difficulty_level == "Hard"],
        }
        
        item_counter = 0
        
        # Generate items for each transformation type
        for transform_type in transform_types:
            # Ensure coverage across difficulties
            for difficulty, diff_tasks in by_difficulty.items():
                if not diff_tasks:
                    continue
                
                # Select tasks for this transform/difficulty combo
                n_to_generate = max(1, self.min_per_transform // 3)
                selected = random.sample(
                    diff_tasks,
                    min(n_to_generate, len(diff_tasks))
                )
                
                for task in selected:
                    # Apply transformation
                    result = AdversarialTransformations.apply(
                        transform_type=transform_type,
                        gold_answer=task.gold_answer,
                        question=task.question,
                        rubric=task.rubric
                    )
                    
                    # Create adversarial item
                    item = AdversarialItem(
                        adversarial_id=f"adv_{item_counter:04d}",
                        parent_id=task.task_id,
                        difficulty_level=task.difficulty_level,
                        question_type=task.question_type,
                        expert_time_mins=task.expert_time_mins,
                        question=task.question,
                        gold_answer=task.gold_answer,
                        rubric=task.rubric,
                        candidate_answer=result.candidate_answer,
                        transformation_type=result.transformation_type.value,
                        expected_outcome=result.expected_outcome,
                        notes=result.notes
                    )
                    
                    adversarial_items.append(item)
                    item_counter += 1
        
        return adversarial_items
    
    def save(
        self,
        items: List[AdversarialItem],
        output_path: Path = None
    ):
        """
        Save adversarial items to JSONL file.
        
        Args:
            items: Adversarial items to save
            output_path: Output file path
        """
        output_path = output_path or ADVERSARIAL_PATH
        
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(item.to_json() + "\n")
    
    def generate_and_save(
        self,
        dataset_path: Path = None,
        output_path: Path = None
    ) -> List[AdversarialItem]:
        """
        Full pipeline: load, generate, save.
        
        Args:
            dataset_path: Path to canonical dataset
            output_path: Path for adversarial output
        
        Returns:
            Generated adversarial items
        """
        dataset_path = dataset_path or DATASET_PATH
        output_path = output_path or ADVERSARIAL_PATH
        
        # Load canonical dataset
        env = load_canonical_dataset(dataset_path)
        tasks = list(env)
        
        # Generate adversarial items
        items = self.generate(tasks)
        
        # Save to file
        self.save(items, output_path)
        
        return items
    
    def get_stats(self, items: List[AdversarialItem]) -> Dict[str, Any]:
        """Get statistics about generated items."""
        by_transform = {}
        by_difficulty = {}
        by_expected = {}
        
        for item in items:
            # Count by transform
            t = item.transformation_type
            by_transform[t] = by_transform.get(t, 0) + 1
            
            # Count by difficulty
            d = item.difficulty_level
            by_difficulty[d] = by_difficulty.get(d, 0) + 1
            
            # Count by expected outcome
            e = item.expected_outcome
            by_expected[e] = by_expected.get(e, 0) + 1
        
        return {
            "total": len(items),
            "by_transformation": by_transform,
            "by_difficulty": by_difficulty,
            "by_expected_outcome": by_expected,
        }
    
    def generate_report(self, items: List[AdversarialItem]) -> str:
        """Generate markdown report of adversarial dataset."""
        stats = self.get_stats(items)
        
        lines = [
            "# Adversarial Dataset Report",
            "",
            f"**Total Items**: {stats['total']}",
            "",
            "## By Transformation Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ]
        
        for t, count in stats["by_transformation"].items():
            lines.append(f"| {t} | {count} |")
        
        lines.extend([
            "",
            "## By Difficulty Level",
            "",
            "| Difficulty | Count |",
            "|------------|-------|",
        ])
        
        for d, count in stats["by_difficulty"].items():
            lines.append(f"| {d} | {count} |")
        
        lines.extend([
            "",
            "## By Expected Outcome",
            "",
            "| Expected | Count |",
            "|----------|-------|",
        ])
        
        for e, count in stats["by_expected_outcome"].items():
            lines.append(f"| {e} | {count} |")
        
        lines.extend([
            "",
            "## Coverage Matrix",
            "",
            "| Difficulty | wrong_metric | wrong_number | wrong_unit | conflict | stuffing | hedged |",
            "|------------|--------------|--------------|------------|----------|----------|--------|",
        ])
        
        # Build coverage matrix
        for difficulty in ["Easy", "Medium", "Hard"]:
            row = [difficulty]
            for transform in TransformationType:
                count = sum(
                    1 for item in items
                    if item.difficulty_level == difficulty and
                    item.transformation_type == transform.value
                )
                row.append(str(count))
            lines.append("| " + " | ".join(row) + " |")
        
        return "\n".join(lines)


def generate_adversarial_dataset(
    dataset_path: Path = None,
    output_path: Path = None
) -> List[AdversarialItem]:
    """
    Convenience function to generate adversarial dataset.
    
    Args:
        dataset_path: Path to canonical CSV
        output_path: Path for output JSONL
    
    Returns:
        List of generated items
    """
    generator = AdversarialGenerator()
    return generator.generate_and_save(dataset_path, output_path)


if __name__ == "__main__":
    # Generate when run directly
    items = generate_adversarial_dataset()
    generator = AdversarialGenerator()
    print(generator.generate_report(items))
