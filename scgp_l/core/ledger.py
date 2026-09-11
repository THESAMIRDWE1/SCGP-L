"""Machine-readable provenance ledger.

Records all events with explicit layer labels.
Never overwrites raw observations.
Separates classifications and interpretations.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from .types import SessionRecord, RawObservation, ClassificationResult, AnalyticalInterpretation


class Ledger:
    """Machine-readable event log with layer separation."""
    
    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: List[Dict[str, Any]] = []
    
    def record_raw_observation(self, observation: RawObservation, session_id: str, agent_id: str) -> str:
        """Record Layer 1 raw observation.
        
        Returns: SHA256 hash of observation
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "raw_observation",
            "layer": "RAW_OBSERVATION",
            "session_id": session_id,
            "agent_id": agent_id,
            "data": observation.to_dict()
        }
        self.events.append(event)
        return self._hash_event(event)
    
    def record_classification(self, classification: ClassificationResult, session_id: str) -> str:
        """Record Layer 2 classification with explicit rule.
        
        Returns: SHA256 hash of classification
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "classification",
            "layer": "CLASSIFICATION",
            "session_id": session_id,
            "rule_name": classification.rule_name,
            "rule_definition": classification.rule_definition,
            "data": classification.to_dict()
        }
        self.events.append(event)
        return self._hash_event(event)
    
    def record_interpretation(self, interpretation: AnalyticalInterpretation, session_id: str) -> str:
        """Record Layer 3 interpretation (marked as INFERRED).
        
        Returns: SHA256 hash of interpretation
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "interpretation",
            "layer": "INTERPRETATION",
            "session_id": session_id,
            "marked_as": interpretation.marked_as,
            "confidence": interpretation.confidence,
            "data": interpretation.to_dict()
        }
        self.events.append(event)
        return self._hash_event(event)
    
    def write_session(self, session: SessionRecord):
        """Persist session with all layers separated."""
        output = {
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "problem_id": session.problem_id,
            "timestamp_generated": datetime.utcnow().isoformat(),
            
            "layer_1_raw_observations": [
                {"hash": self._hash_raw(o), "data": o.to_dict()}
                for o in session.raw_observations
            ],
            
            "layer_2_classifications": [
                {"hash": self._hash_classification(c), "data": c.to_dict()}
                for c in session.classifications
            ],
            
            "layer_3_interpretations": [
                {"hash": self._hash_interpretation(i), "data": i.to_dict()}
                for i in session.interpretations
            ],
            
            "agent_diagnoses": [
                d.to_dict() for d in session.agent_diagnoses
            ],
            
            "terminal_classification": session.terminal_classification,
            "terminal_confidence": session.terminal_confidence,
        }
        
        session_file = self.ledger_path / f"{session.session_id}.json"
        with open(session_file, 'w') as f:
            json.dump(output, f, indent=2)
    
    def write_all_events(self):
        """Persist all recorded events (for audit trail)."""
        events_file = self.ledger_path / "all_events.jsonl"
        with open(events_file, 'w') as f:
            for event in self.events:
                f.write(json.dumps(event) + "\n")
    
    @staticmethod
    def _hash_event(event: Dict[str, Any]) -> str:
        """SHA256 hash of event."""
        event_str = json.dumps(event, sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()
    
    @staticmethod
    def _hash_raw(obs: RawObservation) -> str:
        obs_str = json.dumps(obs.to_dict(), sort_keys=True)
        return hashlib.sha256(obs_str.encode()).hexdigest()
    
    @staticmethod
    def _hash_classification(c: ClassificationResult) -> str:
        c_str = json.dumps(c.to_dict(), sort_keys=True)
        return hashlib.sha256(c_str.encode()).hexdigest()
    
    @staticmethod
    def _hash_interpretation(i: AnalyticalInterpretation) -> str:
        i_str = json.dumps(i.to_dict(), sort_keys=True)
        return hashlib.sha256(i_str.encode()).hexdigest()
