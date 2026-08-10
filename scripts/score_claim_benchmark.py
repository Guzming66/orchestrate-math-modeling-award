#!/usr/bin/env python3
"""Score claim-engine benchmark runs and optionally compare two workflow versions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CASE_METRICS = (
    "supported_claim_count",
    "false_innovation_count",
    "mean_component_count",
    "baseline_gain_coverage",
    "reproducibility_rate",
    "paper_mapping_rate",
    "paper_meta_language_rate",
    "adaptive_review_accuracy",
    "implementation_gap_detection_rate",
    "presentation_blind_score",
    "blind_quality_score",
)
RATE_METRICS = {
    "baseline_gain_coverage",
    "reproducibility_rate",
    "paper_mapping_rate",
    "paper_meta_language_rate",
    "adaptive_review_accuracy",
    "implementation_gap_detection_rate",
}
SCORE_METRICS = {"presentation_blind_score", "blind_quality_score"}


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("benchmark result must be an object")
    return value


def score(document: dict[str, object]) -> dict[str, float]:
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark result has no cases")
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"benchmark case {index} is not an object")
        missing = [metric for metric in CASE_METRICS if metric not in case]
        if missing:
            raise ValueError(f"benchmark case {index} is missing metrics: {', '.join(missing)}")
        for metric in CASE_METRICS:
            try:
                value = float(case[metric])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"benchmark case {index} has non-numeric {metric}") from exc
            if value < 0:
                raise ValueError(f"benchmark case {index} has negative {metric}")
            if metric in RATE_METRICS and value > 1:
                raise ValueError(f"benchmark case {index} has rate outside [0, 1]: {metric}")
            if metric in SCORE_METRICS and not 1 <= value <= 5:
                raise ValueError(f"benchmark case {index} has score outside [1, 5]: {metric}")
    total_supported = sum(int(case["supported_claim_count"]) for case in cases)
    total_false = sum(int(case["false_innovation_count"]) for case in cases)
    denominator = max(1, total_supported + total_false)
    return {
        "supported_claims_per_case": total_supported / len(cases),
        "false_innovation_rate": total_false / denominator,
        "mean_component_count": sum(float(case["mean_component_count"]) for case in cases) / len(cases),
        "baseline_gain_coverage": sum(float(case["baseline_gain_coverage"]) for case in cases) / len(cases),
        "reproducibility_rate": sum(float(case["reproducibility_rate"]) for case in cases) / len(cases),
        "paper_mapping_rate": sum(float(case["paper_mapping_rate"]) for case in cases) / len(cases),
        "paper_meta_language_rate": sum(float(case["paper_meta_language_rate"]) for case in cases) / len(cases),
        "adaptive_review_accuracy": sum(float(case["adaptive_review_accuracy"]) for case in cases) / len(cases),
        "implementation_gap_detection_rate": sum(float(case["implementation_gap_detection_rate"]) for case in cases) / len(cases),
        "presentation_blind_score": sum(float(case["presentation_blind_score"]) for case in cases) / len(cases),
        "blind_quality_score": sum(float(case["blind_quality_score"]) for case in cases) / len(cases),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score innovation-claim benchmark results.")
    parser.add_argument("results")
    parser.add_argument("--compare")
    args = parser.parse_args()
    current = score(load(Path(args.results)))
    output: dict[str, object] = {"current": current}
    if args.compare:
        baseline = score(load(Path(args.compare)))
        output["baseline"] = baseline
        output["delta"] = {key: current[key] - baseline[key] for key in current}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
