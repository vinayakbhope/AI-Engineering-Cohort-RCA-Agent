from typing import List, Optional
from pydantic import BaseModel, Field

# =====================================================================
# AGENT INTERMEDIATE HANDOFF SCHEMAS (METRIC-FOCUSED FOR RCAEVAL)
# =====================================================================

class MetricAnomalyResult(BaseModel):
    """Output schema for the Metric Anomaly Specialist Agent."""
    primary_error_service: str = Field(
        description="Microservice where metric anomaly or spike first originated"
    )
    anomaly_summary: str = Field(
        description="Summary of metric statistical deviations (CPU, memory, latency spikes)"
    )
    anomaly_timestamp: str = Field(
        description="Estimated timestamp or time window of initial metric anomaly"
    )

class TopologyAnalysisResult(BaseModel):
    """Output schema for the Topology & Dependency Analyst Agent."""
    failing_component_chain: List[str] = Field(
        description="Sequential list of services in failure propagation chain"
    )
    bottleneck_service: str = Field(
        description="Upstream microservice identified as the primary failure root cause"
    )

class FaultClassificationResult(BaseModel):
    """Output schema for the Infrastructure Fault Classifier Agent."""
    fault_type: str = Field(
        description="Identified fault mechanism (e.g., CPU hog, memory leak, network delay, packet loss)"
    )
    affected_resource: str = Field(
        description="Resource or subsystem impacted (e.g., node CPU, pod memory, network interface)"
    )
    fault_evidence: str = Field(
        description="Metric values and evidence supporting the fault classification"
    )

# =====================================================================
# FINAL EXECUTIVE REPORT SCHEMA
# =====================================================================

class FinalRCAReport(BaseModel):
    """Output schema for the Incident Commander (RCA Synthesizer Agent)."""
    incident_title: str = Field(
        description="Concise executive title describing the incident"
    )
    identified_fault_type: str = Field(
        description="Exact root cause fault mechanism (e.g., disk, CPU burn, memory leak, network delay, packet loss)"
    )
    root_cause_summary: str = Field(
        description="Detailed technical post-mortem explanation of the fault propagation"
    )
    culprit_commit: Optional[str] = Field(
        default="N/A (Chaos Injected Metric Fault)",
        description="Commit hash or chaos injection event description"
    )
    affected_services: List[str] = Field(
        description="List of all impacted downstream services"
    )
    recommended_mitigation: str = Field(
        description="Immediate actionable remediation steps (e.g., pod restart, resource limit adjustment)"
    )

# =====================================================================
# EVALUATION HARNESS SCHEMAS
# =====================================================================

class EvaluationScore(BaseModel):
    """Individual system evaluation metrics scored by LLM-as-a-Judge."""
    rca_accuracy_score: int = Field(
        description="Score from 0 to 10 on correctly identifying root cause service and mechanism"
    )
    actionability_score: int = Field(
        description="Score from 0 to 10 on clarity and effectiveness of mitigation steps"
    )
    reasoning: str = Field(
        description="Detailed justification for assigned scores"
    )

class DualEval(BaseModel):
    """Comparative evaluation payload for Baseline vs Multi-Agent graph."""
    system_a_eval: EvaluationScore = Field(description="Evaluation for Naive Single-Prompt Baseline")
    system_b_eval: EvaluationScore = Field(description="Evaluation for Multi-Agent Graph System")