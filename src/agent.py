import json
import os
from typing import Any, Dict, Optional

from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from src.schemas import (
    FaultClassificationResult,
    FinalRCAReport,
    MetricAnomalyResult,
    TopologyAnalysisResult,
)

NORMALIZATION_RULE = (
    "\nCRITICAL: Always normalize service names by removing dataset folder prefixes (e.g., 're2tt_', 're1ob_') and fault suffixes.\n"
    "IMPORTANT REGARDING 'ts-' SERVICES: Do NOT strip the 'ts-' prefix from TrainTicket microservices. "
    "'ts-' is part of the microservice name itself (e.g., 'ts-travel-service', 'ts-train-service', 'ts-order-service'). "
    "Stripping 'ts-' to output 'travel-service' is INCORRECT; keep 'ts-travel-service' intact."
)


class RCAAgentOrchestrator:
    """Multi-agent orchestrator for Root Cause Analysis (RCA) on metric telemetry.

    Implements a 4-agent sequential pipeline using CrewAI and Pydantic
    structured handoffs tailored for time-series metric analysis.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

    def _create_agents(self) -> tuple[Agent, Agent, Agent, Agent]:
        metric_analyst = Agent(
            role="Metric Anomaly Specialist",
            goal=(
                "Scan time-series metric data to detect statistical deviations,"
                " CPU/memory spikes, or latency jumps and isolate candidate services."
                + NORMALIZATION_RULE
            ),
            backstory=(
                "You are an expert SRE metric analyst specializing in Prometheus time-series."
                " You identify exact timestamps when metrics diverge from baseline."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        topology_analyst = Agent(
            role="Topology & Dependency Analyst",
            goal=(
                "Analyze service latency correlations and dependency chains to identify"
                " the root upstream bottleneck service."
                + NORMALIZATION_RULE
            ),
            backstory=(
                "You specialize in microservice dependency graphs and failure propagation."
                " You trace downstream symptoms back to upstream root cause components."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        fault_classifier = Agent(
            role="Infrastructure Fault Classifier",
            goal=(
                "Classify the exact fault mechanism (CPU hog, memory leak, network delay/loss)"
                " based on resource telemetry signatures."
            ),
            backstory=(
                "You are an SRE chaos engineering analyst. You recognize exact metric"
                " signatures corresponding to resource starvation or network faults."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        rca_synthesizer = Agent(
            role="Incident Commander",
            goal=(
                "Synthesize findings from Metric, Topology, and Fault Classifier agents"
                " into an executive Root Cause Analysis report."
                + NORMALIZATION_RULE
            ),
            backstory=(
                "You are the Lead Incident Commander. You compile granular metric evidence"
                " into structured post-mortem reports with clear, actionable mitigations."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        return metric_analyst, topology_analyst, fault_classifier, rca_synthesizer

    def analyze_incident(
        self,
        case_id: str,
        metrics_summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FinalRCAReport:
        """Executes the sequential 4-agent pipeline with structured Pydantic handoffs."""
        metric_analyst, topology_analyst, fault_classifier, rca_synthesizer = (
            self._create_agents()
        )

        inject_time = metadata.get("inject_time", "Unknown") if metadata else "Unknown"

        # Step 1: Metric Anomaly Detection Task
        metric_task = Task(
            description=(
                f"Analyze metrics telemetry for case '{case_id}' (Fault injected around: {inject_time}).\n"
                f"Identify initial anomalous service, metric spike, and timestamp.\n"
                f"Ensure all extracted service names are clean canonical names without case prefixes (e.g., retain 'ts-travel-service').\n\n"
                f"=== METRICS TELEMETRY ===\n{metrics_summary}"
            ),
            expected_output="Structured MetricAnomalyResult containing primary error service, anomaly summary, and timestamp.",
            agent=metric_analyst,
            output_pydantic=MetricAnomalyResult,
        )

        # Step 2: Topology & Causal Propagation Task
        topology_task = Task(
            description=(
                "Using the anomaly detection findings, analyze service dependency correlations"
                " and identify the upstream root cause bottleneck service."
            ),
            expected_output="Structured TopologyAnalysisResult containing failing component chain and bottleneck service.",
            agent=topology_analyst,
            context=[metric_task],
            output_pydantic=TopologyAnalysisResult,
        )

        # Step 3: Fault Classification Task
        fault_task = Task(
            description=(
                "Analyze the metric signatures of the bottleneck service to classify the precise"
                " fault mechanism (e.g., CPU burn, memory exhaustion, network delay, packet loss)."
            ),
            expected_output="Structured FaultClassificationResult containing fault_type, affected_resource, and fault_evidence.",
            agent=fault_classifier,
            context=[topology_task],
            output_pydantic=FaultClassificationResult,
        )

        # Step 4: Final Synthesis Task
        synthesis_task = Task(
            description=(
                "Synthesize findings from the Metric, Topology, and Fault Classifier agents into"
                " a final executive Root Cause Analysis (RCA) Incident Report.\n"
                "CRITICAL:\n"
                "1. Ensure 'identified_fault_type' explicitly captures the exact mechanism identified by the Fault Classifier (e.g., 'disk', 'CPU burn', 'network delay').\n"
                "2. Ensure all entries in 'affected_services' use clean canonical microservice names (e.g., 'ts-travel-service' instead of 're2tt_ts-travel-service' or 'travel-service'). Do NOT strip 'ts-'!"
            ),
            expected_output="Structured FinalRCAReport containing incident_title, identified_fault_type, root_cause_summary, affected_services, and recommended_mitigation.",
            agent=rca_synthesizer,
            context=[metric_task, topology_task, fault_task],
            output_pydantic=FinalRCAReport,
        )

        crew = Crew(
            agents=[metric_analyst, topology_analyst, fault_classifier, rca_synthesizer],
            tasks=[metric_task, topology_task, fault_task, synthesis_task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()

        if result.pydantic:
            return result.pydantic

        if synthesis_task.output and synthesis_task.output.pydantic:
            return synthesis_task.output.pydantic

        raise ValueError("The RCA Synthesizer agent failed to produce a valid FinalRCAReport payload.")