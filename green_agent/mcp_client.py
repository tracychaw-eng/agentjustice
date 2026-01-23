"""
MCP Client for calling judge tools.

Provides async interface to MCP server endpoints.
"""
import httpx
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import server_config
from core.types import JudgeOutput, JudgeCall, ParsedValue, CriteriaMatch


@dataclass
class MCPClientConfig:
    """Configuration for MCP client."""
    base_url: str
    timeout: float = 30.0
    retries: int = 3


class MCPClient:
    """
    Client for calling MCP judge tools.
    
    Handles HTTP communication with the MCP server and
    converts responses to structured types.
    """
    
    def __init__(self, config: MCPClientConfig = None):
        """
        Initialize MCP client.

        Args:
            config: Client configuration (uses server_config if not provided)
        """
        if config is None:
            config = MCPClientConfig(base_url=server_config.mcp_server_url)

        self.config = config
        self.client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout
        )

    def get_endpoint_info(self) -> Dict[str, str]:
        """Get information about configured endpoints."""
        return {
            "base_url": self.config.base_url,
            "semantic_endpoint": f"{self.config.base_url}{server_config.mcp_semantic_path}",
            "numeric_endpoint": f"{self.config.base_url}{server_config.mcp_numeric_path}",
            "contradiction_endpoint": f"{self.config.base_url}{server_config.mcp_contradiction_path}",
            "health_endpoint": f"{self.config.base_url}{server_config.mcp_health_path}",
            "timeout": self.config.timeout,
            "retries": self.config.retries,
        }

    def preflight_check(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Perform preflight checks to validate MCP server connectivity and endpoints.

        Args:
            verbose: If True, print detailed information

        Returns:
            Dictionary with check results
        """
        results = {
            "overall_status": "unknown",
            "checks": [],
            "errors": [],
            "warnings": []
        }

        if verbose:
            print("\n" + "=" * 70)
            print("  MCP Server Preflight Check")
            print("=" * 70)
            print(f"\nBase URL: {self.config.base_url}")
            print(f"Timeout: {self.config.timeout}s")

        # Check 1: Health endpoint
        try:
            if verbose:
                print(f"\n[1/5] Checking health endpoint...")
            response = self.client.get(server_config.mcp_health_path)
            if response.status_code == 200:
                results["checks"].append({"name": "health", "status": "pass"})
                if verbose:
                    print(f"  [PASS] Health check passed (status: {response.status_code})")
            else:
                results["checks"].append({"name": "health", "status": "fail", "code": response.status_code})
                results["errors"].append(f"Health check returned {response.status_code}")
                if verbose:
                    print(f"  [FAIL] Health check failed (status: {response.status_code})")
        except Exception as e:
            results["checks"].append({"name": "health", "status": "error", "error": str(e)})
            results["errors"].append(f"Health check error: {str(e)}")
            if verbose:
                print(f"  [ERROR] Health check error: {str(e)}")

        # Check 2: Version endpoint
        try:
            if verbose:
                print(f"\n[2/5] Checking version endpoint...")
            response = self.client.get(server_config.mcp_version_path)
            if response.status_code == 200:
                version_data = response.json()
                results["checks"].append({"name": "version", "status": "pass", "data": version_data})
                if verbose:
                    print(f"  [PASS] Version endpoint passed")
                    print(f"    Server version: {version_data.get('server_version', 'unknown')}")
                    print(f"    Judge versions: {version_data.get('judge_versions', {})}")
            else:
                results["checks"].append({"name": "version", "status": "fail", "code": response.status_code})
                if verbose:
                    print(f"  [FAIL] Version endpoint failed (status: {response.status_code})")
        except Exception as e:
            results["checks"].append({"name": "version", "status": "error", "error": str(e)})
            if verbose:
                print(f"  [WARN] Version endpoint error: {str(e)}")

        # Check 3-5: Test each judge with minimal payload
        test_payload = {
            "question": "Test question",
            "model_answer": "Test answer",
            "gold_answer": "Test answer",
            "rubric": []
        }

        for idx, (judge_name, endpoint) in enumerate([
            ("semantic", server_config.mcp_semantic_path),
            ("numeric", server_config.mcp_numeric_path),
            ("contradiction", server_config.mcp_contradiction_path)
        ], start=3):
            try:
                if verbose:
                    print(f"\n[{idx}/5] Testing {judge_name} judge endpoint...")
                response = self.client.post(endpoint, json=test_payload)
                if response.status_code == 200:
                    data = response.json()
                    required_fields = ["score", "confidence", "reason"]
                    missing = [f for f in required_fields if f not in data]
                    if not missing:
                        results["checks"].append({"name": f"{judge_name}_judge", "status": "pass"})
                        if verbose:
                            print(f"  [PASS] {judge_name.capitalize()} judge passed (score: {data.get('score', 'N/A')})")
                    else:
                        results["checks"].append({
                            "name": f"{judge_name}_judge",
                            "status": "fail",
                            "reason": f"Missing fields: {missing}"
                        })
                        results["errors"].append(f"{judge_name} judge missing fields: {missing}")
                        if verbose:
                            print(f"  [FAIL] {judge_name.capitalize()} judge response missing fields: {missing}")
                else:
                    results["checks"].append({
                        "name": f"{judge_name}_judge",
                        "status": "fail",
                        "code": response.status_code
                    })
                    results["errors"].append(f"{judge_name} judge returned {response.status_code}")
                    if verbose:
                        print(f"  [FAIL] {judge_name.capitalize()} judge failed (status: {response.status_code})")
            except Exception as e:
                results["checks"].append({
                    "name": f"{judge_name}_judge",
                    "status": "error",
                    "error": str(e)
                })
                results["errors"].append(f"{judge_name} judge error: {str(e)}")
                if verbose:
                    print(f"  [ERROR] {judge_name.capitalize()} judge error: {str(e)}")

        # Determine overall status
        passed = sum(1 for c in results["checks"] if c["status"] == "pass")
        total = len(results["checks"])

        if passed == total:
            results["overall_status"] = "pass"
        elif passed >= 3:  # At least health + 2 judges working
            results["overall_status"] = "degraded"
            results["warnings"].append("Some endpoints failed but core functionality available")
        else:
            results["overall_status"] = "fail"

        if verbose:
            print("\n" + "=" * 70)
            print(f"  Overall Status: {results['overall_status'].upper()}")
            print(f"  Checks Passed: {passed}/{total}")
            if results["errors"]:
                print(f"\n  Errors:")
                for err in results["errors"]:
                    print(f"    - {err}")
            print("=" * 70 + "\n")

        return results
    
    def health_check(self) -> bool:
        """Check if MCP server is healthy."""
        try:
            response = self.client.get(server_config.mcp_health_path)
            return response.status_code == 200
        except Exception:
            return False

    def get_versions(self) -> Dict[str, Any]:
        """Get judge versions and prompt hashes."""
        try:
            response = self.client.get(server_config.mcp_version_path)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def call_semantic_judge(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        meta: Dict[str, Any] = None
    ) -> JudgeOutput:
        """
        Call semantic equivalence judge.
        
        Args:
            question: The original question
            model_answer: Answer from model
            gold_answer: Reference answer
            rubric: Evaluation criteria
            meta: Optional metadata
        
        Returns:
            JudgeOutput with results
        """
        start_time = time.perf_counter()
        
        payload = {
            "question": question,
            "model_answer": model_answer,
            "gold_answer": gold_answer,
            "rubric": rubric,
            "meta": meta or {}
        }
        
        try:
            response = self.client.post(
                server_config.mcp_semantic_path,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Convert criteria matches
            criteria_matches = [
                CriteriaMatch(
                    criteria=cm.get("criteria", ""),
                    matched=cm.get("matched", False),
                    confidence=cm.get("confidence", 0.0),
                    reason=cm.get("reason", "")
                )
                for cm in data.get("criteria_matches", [])
            ]
            
            return JudgeOutput(
                judge_name="semantic_equivalence",
                judge_version=data.get("judge_version", "unknown"),
                score=data.get("score", 0.0),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
                raw_output=data,
                latency_ms=latency_ms,
                prompt_hash=data.get("prompt_hash", ""),
                criteria_matches=criteria_matches
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_type = type(e).__name__
            error_msg = str(e)

            return JudgeOutput(
                judge_name="semantic_equivalence",
                judge_version="error",
                score=0.0,
                confidence=0.0,
                reason=f"MCP call failed: {error_type}: {error_msg}",
                raw_output={
                    "error": error_msg,
                    "error_type": error_type,
                    "status_code": getattr(e, 'status_code', None)
                },
                latency_ms=latency_ms,
                prompt_hash="",
                judge_ok=False
            )
    
    def call_numeric_judge(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        meta: Dict[str, Any] = None,
        tolerance: float = None
    ) -> JudgeOutput:
        """
        Call numeric tolerance judge.
        
        Args:
            question: The original question
            model_answer: Answer from model
            gold_answer: Reference answer
            rubric: Evaluation criteria
            meta: Optional metadata
            tolerance: Relative tolerance override
        
        Returns:
            JudgeOutput with results
        """
        start_time = time.perf_counter()
        
        payload = {
            "question": question,
            "model_answer": model_answer,
            "gold_answer": gold_answer,
            "rubric": rubric,
            "meta": meta or {},
            "tolerance": tolerance
        }
        
        try:
            response = self.client.post(
                server_config.mcp_numeric_path,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Convert parsed values
            parsed_model = [
                ParsedValue(
                    value=v.get("value", 0.0),
                    unit=v.get("unit"),
                    context=v.get("context"),
                    original_text=v.get("original_text", "")
                )
                for v in data.get("parsed_model_values", [])
            ]
            
            parsed_gold = [
                ParsedValue(
                    value=v.get("value", 0.0),
                    unit=v.get("unit"),
                    context=v.get("context"),
                    original_text=v.get("original_text", "")
                )
                for v in data.get("parsed_gold_values", [])
            ]
            
            return JudgeOutput(
                judge_name="numeric_tolerance",
                judge_version=data.get("judge_version", "unknown"),
                score=data.get("score", 0.0),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
                raw_output=data,
                latency_ms=latency_ms,
                prompt_hash=data.get("prompt_hash", ""),
                parsed_model_values=parsed_model,
                parsed_gold_values=parsed_gold,
                tolerance_used=data.get("tolerance_used"),
                diff_ratio=data.get("diff_ratio"),
                failure_reason=data.get("failure_reason", "none")
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_type = type(e).__name__
            error_msg = str(e)

            return JudgeOutput(
                judge_name="numeric_tolerance",
                judge_version="error",
                score=0.0,
                confidence=0.0,
                reason=f"MCP call failed: {error_type}: {error_msg}",
                raw_output={
                    "error": error_msg,
                    "error_type": error_type,
                    "status_code": getattr(e, 'status_code', None)
                },
                latency_ms=latency_ms,
                prompt_hash="",
                judge_ok=False,
                failure_reason="extraction_failed"  # Network/parse error = extraction failed
            )
    
    def call_contradiction_judge(
        self,
        question: str,
        model_answer: str,
        gold_answer: str,
        rubric: List[Dict[str, str]],
        meta: Dict[str, Any] = None
    ) -> JudgeOutput:
        """
        Call contradiction detection judge.
        
        Args:
            question: The original question
            model_answer: Answer from model
            gold_answer: Reference answer
            rubric: Evaluation criteria
            meta: Optional metadata
        
        Returns:
            JudgeOutput with results
        """
        start_time = time.perf_counter()
        
        payload = {
            "question": question,
            "model_answer": model_answer,
            "gold_answer": gold_answer,
            "rubric": rubric,
            "meta": meta or {}
        }
        
        try:
            response = self.client.post(
                server_config.mcp_contradiction_path,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            return JudgeOutput(
                judge_name="contradiction",
                judge_version=data.get("judge_version", "unknown"),
                score=data.get("score", 0.0),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
                raw_output=data,
                latency_ms=latency_ms,
                prompt_hash=data.get("prompt_hash", ""),
                violated=data.get("violated", False),
                contradiction_details=data.get("contradiction_details", [])
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_type = type(e).__name__
            error_msg = str(e)

            return JudgeOutput(
                judge_name="contradiction",
                judge_version="error",
                score=0.0,
                confidence=0.0,
                reason=f"MCP call failed: {error_type}: {error_msg}",
                raw_output={
                    "error": error_msg,
                    "error_type": error_type,
                    "status_code": getattr(e, 'status_code', None)
                },
                latency_ms=latency_ms,
                prompt_hash="",
                judge_ok=False,
                violated=None  # None = unknown/error, not a contradiction
            )
    
    def to_judge_call(self, output: JudgeOutput, input_payload: Dict, response_status: int = None) -> JudgeCall:
        """
        Convert JudgeOutput to JudgeCall for logging.

        Args:
            output: Judge output
            input_payload: Original request payload
            response_status: HTTP response status code (if available)

        Returns:
            JudgeCall for audit logging
        """
        error_info = None
        if not output.judge_ok:
            error_info = output.raw_output.get("error")

        return JudgeCall(
            judge=output.judge_name,
            input_payload={
                "question": input_payload.get("question", "")[:200],  # Truncate for logs
                "model_answer": input_payload.get("model_answer", "")[:200],
                "gold_answer": input_payload.get("gold_answer", "")[:200],
                "rubric_count": len(input_payload.get("rubric", [])),
                "meta": input_payload.get("meta", {})
            },
            output_payload={
                "score": output.raw_output.get("score", 0.0),
                "confidence": output.raw_output.get("confidence", 0.0),
                "reason": output.raw_output.get("reason", "")[:500],  # Truncate
                "judge_ok": output.judge_ok,
                "error": error_info,
                "error_type": output.raw_output.get("error_type"),
                "status_code": response_status or output.raw_output.get("status_code"),
                "violated": output.raw_output.get("violated"),
                "failure_reason": getattr(output, "failure_reason", None) or output.raw_output.get("failure_reason", "none")
            },
            latency_ms=output.latency_ms,
            judge_version=output.judge_version,
            prompt_hash=output.prompt_hash,
            error=error_info
        )
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton client
_client_instance = None

def get_mcp_client() -> MCPClient:
    """Get or create MCP client singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPClient()
    return _client_instance
