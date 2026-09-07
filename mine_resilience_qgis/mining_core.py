"""Pure engineering-screening helpers used by the QGIS mining workflow."""

from __future__ import annotations

import html
import json
from pathlib import Path


def validate_score(value: float, label: str = "score") -> float:
    number = float(value)
    if not 1.0 <= number <= 5.0:
        raise ValueError(f"{label} must be between 1 and 5.")
    return number


def weighted_risk_score(hazard: float, terrain: float, criticality: float,
                        hazard_weight: float = 0.50, terrain_weight: float = 0.20,
                        criticality_weight: float = 0.30) -> float:
    values = [validate_score(hazard, "hazard"), validate_score(terrain, "terrain"),
              validate_score(criticality, "criticality")]
    weights = [float(hazard_weight), float(terrain_weight), float(criticality_weight)]
    if any(weight < 0 for weight in weights) or sum(weights) <= 0:
        raise ValueError("Risk weights must be non-negative and have a positive total.")
    return round(20.0 * sum(v * w for v, w in zip(values, weights)) / sum(weights), 2)


def risk_band(score: float) -> str:
    value = float(score)
    if not 0 <= value <= 100:
        raise ValueError("Risk score must be between 0 and 100.")
    if value >= 80:
        return "CRITICAL"
    if value >= 60:
        return "HIGH"
    if value >= 40:
        return "MODERATE"
    return "LOW"


def runoff_screening_volume(area_hectares: float, rainfall_mm: float,
                            runoff_coefficient: float) -> float:
    area = float(area_hectares)
    rainfall = float(rainfall_mm)
    coefficient = float(runoff_coefficient)
    if area < 0 or rainfall < 0 or not 0 <= coefficient <= 1:
        raise ValueError("Area/rainfall must be non-negative and runoff coefficient must be 0-1.")
    return round(area * 10_000.0 * rainfall / 1_000.0 * coefficient, 3)


def write_engineering_report(path: str | Path, summary: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in summary.items()
    )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Mine Resilience Screening Report</title>
<style>body{{font-family:Arial,sans-serif;margin:38px;color:#17212b}}h1{{color:#174d3b}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd4da;padding:9px;text-align:left}}
th{{width:34%;background:#edf4f1}}.warning{{padding:14px;background:#fff3cd;border-left:5px solid #d39e00}}
</style></head><body><h1>Mine Water &amp; Infrastructure Resilience</h1>
<p class="warning"><b>REVIEW REQUIRED.</b> Screening outputs are not final hydrologic,
hydraulic, geotechnical, TSF, culvert, flood, or operational design. Verify source data,
rainfall, runoff assumptions, asset criticality, geometry, and field conditions.</p>
<table>{rows}</table></body></html>"""
    target.write_text(document, encoding="utf-8")


def write_methodology(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
