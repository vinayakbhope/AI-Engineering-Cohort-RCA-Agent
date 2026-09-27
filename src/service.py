from typing import Any, Dict, Optional
from src.agent import RCAAgentOrchestrator
from src.schemas import FinalRCAReport


class RCAService:
    """Layer 1: Production Service Wrapper.

    Exposes a clean user entry point for live production incident management,
    webhooks, or SRE CLI tools without evaluation dependencies.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.orchestrator = RCAAgentOrchestrator(model_name=model_name)

    def analyze_incident(
        self,
        case_id: str,
        metrics_summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> FinalRCAReport:
        """Production entry method to execute RCA analysis on metric telemetry."""
        return self.orchestrator.analyze_incident(
            case_id=case_id,
            metrics_summary=metrics_summary,
            metadata=metadata,
        )