"""Shared data types for SCGP-L.

All types explicitly marked with layer labels.
No semantic interpretation embedded in types.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import json
from datetime import datetime


class EpistemicLayer(Enum):
    """Explicit layer classification for all data."""
    RAW_OBSERVATION = "RAW_OBSERVATION"
    CLASSIFICATION = "CLASSIFICATION"
    INTERPRETATION = "INTERPRETATION"


class ExecutionStatus(Enum):
    """Raw execution outcomes (Layer 1)."""
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    CRASH = "CRASH"
    ERROR = "ERROR"


@dataclass
class RawObservation:
    """Single execution result (Layer 1: RAW_OBSERVATION).
    
    These are direct measurements only.
    No interpretation. Reproducible.
    """
    layer: EpistemicLayer = EpistemicLayer.RAW_OBSERVATION
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    input_value: str = ""
    target_output: str = ""
    candidate_output: str = ""
    
    exit_code_target: int = -1
    exit_code_candidate: int = -1
    
    wall_time_target_ms: float = 0.0
    wall_time_candidate_ms: float = 0.0
    
    output_bytes_match: bool = False
    exit_code_match: bool = False
    timed_out: bool = False
    crashed: bool = False
    
    stderr_target: str = ""
    stderr_candidate: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize with explicit layer label."""
        data = asdict(self)
        data['layer'] = self.layer.value
        return data


@dataclass
class ExecutionBatch:
    """Collection of raw observations (Layer 1)."""
    layer: EpistemicLayer = EpistemicLayer.RAW_OBSERVATION
    session_id: str = ""
    agent_id: str = ""
    iteration: int = -1
    candidate_sha256: str = ""
    batch_id: str = ""
    phase: str = ""  # "training" or "blind_execution"
    
    observations: List[RawObservation] = field(default_factory=list)
    input_set_sha256: str = ""  # Hash of all inputs in batch
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['layer'] = self.layer.value
        data['observations'] = [o.to_dict() for o in self.observations]
        return data


@dataclass
class ClassificationResult:
    """Applying experimental rule to observations (Layer 2: CLASSIFICATION)."""
    layer: EpistemicLayer = EpistemicLayer.CLASSIFICATION
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    rule_name: str = ""  # Name of experimental rule applied
    rule_definition: str = ""  # Exact rule definition
    
    observation_summary: Dict[str, Any] = field(default_factory=dict)
    rule_evaluated: bool = False
    rule_satisfied: bool = False
    classification: str = ""  # e.g., "PASS", "FAIL", "CONVERGED", "BLOCKED_ISOLATION"
    
    threshold_value: Optional[float] = None
    observed_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['layer'] = self.layer.value
        return data


@dataclass
class AnalyticalInterpretation:
    """Post-hoc analyst interpretation (Layer 3: INTERPRETATION).
    
    Explicitly marked as INFERRED. Never used as evidence.
    Requires independent testing to promote to Layer 2.
    """
    layer: EpistemicLayer = EpistemicLayer.INTERPRETATION
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    marked_as: str = "ANALYTICAL_HYPOTHESIS"  # or "INFERRED", "SPECULATIVE"
    confidence: str = "SPECULATIVE"  # or "LOW", "MEDIUM", "HIGH"
    
    supporting_observations: List[str] = field(default_factory=list)
    proposed_interpretation: str = ""
    alternative_explanations: List[str] = field(default_factory=list)
    
    validation_method: str = ""  # How to test this interpretation
    required_for_promotion: str = ""  # What would make this a Layer 2 classification
    
    not_valid_evidence_for: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['layer'] = self.layer.value
        return data


@dataclass
class AgentDiagnosis:
    """Optional agent commentary on failure (RECORDED BUT NOT ANALYZED).
    
    Agent may propose why hypothesis failed.
    System records it but does not:
      - Parse it
      - Validate it
      - Feed it to convergence analysis
      - Use it for evidence
    """
    agent_id: str = ""
    iteration: int = -1
    optional_diagnosis: str = ""  # Agent's optional commentary
    optional_confidence: str = "UNKNOWN"  # Agent's confidence in diagnosis
    reasoning: str = ""  # Agent's reasoning (optional, not analyzed)
    
    new_candidate_sha256: str = ""  # Hash of modified candidate
    new_candidate_source: str = ""  # Full source of new candidate
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConvergenceObservation:
    """Cross-agent convergence data (Layer 1: RAW_OBSERVATION).
    
    Records measured similarities. No interpretation.
    """
    layer: EpistemicLayer = EpistemicLayer.RAW_OBSERVATION
    
    agent_1_id: str = ""
    agent_2_id: str = ""
    
    agent_1_final_pass_rate: float = 0.0
    agent_2_final_pass_rate: float = 0.0
    pass_rate_difference: float = 0.0
    
    textual_similarity_score: float = 0.0
    common_substrings: List[str] = field(default_factory=list)
    
    output_equivalence_test_set: bool = False
    output_equivalence_holdout_set: bool = False
    output_equivalence_rate: float = 0.0
    
    transfer_pass_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['layer'] = self.layer.value
        return data


@dataclass
class SessionRecord:
    """Complete session for one agent (references all layers).
    
    Contains:
    - Raw observations (Layer 1)
    - Classifications (Layer 2)
    - Interpretations (Layer 3, separate section)
    """
    session_id: str = ""
    agent_id: str = ""
    problem_id: str = ""
    
    raw_observations: List[RawObservation] = field(default_factory=list)
    classifications: List[ClassificationResult] = field(default_factory=list)
    interpretations: List[AnalyticalInterpretation] = field(default_factory=list)
    agent_diagnoses: List[AgentDiagnosis] = field(default_factory=list)
    
    convergence_data: List[ConvergenceObservation] = field(default_factory=list)
    
    terminal_classification: str = "UNKNOWN_INSUFFICIENT_DATA"
    terminal_confidence: str = "LOW"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "problem_id": self.problem_id,
            "layer_1_raw_observations": [o.to_dict() for o in self.raw_observations],
            "layer_2_classifications": [c.to_dict() for c in self.classifications],
            "layer_3_interpretations": [i.to_dict() for i in self.interpretations],
            "agent_diagnoses": [d.to_dict() for d in self.agent_diagnoses],
            "convergence_data": [c.to_dict() for c in self.convergence_data],
            "terminal_classification": self.terminal_classification,
            "terminal_confidence": self.terminal_confidence,
        }
