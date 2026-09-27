import os
import re
from langchain_openai import ChatOpenAI

from src.schemas import EvaluationScore, FinalRCAReport


class RCAEvaluator:
    """Evaluation engine for Root Cause Analysis (RCA) reports."""

    def __init__(self, judge_model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=judge_model,
            api_key=os.environ.get("OPENAI_API_KEY"),
        ).with_structured_output(EvaluationScore)

    @staticmethod
    def evaluate_top1_match(
        report: FinalRCAReport, ground_truth_service: str
    ) -> bool:
        """Deterministic evaluation: Checks if ground-truth service is present

        as an exact match in predicted affected services or as an isolated word token
        in root_cause_summary.
        """
        if not ground_truth_service or ground_truth_service.lower() == "unknown":
            return False

        gt_lower = ground_truth_service.lower().strip()
        predicted_services = [s.lower().strip() for s in report.affected_services]

        # 1. Exact list match
        if gt_lower in predicted_services:
            return True

        # 2. Strict word boundary search (prevents matching prefixes like re2tt_ts-train-service)
        pattern = r"(?<![\w\-])" + re.escape(gt_lower) + r"(?![\w\-])"
        return bool(re.search(pattern, report.root_cause_summary, re.IGNORECASE))

    def evaluate_qualitative(
            self,
            report: FinalRCAReport,
            ground_truth_service: str,
            fault_type: str,
    ) -> EvaluationScore:
        """LLM-as-a-Judge evaluation assessing RCA accuracy and actionability."""
        prompt = (
            f"You are an expert SRE benchmark evaluator. Evaluate the following Root Cause Analysis (RCA) report.\n\n"
            f"=== GROUND TRUTH ===\n"
            f"Root Cause Service: {ground_truth_service}\n"
            f"Fault Mechanism: {fault_type}\n\n"
            f"=== GENERATED RCA REPORT ===\n"
            f"Title: {report.incident_title}\n"
            f"Identified Fault Type: {report.identified_fault_type}\n"
            f"Summary: {report.root_cause_summary}\n"
            f"Affected Services: {', '.join(report.affected_services)}\n"
            f"Mitigation: {report.recommended_mitigation}\n\n"
            f"Rate the report from 0 to 10 on RCA Accuracy (did it correctly identify '{ground_truth_service}' and '{fault_type}') "
            f"and Actionability (are mitigations realistic and effective), and provide concise reasoning."
        )

        return self.llm.invoke(prompt)