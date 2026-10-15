"""Query Intent Detector for Natural-Language Data Questions.

Categorizes natural language analytical questions into a controlled, safe set of intents.
Does not invent unsupported intents. Rejects code execution or dangerous attempts.
"""

from typing import Dict, Any, List, Optional
import re
from query.query_models import QueryIntent


# Security blacklist patterns
DISALLOWED_PATTERNS = [
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bos\.system",
    r"\bsubprocess\b",
    r"\b__import__\b",
    r"\bimport\s+os\b",
    r"\bdelete\b.*?\b(file|table|database|directory)\b",
    r"\bdrop\b.*?\b(table|database)\b",
    r"\btruncate\b.*?\btable\b",
    r"\brun\s+python\s+code\b",
    r"\bpython\s+code\b",
    r"\bexecute\b.*?\b(code|script|sql|command)\b",
    r"\b(arbitrary\s+sql|arbitrary\s+code)\b",
    r"\b(select|insert|update|delete|drop|alter)\s+.*\s+from\b",
    r"\bsh\b|\bbash\b|\bcmd\b|\bpowershell\b",
]


def detect_query_intent(
    question: str,
    metadata: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detect the analytical intent from user question and context.

    Contract:
    Returns:
    {
        "intent": "TOP_N",
        "confidence": 0.92,
        "reason": "...",
        "candidate_intents": []
    }
    """
    if not question or not question.strip():
        return {
            "intent": QueryIntent.UNKNOWN.value,
            "confidence": 0.0,
            "reason": "Empty or whitespace-only question.",
            "candidate_intents": [],
        }

    q_clean = question.strip()
    q_lower = q_clean.lower()

    # 1. Security Check: Reject code execution requests immediately
    for pattern in DISALLOWED_PATTERNS:
        if re.search(pattern, q_lower):
            return {
                "intent": QueryIntent.UNKNOWN.value,
                "confidence": 0.0,
                "reason": "Question contains disallowed code execution, file system, or arbitrary command patterns.",
                "candidate_intents": [],
            }

    # 2. Check for Contextual Follow-ups
    prev_plan = context.get("previous_query_plan") if context else None
    if prev_plan and isinstance(prev_plan, dict):
        prev_intent = prev_plan.get("intent")
        if re.search(r"\b(second|2nd|third|3rd|next|another)\s+(highest|lowest|best|worst|top|bottom)\b", q_lower):
            target_intent = QueryIntent.TOP_N.value if any(w in q_lower for w in ["highest", "best", "top"]) else QueryIntent.BOTTOM_N.value
            return {
                "intent": target_intent,
                "confidence": 0.95,
                "reason": f"Follow-up rank modification referencing previous {prev_intent} query.",
                "candidate_intents": [{"intent": target_intent, "score": 0.95}],
            }
        if re.search(r"\b(make\s+it|change\s+to|show)\s+(top|bottom)?\s*(\d+)\b", q_lower):
            return {
                "intent": prev_intent or QueryIntent.TOP_N.value,
                "confidence": 0.95,
                "reason": "Follow-up limit modification for previous query.",
                "candidate_intents": [{"intent": prev_intent or QueryIntent.TOP_N.value, "score": 0.95}],
            }

    # 3. Intent Pattern Matching with Candidates
    candidates: List[Dict[str, Any]] = []

    def add_candidate(intent: QueryIntent, score: float, reason: str):
        candidates.append({"intent": intent.value, "score": score, "reason": reason})

    # Data Hygiene & Metadata
    if any(k in q_lower for k in ["missing value", "missing values", "null values", "nan", "missing data", "percentage of values are missing", "missing%"]):
        add_candidate(QueryIntent.MISSING_VALUES, 0.95, "Matches missing value inquiry keywords.")
    elif "missing" in q_lower:
        add_candidate(QueryIntent.MISSING_VALUES, 0.85, "Matches keyword 'missing'.")

    if any(k in q_lower for k in ["duplicate", "duplicates", "duplicated", "repeated rows", "identical rows"]):
        add_candidate(QueryIntent.DUPLICATES, 0.95, "Matches duplicate records inquiry keywords.")

    if any(k in q_lower for k in ["data type", "datatypes", "data types", "which columns are numeric", "column types", "dtypes"]):
        add_candidate(QueryIntent.DATA_TYPES, 0.95, "Matches column data types inquiry.")

    if any(k in q_lower for k in ["unique value", "unique values", "distinct values", "how many unique", "nunique"]):
        add_candidate(QueryIntent.UNIQUE_VALUES, 0.92, "Matches unique / distinct value inquiry.")

    # Phase 4 Anomaly Queries
    if any(k in q_lower for k in ["unusual record", "anomalous record", "show anomalies", "show outliers", "list outliers", "outlier rows"]):
        add_candidate(QueryIntent.ANOMALY_RECORDS, 0.94, "Matches anomalous record extraction keywords.")
    elif any(k in q_lower for k in ["unusual value", "unusual values", "anomal", "outlier", "outliers", "isolation forest", "iqr"]):
        add_candidate(QueryIntent.ANOMALY_SUMMARY, 0.92, "Matches statistical anomaly summary keywords.")

    # Phase 5 Correlation
    if any(k in q_lower for k in ["correlat", "correlation", "strongly correlated", "highest correlation", "association between"]):
        add_candidate(QueryIntent.CORRELATION, 0.95, "Matches statistical correlation keywords.")

    # Phase 5 Insights & Summaries
    if any(k in q_lower for k in ["main insight", "main insights", "explain the main insights", "key findings", "important findings", "summary of insight", "executive insight", "summarize", "summarise", "summary of the dataset", "summarize the important findings", "dataset summary"]):
        add_candidate(QueryIntent.INSIGHT_SUMMARY, 0.95, "Matches insight summary keywords.")

    # Statistical Analysis, Regression & Hypothesis Testing
    if any(k in q_lower for k in ["regression", "linear regression", "regress", "r-squared", "trend line equation", "ordinary least squares"]):
        add_candidate(QueryIntent.REGRESSION, 0.96, "Matches linear regression keywords.")

    if any(k in q_lower for k in ["t-test", "ttest", "statistically significant difference", "compare two groups", "is the difference significant", "mann-whitney", "hypothesis test"]):
        add_candidate(QueryIntent.TWO_GROUP_TEST, 0.95, "Matches two-group hypothesis testing keywords.")

    if any(k in q_lower for k in ["chi-square", "chi square", "contingency table", "categorical association", "cramers v"]):
        add_candidate(QueryIntent.CHI_SQUARE, 0.95, "Matches chi-square categorical association test.")

    if any(k in q_lower for k in ["descriptive statistics", "summary statistics", "moments", "distribution summary", "skewness", "kurtosis"]):
        add_candidate(QueryIntent.DESCRIPTIVE_STATISTICS, 0.92, "Matches descriptive statistics keywords.")

    # Predictive & Forecasting Queries (Phase 5)
    if any(k in q_lower for k in ["forecast", "predict future", "future sales", "next 7 days", "next 14 days", "next 30 days", "projected", "future demand", "what will the price be", "forecast demand"]):
        add_candidate(QueryIntent.FORECAST, 0.95, "Matches forecasting inquiry keywords.")

    elif any(k in q_lower for k in ["predict", "prediction", "which model performed better", "which model performs better", "model accuracy", "model performance", "predicted price", "predicted value"]):
        add_candidate(QueryIntent.PREDICTION, 0.92, "Matches predictive modeling inquiry keywords.")

    # Temporal & Date Queries
    if any(k in q_lower for k in ["trend", "trajectory", "over time", "monthly trend", "price trend", "daily trend", "weekly trend"]):
        add_candidate(QueryIntent.TREND, 0.94, "Matches temporal trend inquiry keywords.")

    if any(k in q_lower for k in ["what changed between", "difference between dates", "compare august and september", "compare dates", "change between"]):
        add_candidate(QueryIntent.DATE_COMPARISON, 0.95, "Matches date-to-date comparison keywords.")

    if any(k in q_lower for k in ["percentage change", "percent change", "pct change", "growth rate", "how much did price increase"]):
        add_candidate(QueryIntent.PERCENTAGE_CHANGE, 0.92, "Matches percentage change inquiry.")

    if any(k in q_lower for k in ["between", "from date", "during year", "in 202", "date range"]) and any(w in q_lower for w in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "2024", "2025", "2026"]):
        add_candidate(QueryIntent.DATE_RANGE, 0.88, "Matches date range filter keywords.")

    # Cross-dataset & Dataset Comparison
    if any(k in q_lower for k in ["compare these two datasets", "compare datasets", "compare both datasets", "dataset comparison"]):
        add_candidate(QueryIntent.COMPARE_DATASETS, 0.95, "Matches dataset comparison keywords.")

    if any(k in q_lower for k in ["compare sales and customer", "across datasets", "joined with", "customers who purchased", "customer sales", "compare sales between regions", "sales by region", "sales between regions"]):
        add_candidate(QueryIntent.CROSS_DATASET_ANALYSIS, 0.95, "Matches cross-dataset analysis keywords.")

    if any(k in q_lower for k in ["compare sales between two regions", "compare between regions", "compare groups", "compare categories"]):
        add_candidate(QueryIntent.COMPARE_GROUPS, 0.90, "Matches group comparison keywords.")

    # Rankings: Top N & Bottom N
    top_n_pattern = r"\b(top|highest|best|largest|peak|greatest)\s*(\d+)?\b"
    bottom_n_pattern = r"\b(bottom|lowest|worst|smallest|least)\s*(\d+)?\b"

    match_top = re.search(top_n_pattern, q_lower)
    match_bottom = re.search(bottom_n_pattern, q_lower)

    # Check for "highest average price" vs "top 10"
    if match_top:
        limit_str = match_top.group(2)
        if limit_str:
            add_candidate(QueryIntent.TOP_N, 0.95, f"Matches Top-{limit_str} ranking pattern.")
        elif any(w in q_lower for w in ["which", "what", "who"]) and any(w in q_lower for w in ["highest", "largest", "peak", "maximum"]):
            # e.g., "Which market has the highest average price?" -> TOP_N with limit=1 or MAXIMUM
            add_candidate(QueryIntent.TOP_N, 0.93, "Matches superlative highest ranking question (Top 1).")
        else:
            add_candidate(QueryIntent.TOP_N, 0.85, "Matches top ranking keywords.")

    if match_bottom:
        limit_str = match_bottom.group(2)
        if limit_str:
            add_candidate(QueryIntent.BOTTOM_N, 0.95, f"Matches Bottom-{limit_str} ranking pattern.")
        elif any(w in q_lower for w in ["which", "what"]) and any(w in q_lower for w in ["lowest", "smallest", "minimum"]):
            add_candidate(QueryIntent.BOTTOM_N, 0.93, "Matches superlative lowest ranking question (Bottom 1).")
        else:
            add_candidate(QueryIntent.BOTTOM_N, 0.85, "Matches bottom ranking keywords.")

    # Aggregations
    if any(k in q_lower for k in ["how many records", "how many rows", "row count", "count of", "total records", "number of rows"]):
        add_candidate(QueryIntent.COUNT, 0.95, "Matches record count inquiry.")

    if any(k in q_lower for k in ["average", "mean", "avg"]):
        add_candidate(QueryIntent.AVERAGE, 0.90, "Matches average/mean aggregation keyword.")

    if any(k in q_lower for k in ["median", "50th percentile"]):
        add_candidate(QueryIntent.MEDIAN, 0.92, "Matches median aggregation keyword.")

    if any(k in q_lower for k in ["sum of", "total of", "total sales", "total revenue", "total quantity", "total amount"]):
        add_candidate(QueryIntent.SUM, 0.90, "Matches summation aggregation keyword.")

    if "minimum" in q_lower or (re.search(r"\bmin\b", q_lower) and "minute" not in q_lower):
        add_candidate(QueryIntent.MINIMUM, 0.88, "Matches minimum aggregation keyword.")

    if "maximum" in q_lower or (re.search(r"\bmax\b", q_lower) and "maximum" not in q_lower):
        add_candidate(QueryIntent.MAXIMUM, 0.88, "Matches maximum aggregation keyword.")

    # Grouping
    if any(k in q_lower for k in ["group by", "grouped by", "by market", "by commodity", "by region", "by customer", "per category", "for each"]):
        add_candidate(QueryIntent.GROUP_BY, 0.85, "Matches grouping keywords.")

    # Filtering & Showing data
    if any(k in q_lower for k in ["where", "greater than", "less than", "is equal to", "filtered by", "more than", "above"]):
        add_candidate(QueryIntent.FILTER, 0.82, "Matches filter clause keywords.")

    if any(k in q_lower for k in ["show me records", "show data", "display rows", "view records", "show the first"]):
        add_candidate(QueryIntent.SHOW_DATA, 0.80, "Matches raw records display inquiry.")

    # Sort
    if any(k in q_lower for k in ["sort by", "order by", "sorted ascending", "sorted descending"]):
        add_candidate(QueryIntent.SORT, 0.85, "Matches sorting keywords.")

    # Highest and lowest values
    if "highest and lowest" in q_lower or "max and min" in q_lower:
        add_candidate(QueryIntent.DESCRIPTIVE_STATISTICS, 0.90, "Matches range (highest and lowest) inquiry.")

    if not candidates:
        return {
            "intent": QueryIntent.UNKNOWN.value,
            "confidence": 0.20,
            "reason": "Could not conclusively map question to a known analytical intent.",
            "candidate_intents": [],
        }

    # Sort candidates by descending score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_cand = candidates[0]

    return {
        "intent": top_cand["intent"],
        "confidence": top_cand["score"],
        "reason": top_cand["reason"],
        "candidate_intents": candidates,
    }
