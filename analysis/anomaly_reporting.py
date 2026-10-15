"""Anomaly Reporting - Formatting clean summaries for Phase 5 insights and executive reports."""

from typing import Dict, Any, List, Optional, Union
from models.anomaly import CombinedAnomalyResult


def generate_phase5_anomaly_summary(
    anomaly_results: Union[CombinedAnomalyResult, Dict[str, Any]],
    dataset_name: str = "dataset.csv",
) -> Dict[str, Any]:
    """Expose clean, structured summary for Phase 5 insight generator consumption.

    Guarantees:
    - Phase 5 can consume this directly without rerunning anomaly detection.
    """
    if isinstance(anomaly_results, CombinedAnomalyResult):
        return {
            "dataset": anomaly_results.dataset_name,
            "anomaly_count": anomaly_results.anomaly_count,
            "anomaly_percentage": anomaly_results.anomaly_percentage,
            "affected_columns": anomaly_results.affected_columns,
            "methods": anomaly_results.methods_used,
            "severity_breakdown": anomaly_results.severity_breakdown,
            "total_rows": anomaly_results.total_rows,
        }

    if isinstance(anomaly_results, dict):
        summary = anomaly_results.get("summary", {})
        return {
            "dataset": anomaly_results.get("dataset", dataset_name),
            "anomaly_count": summary.get("anomaly_count", anomaly_results.get("anomaly_count", 0)),
            "anomaly_percentage": summary.get("anomaly_percentage", anomaly_results.get("anomaly_percentage", 0.0)),
            "affected_columns": anomaly_results.get("affected_columns", []),
            "methods": anomaly_results.get("methods", []),
            "severity_breakdown": anomaly_results.get("severity_breakdown", {}),
            "total_rows": anomaly_results.get("rows", anomaly_results.get("total_rows", 0)),
        }

    return {
        "dataset": dataset_name,
        "anomaly_count": 0,
        "anomaly_percentage": 0.0,
        "affected_columns": [],
        "methods": [],
        "severity_breakdown": {},
        "total_rows": 0,
    }


def generate_report_anomaly_section(
    anomaly_results: Union[CombinedAnomalyResult, Dict[str, Any]],
    dataset_name: str = "dataset.csv",
) -> str:
    """Format markdown section for inclusion in comprehensive analytical reports."""
    summary = generate_phase5_anomaly_summary(anomaly_results, dataset_name)
    lines = [
        f"### Statistical Anomaly & Outlier Assessment: {summary['dataset']}",
        "",
        f"- **Evaluated Records:** {summary.get('total_rows', 0):,}",
        f"- **Flagged Anomalies:** {summary['anomaly_count']:,} ({summary['anomaly_percentage']:.2f}% of dataset)",
        f"- **Detection Methods:** {', '.join(summary['methods']) if summary['methods'] else 'None'}",
        f"- **Affected Numerical Attributes:** {', '.join(summary['affected_columns']) if summary['affected_columns'] else 'None'}",
    ]

    sev = summary.get("severity_breakdown", {})
    if sev:
        lines.append(f"- **Severity Breakdown:** High: {sev.get('HIGH', 0)}, Medium: {sev.get('MEDIUM', 0)}, Low: {sev.get('LOW', 0)}")

    lines.extend([
        "",
        "> **Governance Policy:** Flagged records are statistical outliers, not confirmed invalid data. Original data is permanently preserved.",
        "",
    ])

    return "\n".join(lines)
