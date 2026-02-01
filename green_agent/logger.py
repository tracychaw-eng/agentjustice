"""
Audit-First Logger for AgentBeats.

Logs complete traces for replay and inspection.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import threading

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import LOGS_DIR, ARTIFACTS_DIR, RESULTS_DIR
from core.types import TaskTrace, RunManifest


class AuditLogger:
    """
    Audit-first logger for complete traceability.
    
    Writes per-task JSONL traces and run manifests.
    """
    
    def __init__(self, run_id: str, logs_dir: Path = None):
        """
        Initialize logger for a run.
        
        Args:
            run_id: Unique identifier for this run
            logs_dir: Directory for log files (uses LOGS_DIR by default)
        """
        self.run_id = run_id
        self.logs_dir = Path(logs_dir) if logs_dir else LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create run-specific subdirectory
        self.run_dir = self.logs_dir / run_id
        self.run_dir.mkdir(exist_ok=True)
        
        # Trace file paths
        self.canonical_traces_path = self.run_dir / "canonical_traces.jsonl"
        self.adversarial_traces_path = self.run_dir / "adversarial_traces.jsonl"
        self.manifest_path = self.run_dir / "manifest.json"
        
        # Thread lock for concurrent writes
        self._lock = threading.Lock()
        
        # Counters
        self.canonical_count = 0
        self.adversarial_count = 0
        self.error_count = 0
    
    def log_trace(self, trace: TaskTrace):
        """
        Log a task trace.
        
        Args:
            trace: Complete trace for one task
        """
        with self._lock:
            # Choose file based on source
            if trace.source == "adversarial":
                path = self.adversarial_traces_path
                self.adversarial_count += 1
            else:
                path = self.canonical_traces_path
                self.canonical_count += 1
            
            # Count errors
            if trace.error_taxonomy:
                self.error_count += len(trace.error_taxonomy)
            
            # Append to JSONL file
            with open(path, "a", encoding="utf-8") as f:
                f.write(trace.to_json() + "\n")
    
    def log_manifest(self, manifest: RunManifest):
        """
        Write run manifest.
        
        Args:
            manifest: Complete run manifest
        """
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.to_json())
    
    def get_stats(self) -> dict:
        """Get logging statistics."""
        return {
            "run_id": self.run_id,
            "canonical_traces": self.canonical_count,
            "adversarial_traces": self.adversarial_count,
            "total_errors": self.error_count,
            "logs_dir": str(self.run_dir)
        }
    
    def read_canonical_traces(self) -> List[TaskTrace]:
        """Read all canonical traces from log file."""
        return self._read_traces(self.canonical_traces_path)
    
    def read_adversarial_traces(self) -> List[TaskTrace]:
        """Read all adversarial traces from log file."""
        return self._read_traces(self.adversarial_traces_path)
    
    def _read_traces(self, path: Path) -> List[dict]:
        """Read traces from JSONL file."""
        traces = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            traces.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return traces
    
    def read_manifest(self) -> Optional[RunManifest]:
        """Read run manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        return None

    def write_agentbeats_results(self, purple_agent_id: str = "purple_agent") -> Path:
        """
        Write results in AgentBeats leaderboard-compatible JSON format.

        Args:
            purple_agent_id: The purple agent identifier for the leaderboard

        Returns:
            Path to the written results file
        """
        results_dir = RESULTS_DIR
        results_dir.mkdir(parents=True, exist_ok=True)

        # Read all traces
        canonical_traces = self._read_traces(self.canonical_traces_path)
        adversarial_traces = self._read_traces(self.adversarial_traces_path)

        # Build results array
        results = []

        for trace in canonical_traces:
            hybrid = trace.get("hybrid_score", {})
            results.append({
                "task_id": trace.get("task_id"),
                "source": "canonical",
                "final_score": hybrid.get("final_score", 0.0),
                "semantic_score": hybrid.get("semantic_score", 0.0),
                "numeric_score": hybrid.get("numeric_score", 0.0),
                "contradiction_violated": hybrid.get("contradiction_violated", False),
                "difficulty_level": trace.get("difficulty_level", "Unknown"),
                "question_type": trace.get("question_type", "Unknown")
            })

        for trace in adversarial_traces:
            hybrid = trace.get("hybrid_score", {})
            results.append({
                "task_id": trace.get("task_id"),
                "source": "adversarial",
                "final_score": hybrid.get("final_score", 0.0),
                "semantic_score": hybrid.get("semantic_score", 0.0),
                "numeric_score": hybrid.get("numeric_score", 0.0),
                "contradiction_violated": hybrid.get("contradiction_violated", False),
                "difficulty_level": trace.get("difficulty_level", "Adversarial"),
                "question_type": trace.get("question_type", trace.get("transformation_type", "Unknown")),
                "transformation_type": trace.get("transformation_type"),
                "expected_outcome": trace.get("expected_outcome")
            })

        # Build AgentBeats-compatible structure
        agentbeats_result = {
            "participants": {
                "agent": purple_agent_id
            },
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results": results,
            "summary": {
                "canonical_count": len(canonical_traces),
                "adversarial_count": len(adversarial_traces),
                "total_count": len(results)
            }
        }

        # Write to results directory
        results_file = results_dir / f"{self.run_id}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(agentbeats_result, f, indent=2)

        # Also write to /app/output/detailed_results.json for AgentBeats submission
        # Note: We use detailed_results.json because agentbeats-client creates its own results.json
        output_dir = Path("/app/output")
        if output_dir.exists():
            output_file = output_dir / "detailed_results.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(agentbeats_result, f, indent=2)
            print(f"[Green Agent] Detailed results written to: {output_file}")

        return results_file


class LoggerManager:
    """
    Manages logger instances for multiple runs.
    """
    
    def __init__(self, logs_dir: Path = None):
        self.logs_dir = logs_dir or LOGS_DIR
        self._loggers = {}
    
    def create_logger(self, run_id: str = None) -> AuditLogger:
        """
        Create a new logger for a run.
        
        Args:
            run_id: Optional run ID (generates one if not provided)
        
        Returns:
            AuditLogger instance
        """
        if run_id is None:
            run_id = self._generate_run_id()
        
        logger = AuditLogger(run_id, self.logs_dir)
        self._loggers[run_id] = logger
        return logger
    
    def get_logger(self, run_id: str) -> Optional[AuditLogger]:
        """Get existing logger by run ID."""
        return self._loggers.get(run_id)
    
    def list_runs(self) -> List[str]:
        """List all run IDs with logs."""
        if not self.logs_dir.exists():
            return []
        return [d.name for d in self.logs_dir.iterdir() if d.is_dir()]
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        import uuid
        short_uuid = str(uuid.uuid4())[:8]
        return f"run_{timestamp}_{short_uuid}"


# Singleton manager
_manager = None

def get_logger_manager() -> LoggerManager:
    """Get logger manager singleton."""
    global _manager
    if _manager is None:
        _manager = LoggerManager()
    return _manager


def create_run_logger(run_id: str = None) -> AuditLogger:
    """Create a new run logger."""
    return get_logger_manager().create_logger(run_id)
