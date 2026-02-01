"""
AgentBeats Phase-1 Configuration Settings

All paths, model settings, and tunable parameters.
Environment variables override defaults.
"""
import os
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
RESULTS_DIR = BASE_DIR / "results"  # AgentBeats leaderboard results

# Dataset paths
DATASET_PATH = DATA_DIR / "public_updated.csv"
ADVERSARIAL_PATH = DATA_DIR / "public_adversarial.jsonl"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
ARTIFACTS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


@dataclass
class LLMConfig:
    """LLM configuration for judge tools."""
    provider: str = os.getenv("LLM_PROVIDER", "openai")
    model: str = os.getenv("LLM_MODEL", "gpt-4o")
    temperature: float = 0.0  # Frozen at 0 for reproducibility
    max_tokens: int = 1024
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    
    # Anthropic fallback
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    def get_api_key(self) -> str:
        if self.provider == "openai":
            return self.api_key
        elif self.provider == "anthropic":
            return self.anthropic_api_key
        return self.api_key


@dataclass
class ScorerConfig:
    """Hybrid scorer configuration (≤5 tunable parameters)."""
    numeric_rel_tol: float = 0.01  # 1% relative tolerance
    semantic_conf_threshold: float = 0.7
    consistency_penalty: float = 0.2
    contradiction_penalty: float = 0.5
    hedging_penalty: float = 0.1
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "numeric_rel_tol": self.numeric_rel_tol,
            "semantic_conf_threshold": self.semantic_conf_threshold,
            "consistency_penalty": self.consistency_penalty,
            "contradiction_penalty": self.contradiction_penalty,
            "hedging_penalty": self.hedging_penalty,
        }


@dataclass
class CalibrationConfig:
    """Cross-validation and calibration settings."""
    cv_folds: int = 5
    cv_repeats: int = 5
    random_seed: int = 42
    
    # Parameter search space
    param_grid: Dict[str, List[float]] = field(default_factory=lambda: {
        "numeric_rel_tol": [0.005, 0.01, 0.02, 0.05],
        "semantic_conf_threshold": [0.5, 0.6, 0.7, 0.8],
        "consistency_penalty": [0.1, 0.2, 0.3],
        "contradiction_penalty": [0.3, 0.4, 0.5],
        "hedging_penalty": [0.0, 0.1, 0.2],
    })


@dataclass
class ServerConfig:
    """Server configuration for MCP and A2A."""
    mcp_server_host: str = os.getenv("MCP_SERVER_HOST", "localhost")
    mcp_server_port: int = int(os.getenv("MCP_SERVER_PORT", "8001"))

    green_agent_host: str = os.getenv("GREEN_AGENT_HOST", "localhost")
    green_agent_port: int = int(os.getenv("GREEN_AGENT_PORT", "8002"))

    purple_agent_host: str = os.getenv("PURPLE_AGENT_HOST", "localhost")
    purple_agent_port: int = int(os.getenv("PURPLE_AGENT_PORT", "8003"))

    # Full URL overrides (for Docker/K8s environments)
    _mcp_server_url_override: str = field(default_factory=lambda: os.getenv("MCP_SERVER_URL", ""))
    _green_agent_url_override: str = field(default_factory=lambda: os.getenv("GREEN_AGENT_URL", ""))
    _purple_agent_url_override: str = field(default_factory=lambda: os.getenv("PURPLE_AGENT_URL", ""))

    # MCP judge endpoint paths
    mcp_semantic_path: str = "/judge/semantic_equivalence"
    mcp_numeric_path: str = "/judge/numeric_tolerance"
    mcp_contradiction_path: str = "/judge/contradiction"
    mcp_health_path: str = "/health"
    mcp_version_path: str = "/version"

    @property
    def mcp_server_url(self) -> str:
        if self._mcp_server_url_override:
            return self._mcp_server_url_override.rstrip("/")
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}"

    @property
    def green_agent_url(self) -> str:
        if self._green_agent_url_override:
            return self._green_agent_url_override.rstrip("/")
        return f"http://{self.green_agent_host}:{self.green_agent_port}"

    @property
    def purple_agent_url(self) -> str:
        if self._purple_agent_url_override:
            return self._purple_agent_url_override.rstrip("/")
        return f"http://{self.purple_agent_host}:{self.purple_agent_port}"

    def get_judge_endpoints(self) -> Dict[str, str]:
        """Get all judge endpoint URLs."""
        base = self.mcp_server_url
        return {
            "semantic": f"{base}{self.mcp_semantic_path}",
            "numeric": f"{base}{self.mcp_numeric_path}",
            "contradiction": f"{base}{self.mcp_contradiction_path}",
            "health": f"{base}{self.mcp_health_path}",
            "version": f"{base}{self.mcp_version_path}",
        }


@dataclass
class PurpleAgentConfig:
    """Purple Agent mode configuration."""
    # Modes: "gold" (return gold answer), "llm" (generate with LLM), "adversarial" (return adversarial candidate)
    mode: str = os.getenv("PURPLE_AGENT_MODE", "gold")
    
    def validate(self):
        valid_modes = ["gold", "llm", "adversarial"]
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid PURPLE_AGENT_MODE: {self.mode}. Must be one of {valid_modes}")


# Global configuration instances
llm_config = LLMConfig()
scorer_config = ScorerConfig()
calibration_config = CalibrationConfig()
server_config = ServerConfig()
purple_agent_config = PurpleAgentConfig()


# Judge version strings (for audit trail)
JUDGE_VERSIONS = {
    "semantic": "semantic_v1.0.0",
    "numeric": "numeric_v1.1.0",  # Updated: confidence semantics + failure_reason field
    "contradiction": "contradiction_v1.1.0",  # Updated: exclude numeric mismatches from contradiction logic
}


def get_config_summary() -> Dict[str, Any]:
    """Get a summary of all configuration for manifest."""
    return {
        "llm": {
            "provider": llm_config.provider,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        },
        "scorer": scorer_config.to_dict(),
        "calibration": {
            "cv_folds": calibration_config.cv_folds,
            "cv_repeats": calibration_config.cv_repeats,
            "random_seed": calibration_config.random_seed,
        },
        "servers": {
            "mcp": server_config.mcp_server_url,
            "green_agent": server_config.green_agent_url,
            "purple_agent": server_config.purple_agent_url,
        },
        "purple_agent_mode": purple_agent_config.mode,
        "judge_versions": JUDGE_VERSIONS,
    }
