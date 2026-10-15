"""Anomaly Scoring - Multi-method combination, agreement calculation, and severity classification."""

from typing import Dict, Any, List, Optional, Tuple, Union, Set
from collections import defaultdict
import numpy as np
import pandas as pd

from models.anomaly import (
    IQRAnalysisResult,
    IsolationForestResult,
    ZScoreAnalysisResult,
    RobustZScoreAnalysisResult,
    MultivariateAnalysisResult,
    SingleAnomalyRecord,
    CombinedAnomalyResult,
)


def calculate_anomaly_severity(
    score: float,
    methods_agreeing: int,
    total_methods: int,
    affected_columns: List[str],
    max_z: float = 0.0,
    has_iqr_outlier: bool = False,
) -> Tuple[str, List[str]]:
    """Determine transparent severity classification (LOW, MEDIUM, HIGH) with documented evidence signals.

    Rules:
    - HIGH:
      * 3 or more methods agree, OR
      * 2 or more methods agree with high score (>= 0.70) or extreme Z-score (|z| >= 4.0), OR
      * Multiple columns affected (>= 2) with significant deviations.
    - MEDIUM:
      * 2 methods agree, OR
      * 1 method with notable deviation (score >= 0.50 or |z| >= 3.5), OR
      * Both IQR bounds violated and high isolation tree partition rate.
    - LOW:
      * 1 method identifying borderline deviation (score < 0.50 and |z| < 3.5).
    """
    signals = []

    # Agreement signals
    if methods_agreeing >= 3:
        signals.append(f"Strong consensus: {methods_agreeing} of {total_methods} detection algorithms flagged this record")
    elif methods_agreeing == 2:
        signals.append(f"Dual-algorithm consensus: 2 of {total_methods} algorithms flagged this record")
    else:
        signals.append(f"Single algorithm signal ({methods_agreeing} of {total_methods} evaluated)")

    # Magnitude signals
    if max_z >= 4.0:
        signals.append(f"Extreme statistical dispersion: observation deviates by {max_z:.2f} standard deviations")
    elif max_z >= 3.0:
        signals.append(f"Notable statistical deviation: Z-score is {max_z:.2f}")

    if len(affected_columns) > 1:
        signals.append(f"Cross-feature impact: {len(affected_columns)} columns affected ({', '.join(affected_columns)})")

    if score >= 0.75:
        signals.append(f"High isolation certainty score: {score:.3f}")

    # Determine level
    if methods_agreeing >= 3 or (methods_agreeing >= 2 and (score >= 0.70 or max_z >= 4.0 or len(affected_columns) >= 2)):
        severity = "HIGH"
    elif methods_agreeing == 2 or score >= 0.50 or max_z >= 3.5 or len(affected_columns) >= 2:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return severity, signals


