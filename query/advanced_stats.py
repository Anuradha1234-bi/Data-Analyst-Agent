"""Advanced Statistical Analysis Engine for AI Data Analyst Agent.

Provides mathematically grounded, assumption-verified statistical routines:
1. Extended Descriptive Statistics (Moments, IQR, Skewness, Kurtosis).
2. Pearson & Spearman Correlation Matrices with Causation Caveats.
3. Two-Group Hypothesis Testing (Independent T-Test / Mann-Whitney U).
4. Chi-Square Test of Independence for Categorical Associations.
5. Linear Regression Diagnostics & Trend Estimation.
"""

from typing import Dict, Any, List, Optional, Tuple
import math
import numpy as np
import pandas as pd
from scipy import stats


class AdvancedStatsEngine:
    """Engine executing rigorous statistical tests and distribution analyses."""

    # =========================================================================
    # 1. EXTENDED DESCRIPTIVE STATISTICS
    # =========================================================================

    @classmethod
    def compute_extended_statistics(cls, series: pd.Series) -> Dict[str, Any]:
        """Compute comprehensive moments, quartiles, and distribution shape metrics."""
        clean_s = series.dropna()
        n_total = len(series)
        n_valid = len(clean_s)
        n_missing = n_total - n_valid
        missing_pct = round((n_missing / n_total) * 100.0, 2) if n_total > 0 else 0.0

        if n_valid == 0:
            return {
                "valid_count": 0,
                "missing_count": n_missing,
                "missing_percentage": missing_pct,
                "error": "No non-null numerical observations found in series.",
            }

        mean_val = float(clean_s.mean())
        median_val = float(clean_s.median())
        std_val = float(clean_s.std(ddof=1)) if n_valid > 1 else 0.0
        var_val = float(clean_s.var(ddof=1)) if n_valid > 1 else 0.0
        min_val = float(clean_s.min())
        max_val = float(clean_s.max())
        sum_val = float(clean_s.sum())

        q25 = float(clean_s.quantile(0.25))
        q75 = float(clean_s.quantile(0.75))
        iqr_val = round(q75 - q25, 4)

        # Skewness & Kurtosis (require n >= 3)
        skew_val = float(clean_s.skew()) if n_valid >= 3 else 0.0
        kurt_val = float(clean_s.kurt()) if n_valid >= 4 else 0.0

        skew_label = "Approximately Symmetric"
        if skew_val > 1.0:
            skew_label = "Highly Positively Skewed (Right-tailed)"
        elif skew_val < -1.0:
            skew_label = "Highly Negatively Skewed (Left-tailed)"
        elif 0.5 <= skew_val <= 1.0:
            skew_label = "Moderately Positively Skewed"
        elif -1.0 <= skew_val <= -0.5:
            skew_label = "Moderately Negatively Skewed"

        return {
            "valid_count": n_valid,
            "missing_count": n_missing,
            "missing_percentage": missing_pct,
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_val, 4),
            "variance": round(var_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "sum": round(sum_val, 4),
            "q25": round(q25, 4),
            "q75": round(q75, 4),
            "iqr": iqr_val,
            "skewness": round(skew_val, 4),
            "skewness_interpretation": skew_label,
            "kurtosis": round(kurt_val, 4),
        }

    # =========================================================================
    # 2. CORRELATION & RELATIONSHIP ANALYSIS
    # =========================================================================

    @classmethod
    def compute_correlation_analysis(
        cls,
        df: pd.DataFrame,
        method: str = "pearson",
    ) -> Dict[str, Any]:
        """Compute pairwise correlation matrix and extract strongest relationships."""
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return {
                "success": False,
                "error": f"Correlation analysis requires at least 2 numerical columns. Found {len(num_cols)}.",
            }

        clean_sub = df[num_cols].dropna()
        if len(clean_sub) < 3:
            return {
                "success": False,
                "error": "Insufficient valid observations (minimum 3 rows required for correlation).",
            }

        # Calculate Pearson and Spearman matrices
        corr_matrix = clean_sub.corr(method=method)

        # Extract top pairs (excluding self-correlation)
        pairs: List[Dict[str, Any]] = []
        for i in range(len(num_cols)):
            for j in range(i + 1, len(num_cols)):
                col_a = num_cols[i]
                col_b = num_cols[j]
                r_val = corr_matrix.loc[col_a, col_b]
                if not math.isnan(r_val):
                    abs_r = abs(r_val)
                    if abs_r >= 0.7:
                        strength = "Strong"
                    elif abs_r >= 0.4:
                        strength = "Moderate"
                    elif abs_r >= 0.2:
                        strength = "Weak"
                    else:
                        strength = "Negligible"

                    direction = "Positive" if r_val > 0 else "Negative"

                    pairs.append({
                        "column_a": col_a,
                        "column_b": col_b,
                        "correlation": round(float(r_val), 4),
                        "strength": strength,
                        "direction": direction,
                        "summary": f"{strength} {direction.lower()} relationship (r = {round(r_val, 3)})",
                    })

        pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        # Prepare 2D matrix structure for frontend heatmap
        matrix_data = []
        for col_y in num_cols:
            row_vals = []
            for col_x in num_cols:
                val = corr_matrix.loc[col_y, col_x]
                row_vals.append(None if math.isnan(val) else round(float(val), 3))
            matrix_data.append(row_vals)

        return {
            "success": True,
            "method": method.capitalize(),
            "columns": num_cols,
            "matrix": matrix_data,
            "pairs": pairs,
            "strongest_pair": pairs[0] if pairs else None,
            "limitations": [
                "Correlation measures statistical co-variation, not causal direction or mechanism.",
                "Non-linear dependencies may not be captured by linear Pearson correlation.",
            ],
        }

    # =========================================================================
    # 3. TWO-GROUP HYPOTHESIS TESTING
    # =========================================================================

    @classmethod
    def compare_two_groups(
        cls,
        df: pd.DataFrame,
        group_column: str,
        metric_column: str,
        group_a: Optional[str] = None,
        group_b: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform two-sample t-test and Mann-Whitney U test between category groups."""
        if group_column not in df.columns or metric_column not in df.columns:
            return {"success": False, "error": f"Columns '{group_column}' or '{metric_column}' not found."}

        clean_df = df[[group_column, metric_column]].dropna()
        available_groups = clean_df[group_column].unique()

        if len(available_groups) < 2:
            return {"success": False, "error": f"Group column '{group_column}' requires at least 2 distinct categories."}

        g1_name = str(group_a) if group_a is not None else str(available_groups[0])
        g2_name = str(group_b) if group_b is not None else str(available_groups[1])

        vals_g1 = clean_df[clean_df[group_column] == g1_name][metric_column]
        vals_g2 = clean_df[clean_df[group_column] == g2_name][metric_column]

        n1, n2 = len(vals_g1), len(vals_g2)
        if n1 < 2 or n2 < 2:
            return {
                "success": False,
                "error": f"Insufficient sample sizes for comparison: '{g1_name}' has N={n1}, '{g2_name}' has N={n2}. (Minimum 2 required per group).",
            }

        mean_1, mean_2 = float(vals_g1.mean()), float(vals_g2.mean())
        std_1, std_2 = float(vals_g1.std(ddof=1)), float(vals_g2.std(ddof=1))
        diff = mean_1 - mean_2

        # Independent two-sample t-test (Welch's t-test unequal variances)
        t_stat, p_val = stats.ttest_ind(vals_g1, vals_g2, equal_var=False)

        # Mann-Whitney U test (non-parametric rank-sum test)
        u_stat, u_pval = stats.mannwhitneyu(vals_g1, vals_g2, alternative="two-sided")

        # Cohen's d effect size
        pooled_std = math.sqrt(((n1 - 1) * (std_1 ** 2) + (n2 - 1) * (std_2 ** 2)) / (n1 + n2 - 2)) if (n1 + n2 - 2) > 0 else 1.0
        cohens_d = (diff / pooled_std) if pooled_std > 0 else 0.0

        is_significant = bool(p_val < 0.05)
        significance_text = (
            f"The difference between '{g1_name}' (Mean = {mean_1:,.2f}) and '{g2_name}' (Mean = {mean_2:,.2f}) "
            f"is statistically significant (t = {t_stat:.3f}, p = {p_val:.4f} < 0.05)."
            if is_significant else
            f"No statistically significant difference was detected between '{g1_name}' and '{g2_name}' "
            f"(t = {t_stat:.3f}, p = {p_val:.4f} >= 0.05). The observed variance may be due to random chance."
        )

        return {
            "success": True,
            "test_name": "Welch's t-test (unequal variances)",
            "group_a": {"name": g1_name, "sample_size": n1, "mean": round(mean_1, 2), "std": round(std_1, 2)},
            "group_b": {"name": g2_name, "sample_size": n2, "mean": round(mean_2, 2), "std": round(std_2, 2)},
            "mean_difference": round(diff, 2),
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_val), 4),
            "mann_whitney_u": round(float(u_stat), 2),
            "mann_whitney_p": round(float(u_pval), 4),
            "cohens_d": round(float(cohens_d), 3),
            "is_significant": is_significant,
            "interpretation": significance_text,
            "limitations": [
                "Welch's t-test assumes approximately continuous distribution within each group.",
                "Statistical significance does not imply business significance or practical importance.",
            ],
        }

    # =========================================================================
    # 4. CHI-SQUARE TEST OF INDEPENDENCE
    # =========================================================================

    @classmethod
    def chi_square_test(
        cls,
        df: pd.DataFrame,
        col_x: str,
        col_y: str,
    ) -> Dict[str, Any]:
        """Compute contingency table and Chi-square test of independence for two categorical columns."""
        clean_df = df[[col_x, col_y]].dropna()
        if len(clean_df) < 5:
            return {"success": False, "error": "Insufficient records (minimum 5) for chi-square test."}

        contingency_table = pd.crosstab(clean_df[col_x], clean_df[col_y])
        if contingency_table.shape[0] < 2 or contingency_table.shape[1] < 2:
            return {"success": False, "error": "Both categorical features must have at least 2 distinct levels."}

        chi2_stat, p_val, dof, expected = stats.chi2_contingency(contingency_table)

        # Cramér's V measure of association: sqrt(chi2 / (n * min(r-1, c-1)))
        n = contingency_table.sum().sum()
        min_dim = min(contingency_table.shape[0] - 1, contingency_table.shape[1] - 1)
        cramers_v = math.sqrt(chi2_stat / (n * min_dim)) if (n * min_dim) > 0 else 0.0

        is_significant = bool(p_val < 0.05)
        text = (
            f"Statistically significant association detected between '{col_x}' and '{col_y}' "
            f"(Chi² = {chi2_stat:.2f}, dof = {dof}, p = {p_val:.4f} < 0.05, Cramér's V = {cramers_v:.3f})."
            if is_significant else
            f"No statistically significant relationship between '{col_x}' and '{col_y}' "
            f"(Chi² = {chi2_stat:.2f}, dof = {dof}, p = {p_val:.4f} >= 0.05). Categories appear independent."
        )

        return {
            "success": True,
            "chi2_statistic": round(float(chi2_stat), 3),
            "degrees_of_freedom": int(dof),
            "p_value": round(float(p_val), 4),
            "cramers_v": round(float(cramers_v), 3),
            "is_significant": is_significant,
            "contingency_table_shape": list(contingency_table.shape),
            "interpretation": text,
        }

    # =========================================================================
    # 5. LINEAR REGRESSION & TREND ESTIMATION
    # =========================================================================

    @classmethod
    def compute_linear_regression(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
    ) -> Dict[str, Any]:
        """Compute ordinary least squares linear regression between X and Y."""
        clean_df = df[[x_col, y_col]].dropna()

        # If x_col is a date, convert to ordinal for numeric regression
        if pd.api.types.is_datetime64_any_dtype(clean_df[x_col]):
            x_vals = clean_df[x_col].map(pd.Timestamp.toordinal).values
        else:
            x_vals = pd.to_numeric(clean_df[x_col], errors="coerce").dropna().values
            clean_df = clean_df.iloc[:len(x_vals)]

        y_vals = pd.to_numeric(clean_df[y_col], errors="coerce").dropna().values
        min_len = min(len(x_vals), len(y_vals))
        x_vals = x_vals[:min_len]
        y_vals = y_vals[:min_len]

        if min_len < 3:
            return {"success": False, "error": "Linear regression requires at least 3 numerical data points."}

        slope, intercept, r_val, p_val, std_err = stats.linregress(x_vals, y_vals)
        r_squared = r_val ** 2

        trend_dir = "Upward Positive Trend" if slope > 0 else "Downward Negative Trend"
        equation = f"y = {slope:.4f} * x + {intercept:.4f}"

        # Generate regression line data points for chart overlay
        x_min, x_max = float(np.min(x_vals)), float(np.max(x_vals))
        y_hat_min = slope * x_min + intercept
        y_hat_max = slope * x_max + intercept

        return {
            "success": True,
            "x_column": x_col,
            "y_column": y_col,
            "slope": round(float(slope), 4),
            "intercept": round(float(intercept), 4),
            "r_value": round(float(r_val), 4),
            "r_squared": round(float(r_squared), 4),
            "p_value": round(float(p_val), 4),
            "standard_error": round(float(std_err), 4),
            "equation": equation,
            "trend_direction": trend_dir,
            "line_points": [
                {"x": round(x_min, 2), "y": round(float(y_hat_min), 2)},
                {"x": round(x_max, 2), "y": round(float(y_hat_max), 2)},
            ],
            "interpretation": (
                f"For every 1-unit increase in '{x_col}', '{y_col}' changes by approximately {slope:,.2f}. "
                f"The model explains {r_squared * 100:.1f}% of the variance in '{y_col}' (R² = {r_squared:.3f}, p = {p_val:.4f})."
            ),
            "limitations": [
                "Assumes a strictly linear relationship between predictor and target.",
                "Extreme outliers can substantially skew linear slope estimates.",
                "Statistical association does not prove causal intervention.",
            ],
        }
