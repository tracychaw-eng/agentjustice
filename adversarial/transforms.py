"""
Adversarial Transformation Types.

Defines transformations for generating adversarial test cases.
"""
from enum import Enum
from typing import Dict, Any, Callable, Optional
import re
import random


class TransformationType(str, Enum):
    """Adversarial transformation types."""
    WRONG_METRIC_RIGHT_NUMBER = "wrong_metric_right_number"
    RIGHT_METRIC_WRONG_NUMBER = "right_metric_wrong_number"
    WRONG_UNIT_SCALE = "wrong_unit_scale"
    MULTI_NUMBER_CONFLICT = "multi_number_conflict"
    KEYWORD_STUFFING = "keyword_stuffing"
    HEDGED_ANSWER = "hedged_answer"


class TransformationResult:
    """Result of applying a transformation."""
    
    def __init__(
        self,
        candidate_answer: str,
        transformation_type: TransformationType,
        expected_outcome: str,
        notes: str
    ):
        self.candidate_answer = candidate_answer
        self.transformation_type = transformation_type
        self.expected_outcome = expected_outcome
        self.notes = notes


class AdversarialTransformations:
    """
    Collection of adversarial transformations.
    
    Each transformation creates a specific type of incorrect answer
    designed to test evaluator robustness.
    """
    
    @staticmethod
    def wrong_metric_right_number(
        gold_answer: str,
        question: str
    ) -> TransformationResult:
        """
        Correct numeric value but wrong financial metric.
        
        Expected: Semantic should fail, numeric may pass → penalize
        """
        # Extract numbers from gold answer
        numbers = re.findall(r'\$?[\d,]+\.?\d*\s*(?:billion|million|%|bps)?', gold_answer)
        
        # Substitute metric words
        metric_swaps = {
            "revenue": "profit",
            "profit": "revenue",
            "margin": "ratio",
            "growth": "decline",
            "increase": "decrease",
            "beat": "miss",
            "miss": "beat",
            "expenses": "income",
            "income": "expenses",
            "assets": "liabilities",
            "liabilities": "assets",
        }
        
        candidate = gold_answer
        for original, replacement in metric_swaps.items():
            candidate = re.sub(
                rf'\b{original}\b',
                replacement,
                candidate,
                flags=re.IGNORECASE
            )
        
        # If no changes made, create synthetic version
        if candidate == gold_answer:
            if numbers:
                candidate = f"The operating expenses were {numbers[0]} for the period, showing efficiency improvements."
            else:
                candidate = "The company reported strong profit margins due to cost optimization."
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.WRONG_METRIC_RIGHT_NUMBER,
            expected_outcome="fail",
            notes="Numeric values correct but applied to wrong metric/concept"
        )
    
    @staticmethod
    def right_metric_wrong_number(
        gold_answer: str,
        question: str
    ) -> TransformationResult:
        """
        Correct metric but incorrect numeric value.
        
        Expected: Numeric should fail
        """
        # Find and modify numbers
        def perturb_number(match):
            num_str = match.group(0)
            try:
                # Extract numeric part
                num = float(re.sub(r'[^\d.]', '', num_str))
                # Perturb by 15-30%
                factor = random.choice([0.7, 0.75, 1.25, 1.3])
                new_num = num * factor
                
                # Preserve format
                if '.' in num_str:
                    new_str = f"{new_num:.2f}"
                else:
                    new_str = f"{int(new_num):,}"
                
                # Add back prefix/suffix
                prefix = num_str[:num_str.find(re.search(r'\d', num_str).group())]
                suffix_match = re.search(r'[\d,.]+(.*)', num_str)
                suffix = suffix_match.group(1) if suffix_match else ''
                
                return prefix + new_str + suffix
            except:
                return num_str
        
        candidate = re.sub(
            r'\$?[\d,]+\.?\d*',
            perturb_number,
            gold_answer
        )
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.RIGHT_METRIC_WRONG_NUMBER,
            expected_outcome="fail",
            notes="Correct metric/concept but numeric values are incorrect"
        )
    
    @staticmethod
    def wrong_unit_scale(
        gold_answer: str,
        question: str
    ) -> TransformationResult:
        """
        Million vs billion confusion.
        
        Expected: Numeric should fail with large diff_ratio
        """
        unit_swaps = [
            (r'\bbillion\b', 'million'),
            (r'\bmillion\b', 'billion'),
            (r'\bB\b', 'M'),
            (r'\bM\b', 'B'),
            (r'\bthousand\b', 'million'),
            (r'\b%\b', 'bps'),
        ]
        
        candidate = gold_answer
        swap_made = False
        
        for pattern, replacement in unit_swaps:
            new_candidate = re.sub(pattern, replacement, candidate, flags=re.IGNORECASE)
            if new_candidate != candidate:
                candidate = new_candidate
                swap_made = True
                break
        
        if not swap_made:
            # If no unit found, multiply/divide a number
            def scale_number(match):
                num_str = match.group(0)
                try:
                    num = float(re.sub(r'[^\d.]', '', num_str))
                    scaled = num * 1000  # Or /1000
                    return f"${scaled:,.0f}"
                except:
                    return num_str
            
            candidate = re.sub(r'\$[\d,]+\.?\d*', scale_number, gold_answer, count=1)
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.WRONG_UNIT_SCALE,
            expected_outcome="fail",
            notes="Unit scale confusion (e.g., million vs billion)"
        )
    
    @staticmethod
    def multi_number_conflict(
        gold_answer: str,
        question: str
    ) -> TransformationResult:
        """
        Two conflicting values in same answer.
        
        Expected: Contradiction violation
        """
        # Extract key facts
        numbers = re.findall(r'\$?[\d,]+\.?\d*\s*(?:billion|million|%|bps)?', gold_answer)
        
        if numbers:
            num = numbers[0]
            # Create conflicting statement
            candidate = f"{gold_answer}\n\nHowever, alternative calculations suggest the value could be {num} times 1.5, which would be approximately {num} increased by 50%."
        else:
            candidate = f"{gold_answer}\n\nAlternatively, some sources indicate the figure was actually 25% higher than reported."
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.MULTI_NUMBER_CONFLICT,
            expected_outcome="contradiction_violated",
            notes="Answer contains two conflicting values"
        )
    
    @staticmethod
    def keyword_stuffing(
        gold_answer: str,
        question: str,
        rubric: list = None
    ) -> TransformationResult:
        """
        Contains many rubric tokens but wrong answer.
        
        Expected: Semantic should not be fooled
        """
        # Extract keywords from rubric
        keywords = []
        if rubric:
            for item in rubric:
                criteria = item.get("criteria", "")
                # Extract significant words
                words = re.findall(r'\b[A-Za-z]{4,}\b', criteria)
                keywords.extend(words[:5])
        
        if not keywords:
            keywords = re.findall(r'\b[A-Za-z]{4,}\b', gold_answer)[:10]
        
        # Create stuffed answer
        keyword_str = ", ".join(set(keywords[:8]))
        candidate = f"Regarding {keyword_str}, the analysis shows various factors including {keyword_str}. Key metrics like {keywords[0] if keywords else 'performance'} and related measures indicate overall alignment with expectations."
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.KEYWORD_STUFFING,
            expected_outcome="fail",
            notes="Contains relevant keywords but no actual correct information"
        )
    
    @staticmethod
    def hedged_answer(
        gold_answer: str,
        question: str
    ) -> TransformationResult:
        """
        Uncertain language with no final value.
        
        Expected: Low confidence, should penalize
        """
        hedging_phrases = [
            "It's difficult to determine exactly, but",
            "Based on limited information, it might be",
            "The data suggests, though uncertainly,",
            "There could potentially be",
            "It's possible that approximately",
        ]
        
        prefix = random.choice(hedging_phrases)
        
        # Strip specific numbers and add uncertainty
        vague = re.sub(r'\$?[\d,]+\.?\d*', 'some value', gold_answer)
        
        candidate = f"{prefix} {vague}. However, further analysis would be needed to confirm these figures. The actual numbers could vary significantly."
        
        return TransformationResult(
            candidate_answer=candidate,
            transformation_type=TransformationType.HEDGED_ANSWER,
            expected_outcome="fail",
            notes="Hedged/uncertain language with no definitive answer"
        )
    
    @classmethod
    def apply(
        cls,
        transform_type: TransformationType,
        gold_answer: str,
        question: str,
        rubric: list = None
    ) -> TransformationResult:
        """Apply a specific transformation."""
        transforms = {
            TransformationType.WRONG_METRIC_RIGHT_NUMBER: cls.wrong_metric_right_number,
            TransformationType.RIGHT_METRIC_WRONG_NUMBER: cls.right_metric_wrong_number,
            TransformationType.WRONG_UNIT_SCALE: cls.wrong_unit_scale,
            TransformationType.MULTI_NUMBER_CONFLICT: cls.multi_number_conflict,
            TransformationType.KEYWORD_STUFFING: lambda g, q: cls.keyword_stuffing(g, q, rubric),
            TransformationType.HEDGED_ANSWER: cls.hedged_answer,
        }
        
        return transforms[transform_type](gold_answer, question)
    
    @classmethod
    def all_types(cls) -> list:
        """Get all transformation types."""
        return list(TransformationType)