def combine_anomaly_results(
    results: Dict[str, Any],
    df: pd.DataFrame,
    dataset_name: str = "dataset",
) -> CombinedAnomalyResult:
    """Aggregate individual method outputs into a standardized composite anomaly container.

    Supported methods inside results dict:
    - 'iqr': IQRAnalysisResult or dict
    - 'z_score': ZScoreAnalysisResult or dict
    - 'robust_z_score': RobustZScoreAnalysisResult or dict
    - 'isolation_forest': IsolationForestResult or dict
    - 'multivariate': MultivariateAnalysisResult or dict
    """
    if df is None:
        raise ValueError("Cannot combine anomaly results on a None DataFrame.")

    total_rows = len(df)
    methods_present = []
    features_used_set: Set[str] = set()

    # Per-row tracking map: row_idx -> dict of info
    # row_data[row_idx] = {
    #   'methods': set(),
    #   'columns': set(),
    #   'scores': [],
    #   'signals': [],
    #   'expected_ranges': {},
    #   'deviations': {},
    #   'max_z': 0.0,
    # }
    row_data: Dict[Any, Dict[str, Any]] = defaultdict(lambda: {
        "methods": set(),
        "columns": set(),
        "scores": [],
        "signals": [],
        "expected_ranges": {},
        "deviations": {},
        "max_z": 0.0,
        "has_iqr": False,
    })

    # 1. Process IQR results
    iqr_res = results.get("iqr")
    if iqr_res:
        methods_present.append("IQR")
        col_res_dict = getattr(iqr_res, "column_results", {})
        if isinstance(col_res_dict, dict):
            for col, cr in col_res_dict.items():
                features_used_set.add(col)
                outlier_indices = getattr(cr, "outlier_indices", [])
                l_bound = getattr(cr, "lower_bound", 0.0)
                u_bound = getattr(cr, "upper_bound", 0.0)
                for r_idx in outlier_indices:
                    if r_idx in df.index:
                        val = df.loc[r_idx, col]
                        row_data[r_idx]["methods"].add("IQR")
                        row_data[r_idx]["columns"].add(col)
                        row_data[r_idx]["has_iqr"] = True
                        row_data[r_idx]["expected_ranges"][col] = f"[{l_bound:,.2f}, {u_bound:,.2f}]"
                        if val > u_bound:
                            dev = val - u_bound
                            row_data[r_idx]["deviations"][col] = f"+{dev:,.2f} above upper bound"
                            row_data[r_idx]["signals"].append(f"'{col}' ({val:,.2f}) exceeds IQR upper bound ({u_bound:,.2f}) by {dev:,.2f}")
                        elif val < l_bound:
                            dev = l_bound - val
                            row_data[r_idx]["deviations"][col] = f"-{dev:,.2f} below lower bound"
                            row_data[r_idx]["signals"].append(f"'{col}' ({val:,.2f}) is below IQR lower bound ({l_bound:,.2f}) by {dev:,.2f}")
                        row_data[r_idx]["scores"].append(0.55)

    # 2. Process Z-Score results
    z_res = results.get("z_score")
    if z_res:
        methods_present.append("Z-Score")
        col_res_dict = getattr(z_res, "column_results", {})
        if isinstance(col_res_dict, dict):
            for col, zr in col_res_dict.items():
                features_used_set.add(col)
                outlier_indices = getattr(zr, "outlier_indices", [])
                mean_v = getattr(zr, "mean", 0.0)
                std_v = getattr(zr, "std", 1.0)
                thresh = getattr(zr, "threshold", 3.0)
                for r_idx in outlier_indices:
                    if r_idx in df.index:
                        val = df.loc[r_idx, col]
                        z_val = abs((val - mean_v) / std_v) if std_v > 1e-9 else 0.0
                        row_data[r_idx]["methods"].add("Z-Score")
                        row_data[r_idx]["columns"].add(col)
                        row_data[r_idx]["max_z"] = max(row_data[r_idx]["max_z"], z_val)
                        norm_score = min(1.0, 0.4 + (z_val - thresh) * 0.15)
                        row_data[r_idx]["scores"].append(norm_score)
                        row_data[r_idx]["signals"].append(f"'{col}' Z-score is {z_val:.2f}σ (|z| > {thresh})")
                        row_data[r_idx]["expected_ranges"][col] = f"[{mean_v - thresh * std_v:,.2f}, {mean_v + thresh * std_v:,.2f}]"
                        dev_dist = (val - mean_v)
                        row_data[r_idx]["deviations"][col] = f"{dev_dist:+,.2f} from mean ({z_val:.2f}σ)"

    # 3. Process Robust Z-Score results
    rz_res = results.get("robust_z_score")
    if rz_res:
        methods_present.append("Robust Z-Score")
        col_res_dict = getattr(rz_res, "column_results", {})
        if isinstance(col_res_dict, dict):
            for col, rzr in col_res_dict.items():
                features_used_set.add(col)
                outlier_indices = getattr(rzr, "outlier_indices", [])
                med_v = getattr(rzr, "median", 0.0)
                mad_v = getattr(rzr, "mad", 1.0)
                thresh = getattr(rzr, "threshold", 3.5)
                for r_idx in outlier_indices:
                    if r_idx in df.index:
                        val = df.loc[r_idx, col]
                        rz_val = abs(0.6745 * (val - med_v) / mad_v) if mad_v > 1e-9 else 0.0
                        row_data[r_idx]["methods"].add("Robust Z-Score")
                        row_data[r_idx]["columns"].add(col)
                        norm_score = min(1.0, 0.45 + (rz_val - thresh) * 0.12)
                        row_data[r_idx]["scores"].append(norm_score)
                        row_data[r_idx]["signals"].append(f"'{col}' Robust Z-score (MAD) is {rz_val:.2f} (|z_rob| > {thresh})")
                        if col not in row_data[r_idx]["expected_ranges"]:
                            row_data[r_idx]["expected_ranges"][col] = f"Median: {med_v:,.2f}, MAD: {mad_v:,.2f}"

    # 4. Process Isolation Forest results
    if_res = results.get("isolation_forest")
    if if_res:
        methods_present.append("Isolation Forest")
        features_used = getattr(if_res, "features_used", [])
        features_used_set.update(features_used)
        anom_indices = getattr(if_res, "anomaly_indices", [])
        anom_scores = getattr(if_res, "anomaly_scores", [])
        for r_idx in anom_indices:
            if r_idx in df.index:
                row_pos = df.index.get_loc(r_idx)
                sc = anom_scores[row_pos] if row_pos < len(anom_scores) else 0.60
                row_data[r_idx]["methods"].add("Isolation Forest")
                row_data[r_idx]["scores"].append(sc)
                row_data[r_idx]["signals"].append(f"Isolation Forest calibrated anomaly score: {sc:.3f}")
                # If no columns were attributed yet, add features modeled
                if not row_data[r_idx]["columns"] and features_used:
                    for f in features_used:
                        row_data[r_idx]["columns"].add(f)

    # 5. Process Multivariate results if present
    mv_res = results.get("multivariate")
    if mv_res:
        if "Multivariate Analysis" not in methods_present:
            methods_present.append("Multivariate Analysis")
        for anom_rec in getattr(mv_res, "anomalies", []):
            r_idx = getattr(anom_rec, "row_index", None)
            if r_idx in df.index:
                row_data[r_idx]["methods"].add("Multivariate Analysis")
                row_data[r_idx]["scores"].append(getattr(anom_rec, "anomaly_score", 0.65))
                for sig in getattr(anom_rec, "signals", []):
                    row_data[r_idx]["signals"].append(sig)

    total_eval_methods = max(1, len(methods_present))

    # Build SingleAnomalyRecord for each flagged row
    records: List[SingleAnomalyRecord] = []
    all_anomaly_indices: List[Any] = []
    severity_breakdown = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    agreement_distribution: Dict[str, int] = defaultdict(int)
    all_affected_columns_set: Set[str] = set()

    for r_idx, info in row_data.items():
        if not info["methods"]:
            continue

        agreeing_count = len(info["methods"])
        agreement_ratio_str = f"{agreeing_count}/{total_eval_methods}"
        agreement_distribution[agreement_ratio_str] += 1

        # Composite score: mean or max of normalized scores
        comp_score = float(np.max(info["scores"])) if info["scores"] else 0.50
        comp_score = max(0.0, min(1.0, round(comp_score, 3)))

        aff_cols = sorted(list(info["columns"]))
        all_affected_columns_set.update(aff_cols)

        # Calculate severity
        sev, sev_signals = calculate_anomaly_severity(
            score=comp_score,
            methods_agreeing=agreeing_count,
            total_methods=total_eval_methods,
            affected_columns=aff_cols,
            max_z=info["max_z"],
            has_iqr_outlier=info["has_iqr"],
        )
        severity_breakdown[sev] += 1

        all_signals = info["signals"] + [s for s in sev_signals if s not in info["signals"]]

        # Extract original values for affected columns
        orig_vals = {}
        for c in aff_cols:
            if c in df.columns:
                val = df.loc[r_idx, c]
                orig_vals[c] = round(float(val), 4) if isinstance(val, (int, float, np.number)) else str(val)

        records.append(
            SingleAnomalyRecord(
                row_index=r_idx,
                affected_columns=aff_cols,
                original_values=orig_vals,
                methods=sorted(list(info["methods"])),
                methods_agreeing=agreeing_count,
                total_methods_evaluated=total_eval_methods,
                agreement_ratio_str=agreement_ratio_str,
                score=comp_score,
                severity=sev,
                signals=all_signals,
                expected_ranges=info["expected_ranges"],
                deviations=info["deviations"],
            )
        )
        all_anomaly_indices.append(r_idx)

    # Sort records descending by score and severity
    sev_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    records.sort(key=lambda x: (sev_rank.get(x.severity, 0), x.score), reverse=True)

    anom_count = len(records)
    anom_pct = round((anom_count / max(1, total_rows)) * 100, 2)
    normal_count = total_rows - anom_count

    return CombinedAnomalyResult(
        dataset_name=dataset_name,
        total_rows=total_rows,
        features_used=sorted(list(features_used_set)),
        methods_used=methods_present,
        anomaly_count=anom_count,
        normal_count=normal_count,
        anomaly_percentage=anom_pct,
        all_anomaly_indices=all_anomaly_indices,
        records=records,
        affected_columns=sorted(list(all_affected_columns_set)),
        method_results=results,
        severity_breakdown=dict(severity_breakdown),
        method_agreement_counts=dict(agreement_distribution),
        warnings=[],
        errors=[],
    )
