"""
Numeric Tolerance Judge.

Evaluates whether numeric values in model answer match gold answer within tolerance.
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import llm_config, JUDGE_VERSIONS, scorer_config
from core.hashing import hash_prompt


# Regex to detect numeric content in text
NUMERIC_PATTERN = re.compile(r'\d+(?:[.,]\d+)?(?:\s*[%$BMKbmk])?')


# Load pinned prompt
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "numeric.txt"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

PROMPT_HASH = hash_prompt(SYSTEM_PROMPT, JUDGE_VERSIONS["numeric"])


class ParsedValue(BaseModel):
    value: float
    unit: Optional[str] = None
    context: Optional[str] = None
    original_text: str = ""


class ValueComparison(BaseModel):
    gold: float
    model: Optional[float] = None
    match: bool
    diff_ratio: Optional[float] = None
    context: str = ""


class NumericJudgeOutput(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    failure_reason: Optional[str] = "none"  # extraction_failed | alignment_failed | tolerance_failed | none
    parsed_model_values: List[ParsedValue] = Field(default_factory=list)
    parsed_gold_values: List[ParsedValue] = Field(default_factory=list)
    tolerance_used: float
    diff_ratio: Optional[float] = None
    value_comparisons: List[ValueComparison] = Field(default_factory=list)


class NumericJudge:
    """
    Numeric tolerance judge using LLM for parsing and comparison.
    
    Stateless - each call is independent.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=llm_config.get_api_key())
        self.model = llm_config.model
        self.temperature = llm_config.temperature
        self.max_tokens = llm_config.max_tokens
        self.version = JUDGE_VERSIONS["numeric"]
        self.prompt_hash = PROMPT_HASH
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for exact match comparison."""
        if not text:
            return ""
        # Strip whitespace, normalize line endings, lowercase
        return " ".join(text.lower().split())

    def _has_numeric_content(self, text: str) -> bool:
        """Check if text contains any numeric values."""
        if not text:
            return False
        return bool(NUMERIC_PATTERN.search(text))

    def judge(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        meta: Dict[str, Any] = None,
        tolerance: float = None
    ) -> Dict[str, Any]:
        """
        Judge numeric accuracy.

        Args:
            question: The original question
            model_answer: Answer from model being evaluated
            gold_answer: Reference correct answer
            rubric: List of evaluation criteria
            meta: Optional metadata (task_id, difficulty, etc.)
            tolerance: Relative tolerance (overrides config if provided)

        Returns:
            Structured judgment result
        """
        start_time = time.perf_counter()

        # Use provided tolerance or default from config
        tol = tolerance if tolerance is not None else scorer_config.numeric_rel_tol

        # EXACT MATCH SHORTCUT: Skip LLM if answers are textually identical
        if self._normalize_text(model_answer) == self._normalize_text(gold_answer):
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "score": 1.0,
                "confidence": 1.0,
                "reason": "Exact text match detected - skipped LLM evaluation",
                "failure_reason": "none",
                "parsed_model_values": [],
                "parsed_gold_values": [],
                "tolerance_used": tol,
                "diff_ratio": 0.0,
                "value_comparisons": [],
                "judge_version": self.version,
                "prompt_hash": self.prompt_hash,
                "latency_ms": latency_ms,
                "raw_output": {"exact_match": True},
                "error": None
            }

        # Build user prompt
        user_prompt = self._build_user_prompt(
            question, model_answer, gold_answer, rubric, tol
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Ensure tolerance_used is set
            if "tolerance_used" not in result:
                result["tolerance_used"] = tol
            
            # Validate with Pydantic
            validated = NumericJudgeOutput(**result)
            
            return {
                "score": validated.score,
                "confidence": validated.confidence,
                "reason": validated.reason,
                "failure_reason": validated.failure_reason or "none",
                "parsed_model_values": [v.model_dump() for v in validated.parsed_model_values],
                "parsed_gold_values": [v.model_dump() for v in validated.parsed_gold_values],
                "tolerance_used": validated.tolerance_used,
                "diff_ratio": validated.diff_ratio,
                "value_comparisons": [v.model_dump() for v in validated.value_comparisons],
                "judge_version": self.version,
                "prompt_hash": self.prompt_hash,
                "latency_ms": latency_ms,
                "raw_output": result,
                "error": None
            }
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Determine if this is a true extraction failure or a parse error
            # If numbers exist in both answers, extraction was attempted (LLM tried)
            gold_has_numbers = self._has_numeric_content(gold_answer)
            model_has_numbers = self._has_numeric_content(model_answer)

            if gold_has_numbers and model_has_numbers:
                # Parse error: LLM tried but produced malformed JSON
                # Set confidence > 0 because extraction was attempted
                failure_reason = "parse_error"
                confidence = 0.5  # Attempted but couldn't complete
            elif not gold_has_numbers:
                # No numbers in gold = nothing to extract = not an error
                failure_reason = "none"
                confidence = 1.0
            else:
                # True extraction failure: gold has numbers, model doesn't
                failure_reason = "extraction_failed"
                confidence = 0.0

            return {
                "score": 0.0 if failure_reason != "none" else 1.0,
                "confidence": confidence,
                "reason": f"Judge error: {str(e)}",
                "failure_reason": failure_reason,
                "parsed_model_values": [],
                "parsed_gold_values": [],
                "tolerance_used": tol,
                "diff_ratio": None,
                "value_comparisons": [],
                "judge_version": self.version,
                "prompt_hash": self.prompt_hash,
                "latency_ms": latency_ms,
                "raw_output": {},
                "error": str(e)
            }
    
    def _build_user_prompt(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        tolerance: float
    ) -> str:
        """Build the user prompt for evaluation."""
        # Extract any numeric criteria
        numeric_hints = []
        for c in rubric:
            criteria_text = c.get("criteria", "")
            # Look for numbers in criteria
            if any(char.isdigit() for char in criteria_text):
                numeric_hints.append(criteria_text)
        
        hints_text = "\n".join([f"- {h}" for h in numeric_hints]) if numeric_hints else "No specific numeric criteria."
        
        return f"""## QUESTION
{question}

## MODEL ANSWER
{model_answer}

## GOLD ANSWER
{gold_answer}

## NUMERIC CRITERIA FROM RUBRIC
{hints_text}

## TOLERANCE
{tolerance} (relative tolerance, i.e., {tolerance * 100}%)

Please extract numeric values, compare them, and return your judgment as JSON."""


# Singleton instance
_judge_instance = None

def get_judge() -> NumericJudge:
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = NumericJudge()
    return _judge_instance


def judge_numeric_tolerance(
    question: str,
    model_answer: str,
    gold_answer: str,
    rubric: List[Dict[str, str]],
    meta: Dict[str, Any] = None,
    tolerance: float = None
) -> Dict[str, Any]:
    """
    Public interface for numeric judgment.
    
    This is the function called by the MCP server.
    """
    judge = get_judge()
    return judge.judge(question, model_answer, gold_answer, rubric, meta, tolerance)
