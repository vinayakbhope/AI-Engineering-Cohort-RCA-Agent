import json
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from huggingface_hub import snapshot_download
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class TelemetryDataLoader:
    """Ingests RCAEval benchmark telemetry from Hugging Face (phamquiluan/RCAEval)

    supporting multi-suite downloads (RE1, RE2, RE3), metric extraction,
    and metadata parsing.
    """

    HF_REPO_ID = "phamquiluan/RCAEval"
    INDEX_URL = "hf://datasets/phamquiluan/RCAEval/cases.parquet"

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index_df: Optional[pd.DataFrame] = None

    def get_cases_index(self) -> pd.DataFrame:
        """Fetches or loads the RCAEval cases index parquet file."""
        if self._index_df is not None:
            return self._index_df

        local_index = self.data_dir / "cases.parquet"
        if local_index.exists():
            self._index_df = pd.read_parquet(local_index)
        else:
            self._index_df = pd.read_parquet(self.INDEX_URL)
            self._index_df.to_parquet(local_index)

        return self._index_df

    def extract_archives(self) -> None:
        """Finds and extracts any zip or tar archives downloaded into data_dir."""
        for zip_path in self.data_dir.rglob("*.zip"):
            print(f"Extracting ZIP archive: {zip_path.name}")
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(self.data_dir)
                zip_path.unlink()
            except Exception as e:
                print(f"Failed to extract {zip_path}: {e}")

        for tar_path in self.data_dir.rglob("*.tar*"):
            print(f"Extracting TAR archive: {tar_path.name}")
            try:
                with tarfile.open(tar_path, "r:*") as tar_ref:
                    tar_ref.extractall(self.data_dir)
                tar_path.unlink()
            except Exception as e:
                print(f"Failed to extract {tar_path}: {e}")

    def download_suites(self, suite_patterns: List[str] = ["re1*", "re2*", "re3*"]) -> Path:
        """Downloads multiple benchmark suites (RE1, RE2, RE3) from Hugging Face."""
        allow_patterns = ["cases.parquet"]
        for p in suite_patterns:
            clean = p.rstrip("*")
            allow_patterns.extend([
                f"{clean}*",
                f"{clean}*/**",
                f"**/{clean}*",
                f"**/{clean}*/**",
                f"*.tar.gz",
                f"*.zip",
            ])

        print(f"Downloading dataset patterns {suite_patterns} from HF repo '{self.HF_REPO_ID}'...")
        downloaded_path = snapshot_download(
            repo_id=self.HF_REPO_ID,
            repo_type="dataset",
            allow_patterns=allow_patterns,
            local_dir=str(self.data_dir),
            local_dir_use_symlinks=False,
        )

        self.extract_archives()
        return Path(downloaded_path)

    def load_telemetry_for_case(
        self, case_folder: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Loads time-series metrics and metadata for a given RCAEval case."""
        target_path = self.data_dir / case_folder

        if not target_path.exists():
            matches = list(self.data_dir.rglob(Path(case_folder).name))
            if matches:
                target_path = matches[0]

        metrics_str = ""
        metadata = {"case": case_folder}

        if target_path.exists() and target_path.is_dir():
            for f in target_path.rglob("*"):
                if not f.is_file():
                    continue

                fname = f.name.lower()

                if "inject_time" in fname and f.suffix == ".txt":
                    metadata["inject_time"] = f.read_text(encoding="utf-8").strip()

                elif "metric" in fname or f.suffix in [".parquet", ".csv"]:
                    df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)

                    numeric_cols = df.select_dtypes(include=["number"]).columns
                    if not numeric_cols.empty and len(df) > 2:
                        midpoint = len(df) // 2
                        pre_df = df.iloc[:midpoint]
                        post_df = df.iloc[midpoint:]

                        metrics_delta = []
                        for col in numeric_cols:
                            pre_vals = pre_df[col].dropna()
                            post_vals = post_df[col].dropna()

                            if pre_vals.empty or post_vals.empty:
                                continue

                            pre_mean = float(pre_vals.mean())
                            post_max = float(post_vals.max())
                            post_min = float(post_vals.min())

                            if pd.isna(pre_mean) or pd.isna(post_max) or pd.isna(post_min):
                                continue

                            spike_delta = post_max - pre_mean
                            drop_delta = post_min - pre_mean

                            if abs(spike_delta) >= abs(drop_delta):
                                max_delta = spike_delta
                                post_val = post_max
                                change_type = "SPIKE"
                            else:
                                max_delta = drop_delta
                                post_val = post_min
                                change_type = "DROP"

                            metrics_delta.append({
                                "col": col,
                                "pre_mean": pre_mean,
                                "post_val": post_val,
                                "delta": max_delta,
                                "abs_delta": abs(max_delta),
                                "type": change_type
                            })

                        # Rank by absolute magnitude of change (spike or drop)
                        if metrics_delta:
                            df_deltas = pd.DataFrame(metrics_delta).sort_values(by="abs_delta", ascending=False)

                            summary_lines = []
                            for _, row in df_deltas.head(50).iterrows():
                                if row["abs_delta"] > 0.001:
                                    summary_lines.append(
                                        f"- {row['col']}: baseline={row['pre_mean']:.2f} -> post_{row['type'].lower()}={row['post_val']:.2f} "
                                        f"({row['type']} Δ={row['delta']:+.2f})"
                                    )

                            metrics_str = "=== METRIC ANOMALY SHIFT ANALYSIS (SPIKES & DROPS) ===\n" + "\n".join(summary_lines)
                        else:
                            metrics_str = f"=== PROMETHEUS METRICS TELEMETRY ===\n{df.to_string(index=False, max_cols=None, line_width=10000)}"
                    else:
                        metrics_str = f"=== PROMETHEUS METRICS TELEMETRY ===\n{df.to_string(index=False, max_cols=None, line_width=10000)}"

            if metrics_str:
                return metrics_str, metadata

        return (
            f"[NO METRIC TELEMETRY FOUND FOR CASE: {case_folder}]",
            metadata,
        )