Multi-Agent Telemetry Root Cause Analysis (RCA) EngineAn automated SRE Incident Management and Root Cause Analysis system built on CrewAI, LangChain, and Pydantic. This engine orchestrates a sequential 4-agent pipeline to process time-series metrics from microservice architectures, classify fault mechanisms, trace causal propagation chains, and generate executive incident reports.   It includes built-in dataset ingestion for the RCAEval benchmark (phamquiluan/RCAEval) and an LLM-as-a-Judge evaluation harness to measure Top-1 accuracy and report actionability.   🏗 System ArchitectureThe engine uses a sequential agent workflow where each specialized agent performs targeted analysis and hands off structured Pydantic schemas to the next stage:                        ┌──────────────────────────────┐
                     │ Time-Series Metrics & Metadata│
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │ Metric Anomaly Specialist  │
                      └─────────────┬──────────────┘
                                    │ MetricAnomalyResult
                                    ▼
                      ┌────────────────────────────┐
                      │ Topology & Dependency Agent│
                      └─────────────┬──────────────┘
                                    │ TopologyAnalysisResult
                                    ▼
                      ┌────────────────────────────┐
                      │ Infrastructure Fault Agent │
                      └─────────────┬──────────────┘
                                    │ FaultClassificationResult
                                    ▼
                      ┌────────────────────────────┐
                      │ Incident Commander (RCA)   │
                      └─────────────┬──────────────┘
                                    │
                                    ▼
                             FinalRCAReport
Agents & Handoff SchemasMetric Anomaly Specialist (MetricAnomalyResult): Scans baseline vs post-injection metrics to identify anomalous shifts, statistical deviations, and timestamp windows.   Topology & Dependency Analyst (TopologyAnalysisResult): Traces downstream symptoms through dependency chains to isolate the upstream bottleneck microservice.   Infrastructure Fault Classifier (FaultClassificationResult): Classifies resource fault mechanisms (e.g., CPU burn, memory exhaustion, network delay, packet loss).   Incident Commander (FinalRCAReport): Synthesizes all multi-agent findings into an executive post-mortem report complete with actionable remediation steps.   📁 Repository Structure.
├── src/
│   ├── __init__.py
│   ├── agent.py         # RCAAgentOrchestrator & CrewAI 4-agent definition
│   ├── data_loader.py   # Ingests RCAEval datasets from HF & computes metric shifts
│   ├── evaluator.py    # Deterministic Top-1 match & LLM-as-a-Judge evaluator
│   ├── schemas.py      # Pydantic data models for agent handoffs & reports
│   └── service.py      # High-level RCAService wrapper for production integration
├── main.py              # Evaluation loop execution script across RE1/RE2/RE3 suites
├── requirements.txt     # Environment dependencies
└── README.md
⚡ Quick Start1. Prerequisites & Environment SetupEnsure you have Python 3.10+ installed. Clone the repository and install dependencies:Bashgit clone https://github.com/your-org/rca-agent-engine.git
cd rca-agent-engine

python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
2. Configure Environment VariablesSet your OpenAI API key for agent execution and evaluation:   Bashexport OPENAI_API_KEY="your-openai-api-key"
🚀 UsageRunning as a Production ServiceImport RCAService directly into your application, API endpoints, or SRE CLI tools:   Pythonfrom src.service import RCAService

# Initialize the production service
rca_service = RCAService(model_name="gpt-4o-mini")

metrics_data = """
=== METRIC ANOMALY SHIFT ANALYSIS (SPIKES & DROPS) ===
- ts-travel-service_cpu_utilization: baseline=12.40 -> post_spike=98.50 (SPIKE Δ=+86.10)
- ts-order-service_latency: baseline=120.00 -> post_spike=3500.00 (SPIKE Δ=+3380.00)
"""

metadata = {"inject_time": "2026-03-30 14:00:00"}

# Execute RCA Analysis
report = rca_service.analyze_incident(
    case_id="incident_001",
    metrics_summary=metrics_data,
    metadata=metadata,
)

print(f"Title: {report.incident_title}")
print(f"Fault Type: {report.identified_fault_type}")
print(f"Root Cause: {report.root_cause_summary}")
print(f"Affected Services: {report.affected_services}")
print(f"Mitigation: {report.recommended_mitigation}")
🧪 Benchmark EvaluationThe framework includes an automated evaluation harness designed for the RCAEval benchmark.   Running Benchmark CasesRun main.py to automatically download benchmark suites (re1, re2, re3), sample test cases, run multi-agent RCA, and score results:   Bashpython main.py
Customizing Evaluation SettingsIn main.py, you can configure suite sampling, case counts, and qualitative judging:   Pythonif __name__ == "__main__":
    run_evaluation(
        suites=["re1", "re2", "re3"], # Benchmark suites to evaluate
        cases_per_group=1,            # Number of random cases sampled per suite
        run_qualitative=True          # Enable LLM-as-a-Judge scoring (0-10)
    )
Evaluation OutputResults are saved to data/eval_results.json, tracking:   Top-1 Ground Truth Root Cause Match Rate (%)   LLM Judge RCA Accuracy Score (0-10)   LLM Judge Actionability Score (0-10)   Execution Latency per case   🛠 Features & RulesAutomated Metric Shift Processing: Computes pre-injection baseline versus post-injection spikes and drops, reducing token context usage while retaining telemetry signal quality.   Microservice Name Normalization: Automatically strips benchmark suite prefixes (e.g., re2tt_, re1ob_) while preserving microservice prefixes like ts- for TrainTicket microservices.   Deterministic & Qualitative Evaluation: Combines exact/token regex matching for root cause services with an LLM judge evaluating technical explanation quality and mitigation clarity
