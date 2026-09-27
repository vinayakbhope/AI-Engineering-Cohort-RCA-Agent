import json
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.data_loader import TelemetryDataLoader
from src.evaluator import RCAEvaluator
from src.schemas import FinalRCAReport
from src.service import RCAService


def run_evaluation(
    suites: List[str] = ["re1", "re2", "re3"],
    cases_per_group: int = 1,
    run_qualitative: bool = False,
):
    """Layer 3: Evaluation Harness & Benchmark Engine.

    Downloads RE1, RE2, and RE3 benchmark patterns, samples cases, and executes evaluation.
    """
    print("=== Starting Decoupled RCA Agent Evaluation Loop ===")

    loader = TelemetryDataLoader()
    rca_service = RCAService()
    evaluator = RCAEvaluator()

    # 1. Download RE1, RE2, RE3 test suite patterns
    download_patterns = [f"{s}*" for s in suites]
    loader.download_suites(download_patterns)

    # 2. Get cases index
    df_cases = loader.get_cases_index()
    print(f"Total benchmark cases available in index: {len(df_cases)}")

    # 3. Randomly sample 'cases_per_group' cases from each suite group (re1, re2, re3)
    selected_rows = []
    for suite_prefix in suites:
        group = df_cases[df_cases["case"].str.startswith(suite_prefix)]
        if not group.empty:
            sampled = group.sample(n=min(cases_per_group, len(group)))
            selected_rows.append(sampled)
            print(f"Sampled {len(sampled)} random case(s) from group '{suite_prefix}' (total available: {len(group)})")
        else:
            print(f"⚠️ No cases found matching prefix '{suite_prefix}'")

    if not selected_rows:
        print("No cases selected for evaluation.")
        return

    test_subset = pd.concat(selected_rows, ignore_index=True)
    results = []

    # 4. Evaluation Loop
    for idx, (_, row) in enumerate(test_subset.iterrows()):
        case_id = str(row.get("case", f"case_{idx}"))

        ground_truth_service = str(
            row.get("root_cause_service")
            or row.get("ground_truth_root_cause_service")
            or "Unknown"
        )
        fault_type = str(row.get("fault", "Unknown"))

        print(f"\n--------------------------------------------------")
        print(f"[{idx + 1}/{len(test_subset)}] Evaluating Case: {case_id}")
        print(f"Ground Truth Service: {ground_truth_service} | Fault: {fault_type}")
        print(f"--------------------------------------------------")

        # Load telemetry for case
        metrics_summary, meta = loader.load_telemetry_for_case(case_id)

        start_time = time.time()

        try:
            report: FinalRCAReport = rca_service.analyze_incident(
                case_id=case_id,
                metrics_summary=metrics_summary,  # Guardrail token context limit
                metadata=meta,
            )

            elapsed = time.time() - start_time

            is_match = evaluator.evaluate_top1_match(
                report=report, ground_truth_service=ground_truth_service
            )

            eval_scores = None
            if run_qualitative:
                eval_scores = evaluator.evaluate_qualitative(
                    report=report,
                    ground_truth_service=ground_truth_service,
                    fault_type=fault_type,
                )

            print("\n[Generated Report Summary]")
            print(f"Title: {report.incident_title}")
            # Display identified fault type if present in the schema
            if hasattr(report, "identified_fault_type"):
                print(f"Identified Fault: {report.identified_fault_type}")
            print(f"Affected Services: {', '.join(report.affected_services)}")
            print(f"Top-1 Ground Truth Match ({ground_truth_service}): {'✅ YES' if is_match else '❌ NO'}")
            print(f"Execution Time: {elapsed:.2f}s")

            res_dict = {
                "case_id": case_id,
                "ground_truth_service": ground_truth_service,
                "fault_type": fault_type,
                "predicted_services": report.affected_services,
                "is_match": is_match,
                "execution_time_sec": elapsed,
                "report": report.model_dump(),
            }
            if eval_scores:
                res_dict["qualitative_score"] = eval_scores.model_dump()

            results.append(res_dict)

        except Exception as e:
            print(f"❌ Error processing case {case_id}: {e}")

    # 5. Summary Report (Executed ONLY ONCE after the loop finishes)
    if results:
        accuracy = (sum(1 for r in results if r["is_match"]) / len(results)) * 100
        qual_scores = [r["qualitative_score"] for r in results if "qualitative_score" in r]

        print(f"\n==================================================")
        print(f"EVALUATION SUMMARY REPORT")
        print(f"==================================================")
        print(f"Processed Cases: {len(results)}")
        print(f"Top-1 Root Cause Match Rate: {accuracy:.1f}%")

        if qual_scores:
            avg_rca = sum(q["rca_accuracy_score"] for q in qual_scores) / len(qual_scores)
            avg_action = sum(q["actionability_score"] for q in qual_scores) / len(qual_scores)

            print(f"Avg Judge RCA Accuracy:     {avg_rca:.2f} / 10")
            print(f"Avg Judge Actionability:    {avg_action:.2f} / 10")
            print(f"--------------------------------------------------")
            print("QUALITATIVE FEEDBACK BREAKDOWN:")

            for r in results:
                if "qualitative_score" in r:
                    qs = r["qualitative_score"]
                    print(f"\n• Case ID: {r['case_id']}")
                    print(f"  Scores: RCA Accuracy={qs['rca_accuracy_score']}/10 | Actionability={qs['actionability_score']}/10")
                    print(f"  Judge Reasoning:\n    {qs['reasoning']}")

        print(f"==================================================")

        output_path = Path("data/eval_results.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))
        print(f"Saved benchmark results to {output_path}\n")


if __name__ == "__main__":
    run_evaluation(suites=["re1", "re2", "re3"], cases_per_group=1, run_qualitative=True)