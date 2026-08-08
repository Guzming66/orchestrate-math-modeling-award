#!/usr/bin/env python3
"""Score claim-engine benchmark runs and optionally compare two workflow versions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("benchmark result must be an object")
    return value


def score(document: dict[str, object]) -> dict[str, float]:
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark result has no cases")
    total_supported = sum(int(case.get("supported_claim_count", 0)) for case in cases if isinstance(case, dict))
    total_false = sum(int(case.get("false_innovation_count", 0)) for case in cases if isinstance(case, dict))
    denominator = max(1, total_supported + total_false)
    return {
        "supported_claims_per_case": total_supported / len(cases),
        "false_innovation_rate": total_false / denominator,
        "mean_component_count": sum(float(case.get("mean_component_count", 0)) for case in cases if isinstance(case, dict)) / len(cases),
        "baseline_gain_coverage": sum(float(case.get("baseline_gain_coverage", 0)) for case in cases if isinstance(case, dict)) / len(cases),
        "reproducibility_rate": sum(float(case.get("reproducibility_rate", 0)) for case in cases if isinstance(case, dict)) / len(cases),
        "paper_mapping_rate": sum(float(case.get("paper_mapping_rate", 0)) for case in cases if isinstance(case, dict)) / len(cases),
        "blind_quality_score": sum(float(case.get("blind_quality_score", 0)) for case in cases if isinstance(case, dict)) / len(cases),
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
