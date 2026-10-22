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


def normalize_question_for_intent(question: str) -> str:
    """Normalize colloquial, ungrammatical, or conversational phrasing for intent detection."""
    if not question:
        return ""
    q = question.strip()

    # Number words to digits in top/bottom expressions
    word_to_num = {
        r"\bone\b": "1", r"\btwo\b": "2", r"\bthree\b": "3", r"\bfour\b": "4",
        r"\bfive\b": "5", r"\bsix\b": "6", r"\bseven\b": "7", r"\beight\b": "8",
        r"\bnine\b": "9", r"\bten\b": "10",
    }
    q_sub = q
    for pat, rep in word_to_num.items():
        if re.search(r"\b(?:top|bottom|first|last|compare|show|limit)\s+" + pat, q_sub, re.IGNORECASE):
            q_sub = re.sub(pat, rep, q_sub, flags=re.IGNORECASE)

    q_l = q_sub.lower()

    # 1. Normalize colloquial superlatives and sales verbs
    # "selling most", "sells most", "sold most", "sold the most", "selling the most"
    q_l = re.sub(r"\b(?:selling|sells|sold)\s+(?:the\s+)?most\b", "highest sales", q_l)
    # "sold better", "sells better", "selling better"
    q_l = re.sub(r"\b(?:sold|sells|selling)\s+better\b", "highest sales", q_l)
    # "got the most sale", "got most sale", "has the most sale", "most sale", "most sales"
    q_l = re.sub(r"\b(?:got|has|with)?\s*(?:the\s+)?most\s+sales?\b", "highest sales", q_l)
    # "which sales is highest", "whose sales is highest"
    q_l = re.sub(r"\bwhich\s+sales\s+is\s+highest\b", "which has highest sales", q_l)
    # "highest selling", "top selling"
    q_l = re.sub(r"\b(?:highest|top)\s+selling\b", "highest sales", q_l)
    # "lowest selling", "least selling"
    q_l = re.sub(r"\b(?:lowest|least)\s+selling\b", "lowest sales", q_l)
    # "performs best", "performing best", "performed best", "performance best"
    q_l = re.sub(r"\b(?:performs|performing|performed|performance)\s+best\b", "highest performance", q_l)
    # "performs worst", "performing worst", "performed worst"
    q_l = re.sub(r"\b(?:performs|performing|performed|performance)\s+worst\b", "lowest performance", q_l)

    # 2. Strip conversational politeness/fillers at beginning
    q_l = re.sub(
        r"^(?:can you\s+(?:please\s+)?(?:find|tell me|show me|give me|check|get)|could you\s+(?:please\s+)?(?:find|tell me|show me|give me|check|get)|please\s+(?:find|tell me|show me|give me|check|get)|tell me\s+(?:about\s+)?|i want to know\s+|find\s+(?:me\s+)?|show me\s+)",
        "",
        q_l
    ).strip()

    return q_l


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
    q_norm = normalize_question_for_intent(q_clean)
    q_norm_l = q_norm.lower()

    # 1. Security Check: Reject code execution requests immediately
    for pattern in DISALLOWED_PATTERNS:
        if re.search(pattern, q_lower) or re.search(pattern, q_norm_l):
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
        has_by = " by " in q_lower
        if not has_by and str(prev_intent).upper() in ("TOP_N", "BOTTOM_N", "GROUP_BY", "FILTER", "SORT", "SHOW_DATA"):
            if re.search(r"^(?:make\s+it|change\s+to|show\s+(?:only\s+)?(?:the\s+)?)(?:top|bottom)?\s*(\d+)\s*$", q_lower) or re.search(r"\b(make\s+it|change\s+to|limit\s+to)\s+(top|bottom)?\s*(\d+)\b", q_lower):
                return {
                    "intent": prev_intent or QueryIntent.TOP_N.value,
                    "confidence": 0.95,
                    "reason": "Follow-up limit modification for previous query.",
                    "candidate_intents": [{"intent": prev_intent or QueryIntent.TOP_N.value, "score": 0.95}],
                }

    # Strip negative constraints (e.g. "do not include outliers, correlations, or suggestions", "without outliers", "exclude ...")
    # so negative instructions do not trigger positive analytical intents.
    neg_pattern = r"\b(?:do\s+not\s+include|don't\s+include|without|exclude|excluding|do\s+not\s+perform|do\s+not\s+show|no|not\s+include)\s+[^.?;]+"
    q_positive = re.sub(neg_pattern, " ", q_lower).strip()
    q_norm_pos = re.sub(neg_pattern, " ", q_norm_l).strip()

    # 3. Intent Pattern Matching with Candidates
    candidates: List[Dict[str, Any]] = []

    def add_candidate(intent: QueryIntent, score: float, reason: str):
        candidates.append({"intent": intent.value, "score": score, "reason": reason})

    # Data Hygiene & Metadata
    if any(k in q_positive for k in ["missing value", "missing values", "null values", "nan", "missing data", "percentage of values are missing", "missing%"]):
        add_candidate(QueryIntent.MISSING_VALUES, 0.95, "Matches missing value inquiry keywords.")
    elif "missing" in q_positive:
        add_candidate(QueryIntent.MISSING_VALUES, 0.85, "Matches keyword 'missing'.")

    if any(k in q_positive for k in ["duplicate", "duplicates", "duplicated", "repeated rows", "identical rows"]):
        add_candidate(QueryIntent.DUPLICATES, 0.95, "Matches duplicate records inquiry keywords.")

    if any(k in q_positive for k in [
        "data type", "datatypes", "data types", "which columns are numeric", "column types", "dtypes",
        "column names and data types", "column names with their data types", "columns and their data types",
        "list all columns", "list columns", "what are the columns", "show all columns", "columns and data types",
        "column names and their data types", "column names, and data types", "column names and types",
        "tell me its exact filename", "exact filename", "dataset id", "row count, column count",
        "how many columns", "number of columns", "count of columns", "total columns", "column count",
        "list all column names", "list column names", "column names", "what are the column names",
        "all column names", "names of all columns", "list the columns", "show column names"
    ]):
        add_candidate(QueryIntent.DATA_TYPES, 0.98, "Matches column names / data types / schema inquiry.")

    if any(k in q_positive for k in ["unique value", "unique values", "distinct values", "how many unique", "nunique"]):
        add_candidate(QueryIntent.UNIQUE_VALUES, 0.92, "Matches unique / distinct value inquiry.")

    # Comprehensive Data Quality Audit (takes precedence over isolated anomaly/missing checks)
    if any(k in q_positive for k in [
        "data quality audit", "quality audit", "complete audit", "data audit",
        "completeness, uniqueness", "uniqueness, validity", "validity, consistency",
        "audit covering completeness", "complete data quality"
    ]):
        add_candidate(QueryIntent.DATA_QUALITY_AUDIT, 0.98, "Matches comprehensive data quality audit keywords.")

    # Phase 4 Anomaly Queries
    if any(k in q_positive for k in [
        "unusual record", "anomalous record", "show anomalies", "show outliers", "list outliers",
        "outlier rows", "outlier records", "actual outlier records", "show actual outlier records",
        "show outlier records", "show the actual outlier records", "outlier records with"
    ]):
        add_candidate(QueryIntent.ANOMALY_RECORDS, 0.95, "Matches anomalous record extraction keywords.")
    elif any(k in q_positive for k in ["unusual value", "unusual values", "anomal", "outlier", "outliers", "isolation forest", "iqr", "z-score", "zscore"]):
        add_candidate(QueryIntent.ANOMALY_SUMMARY, 0.92, "Matches statistical anomaly summary keywords.")

    # Phase 5 Correlation
    if any(k in q_positive for k in ["correlat", "correlation", "strongly correlated", "highest correlation", "association between", "associated with", "pearson and spearman", "pearson", "spearman"]):
        add_candidate(QueryIntent.CORRELATION, 0.96, "Matches statistical correlation keywords.")

    # Phase 5 Insights & Summaries
    if any(k in q_positive for k in ["main insight", "main insights", "explain the main insights", "key findings", "important findings", "summary of insight", "executive insight", "summarize", "summarise", "summary of the dataset", "summarize the important findings", "dataset summary"]):
        add_candidate(QueryIntent.INSIGHT_SUMMARY, 0.95, "Matches insight summary keywords.")

    # Statistical Analysis, Regression & Hypothesis Testing
    if any(k in q_lower for k in ["regression", "linear regression", "regress", "r-squared", "trend line equation", "ordinary least squares"]):
        add_candidate(QueryIntent.REGRESSION, 0.96, "Matches linear regression keywords.")

    if any(k in q_lower for k in ["t-test", "ttest", "statistically significant difference", "compare two groups", "is the difference significant", "mann-whitney", "hypothesis test"]):
        add_candidate(QueryIntent.TWO_GROUP_TEST, 0.95, "Matches two-group hypothesis testing keywords.")

    if any(k in q_lower for k in ["chi-square", "chi square", "contingency table", "categorical association", "cramers v"]):
        add_candidate(QueryIntent.CHI_SQUARE, 0.95, "Matches chi-square categorical association test.")

    desc_keywords = [
        "descriptive statistics", "summary statistics", "moments", "distribution summary",
        "skewness", "kurtosis", "distribution of", "spread of", "distribution", "statistical summary",
    ]
    if any(k in q_lower for k in desc_keywords) or re.search(r"\b(?:distribution|spread|variance)\s+of\b", q_lower) or re.search(r"\bsummar(?:y|ize)\s+of\s+([a-zA-Z0-9_]+)\b", q_lower):
        if not any(k in q_lower for k in ["main insight", "key findings", "executive insight"]):
            add_candidate(QueryIntent.DESCRIPTIVE_STATISTICS, 0.92, "Matches descriptive statistics or distribution inquiry.")

    # Predictive & Forecasting Queries (Phase 5)
    if any(k in q_lower for k in ["forecast", "predict future", "future sales", "next 7 days", "next 14 days", "next 30 days", "projected", "future demand", "what will the price be", "forecast demand"]):
        add_candidate(QueryIntent.FORECAST, 0.95, "Matches forecasting inquiry keywords.")

    elif any(k in q_lower for k in ["predict", "prediction", "which model performed better", "which model performs better", "model accuracy", "model performance", "predicted price", "predicted value"]):
        add_candidate(QueryIntent.PREDICTION, 0.92, "Matches predictive modeling inquiry keywords.")

    # Temporal & Date Queries
    trend_keywords = [
        "trend", "trajectory", "over time", "monthly trend", "price trend", "daily trend", "weekly trend",
        "monthly sales", "monthly revenue", "sales by month", "revenue by month", "by month", "monthly", "compare monthly", "over months",
    ]
    if any(k in q_lower or k in q_norm_l for k in trend_keywords) or re.search(r"\b(?:monthly\s+(?:sales|revenue|profit|trend)|compare\s+monthly|by\s+month|over\s+time)\b", q_lower) or re.search(r"\b(?:monthly\s+(?:sales|revenue|profit|trend)|compare\s+monthly|by\s+month|over\s+time)\b", q_norm_l):
        add_candidate(QueryIntent.TREND, 0.94, "Matches temporal trend inquiry keywords.")

    if any(k in q_lower for k in ["what changed between", "difference between dates", "compare august and september", "compare dates", "change between"]):
        add_candidate(QueryIntent.DATE_COMPARISON, 0.95, "Matches date-to-date comparison keywords.")

    if any(k in q_lower for k in ["percentage change", "percent change", "pct change", "growth rate", "how much did price increase"]):
        add_candidate(QueryIntent.PERCENTAGE_CHANGE, 0.92, "Matches percentage change inquiry.")

    if any(k in q_lower for k in ["between", "from date", "during year", "in 202", "date range"]) and any(w in q_lower for w in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "2024", "2025", "2026"]):
        add_candidate(QueryIntent.DATE_RANGE, 0.88, "Matches date range filter keywords.")

    # Cross-dataset & Dataset Comparison
    compare_ds_keywords = [
        "compare these two datasets", "compare datasets", "compare both datasets", "dataset comparison",
        "compare row counts", "compare columns between", "compare total records", "compare records between",
    ]
    if (
        any(k in q_lower for k in compare_ds_keywords)
        or re.search(r"\bcompare\s+.*?\b(?:between|of)\s+([a-zA-Z0-9_\.]+\.(?:csv|xlsx|xls))\s+and\s+([a-zA-Z0-9_\.]+\.(?:csv|xlsx|xls))", q_lower)
        or re.search(r"\bcompare\s+(?:the\s+)?(?:row\s+counts?|columns?|total\s+records?|records?)\b.*?\b(?:between|of|in)\b", q_lower)
    ):
        add_candidate(QueryIntent.COMPARE_DATASETS, 0.98, "Matches dataset comparison keywords.")

    cross_ds_keywords = [
        "compare sales and customer", "across datasets", "joined with", "customers who purchased", "customer sales",
        "join with", "joined on", "join on", "inner join", "left join",
    ]
    is_join_syntax = bool(re.search(r"\b(?:inner\s+|left\s+|right\s+|outer\s+)?join\s+[a-zA-Z0-9_\.]+\s+(?:with|and)\s+[a-zA-Z0-9_\.]+", q_lower))
    is_join_on = bool(re.search(r"\bjoin\s+.*?\bon\s+[a-zA-Z0-9_]+", q_lower))
    is_across_files = bool(re.search(r"\bacross\s+[a-zA-Z0-9_\.]+\s+and\s+[a-zA-Z0-9_\.]+", q_lower))
    is_diff_query = bool(re.search(r"\b(?:not\s+present\s+in|not\s+in|absent\s+in|no\s+(?:matching\s+)?records\s+in|without\s+any\s+orders|have\s+[a-zA-Z0-9_]+\s+not\s+present\s+in)\b", q_lower))

    if any(k in q_lower for k in cross_ds_keywords) or is_join_syntax or is_join_on or is_across_files or is_diff_query:
        add_candidate(QueryIntent.CROSS_DATASET_ANALYSIS, 0.96, "Matches cross-dataset or join analysis keywords.")

    if any(k in q_lower for k in ["compare sales between two regions", "compare between regions", "compare groups", "compare categories"]):
        add_candidate(QueryIntent.COMPARE_GROUPS, 0.90, "Matches group comparison keywords.")

    # Rankings: Top N & Bottom N
    top_n_pattern = r"\b(top|highest|best|largest|peak|greatest|most|maximum|max|leading|better)\s*(\d+)?\b"
    bottom_n_pattern = r"\b(bottom|lowest|worst|smallest|least|minimum|min|fewest)\s*(\d+)?\b"

    match_top = re.search(top_n_pattern, q_lower) or re.search(top_n_pattern, q_norm_l)
    match_bottom = re.search(bottom_n_pattern, q_lower) or re.search(bottom_n_pattern, q_norm_l)

    # Check for "highest average price" vs "top 10"
    if match_top:
        limit_str = match_top.group(2)
        if limit_str:
            add_candidate(QueryIntent.TOP_N, 0.95, f"Matches Top-{limit_str} ranking pattern.")
        elif any(w in q_lower or w in q_norm_l for w in ["which", "what", "who"]) and any(w in q_lower or w in q_norm_l for w in ["highest", "largest", "peak", "maximum", "best", "greatest", "most", "better", "leading"]):
            # e.g., "Which market has the highest average price?" -> TOP_N with limit=1 or MAXIMUM
            add_candidate(QueryIntent.TOP_N, 0.93, "Matches superlative highest ranking question (Top 1).")
        elif any(e in q_lower or e in q_norm_l for e in ["product", "commodity", "market", "region", "customer", "item", "category", "company", "state", "brand", "model", "student", "employee", "city", "country"]) and any(w in q_lower or w in q_norm_l for w in ["highest", "most", "best", "largest", "peak", "leading", "top", "better", "maximum"]):
            add_candidate(QueryIntent.TOP_N, 0.93, "Matches entity superlative ranking question (Top 1).")
        else:
            add_candidate(QueryIntent.TOP_N, 0.85, "Matches top ranking keywords.")

    if match_bottom:
        limit_str = match_bottom.group(2)
        if limit_str:
            add_candidate(QueryIntent.BOTTOM_N, 0.95, f"Matches Bottom-{limit_str} ranking pattern.")
        elif any(w in q_lower or w in q_norm_l for w in ["which", "what", "who"]) and any(w in q_lower or w in q_norm_l for w in ["lowest", "smallest", "minimum", "worst", "least", "fewest"]):
            add_candidate(QueryIntent.BOTTOM_N, 0.93, "Matches superlative lowest ranking question (Bottom 1).")
        elif any(e in q_lower or e in q_norm_l for e in ["product", "commodity", "market", "region", "customer", "item", "category", "company", "state", "brand", "model", "student", "employee", "city", "country"]) and any(w in q_lower or w in q_norm_l for w in ["lowest", "least", "worst", "smallest", "minimum", "fewest"]):
            add_candidate(QueryIntent.BOTTOM_N, 0.93, "Matches entity superlative ranking question (Bottom 1).")
        else:
            add_candidate(QueryIntent.BOTTOM_N, 0.85, "Matches bottom ranking keywords.")

    # Aggregations
    count_keywords = [
        "how many records", "how many rows", "row count", "count of", "total records",
        "number of rows", "record count", "how many", "total number of", "total count",
        "count the total rows", "count total rows", "count the rows", "count rows",
        "total rows", "total row count", "number of total rows",
    ]
    if (
        (any(k in q_positive for k in count_keywords)
        or re.search(r"\bhow\s+many\b", q_positive)
        or re.search(r"\bcount\s+(?:the\s+)?(?:total\s+)?(?:records|rows|students|orders|customers|items|products|entries|observations|cases)\b", q_positive))
        and not any(k in q_positive for k in ["how many columns", "number of columns", "count of columns", "how many unique", "how many distinct"])
    ):
        add_candidate(QueryIntent.COUNT, 0.95, "Matches record count inquiry.")

    is_subquery_filter = bool(re.search(r"\b(?:where|having|with)\s+.*?\b(?:above|below|greater than|less than|more than)\s+(?:the\s+)?average\b", q_lower))

    if any(k in q_positive for k in ["average", "mean", "avg"]):
        if is_subquery_filter and any(w in q_lower for w in ["show", "find", "list", "how many", "count"]):
            add_candidate(QueryIntent.AVERAGE, 0.70, "Matches secondary average keyword in filter condition.")
        else:
            add_candidate(QueryIntent.AVERAGE, 0.90, "Matches average/mean aggregation keyword.")

    if any(k in q_positive for k in ["median", "50th percentile"]):
        add_candidate(QueryIntent.MEDIAN, 0.92, "Matches median aggregation keyword.")

    meta_cols_sum = []
    if metadata and isinstance(metadata, dict):
        for m in metadata.values():
            if isinstance(m, dict):
                meta_cols_sum.extend(m.get("column_names", []) or m.get("columns", []) or list(m.get("data_types", {}).keys()))

    has_schema_sum = False
    for mc in meta_cols_sum:
        mc_clean = str(mc).lower().replace("_", " ")
        mc_raw = str(mc).lower()
        if re.search(r"\b(?:total|sum\s+of)\s+(?:" + re.escape(mc_raw) + r"|" + re.escape(mc_clean) + r")\b", q_positive):
            has_schema_sum = True
            break

    if (
        re.search(r"\b(?:sum\s+of|calculate\s+(?:the\s+)?(?:sum|total)|total\s+sum|find\s+(?:the\s+)?(?:sum|total)|by\s+summing|summing|totaling)\b", q_positive)
        or "total sum" in q_positive
        or has_schema_sum
        or (
            re.search(r"\b(?:what\s+is\s+(?:the\s+)?total\s+[a-zA-Z0-9_]+|total\s+[a-zA-Z0-9_]+\s+(?:for|in|of|where)|sum\s+of\s+[a-zA-Z0-9_]+)\b", q_positive)
            and not re.search(r"\btotal\s+(?:records|rows|entries|observations|cases)\b", q_positive)
        )
    ):
        add_candidate(QueryIntent.SUM, 0.96, "Matches explicit summation calculation.")
    elif any(k in q_positive for k in ["sum of", "total of", "total sales", "total revenue", "total quantity", "total amount", "total marks", "sum"]) or re.search(r"\b(?:what is|what are|find|show|give me|tell me)\s+(?:the\s+)?([a-zA-Z0-9_]+)\s+for\s+", q_positive) or re.search(r"\b(?:sales|revenue|profit|price|cost|spending|quantity)\s+for\s+", q_positive):
        add_candidate(QueryIntent.SUM, 0.90, "Matches summation / metric inquiry for entity.")

    if "minimum" in q_positive or (re.search(r"\bmin\b", q_positive) and "minute" not in q_positive) or ("lowest" in q_positive and not any(w in q_positive for w in ["which", "who", "top", "bottom"])):
        add_candidate(QueryIntent.MINIMUM, 0.89, "Matches minimum aggregation keyword.")

    if "maximum" in q_positive or (re.search(r"\bmax\b", q_positive) and "maximum" not in q_positive) or ("highest" in q_positive and not any(w in q_positive for w in ["which", "who", "top", "bottom"])):
        add_candidate(QueryIntent.MAXIMUM, 0.89, "Matches maximum aggregation keyword.")

    # Grouping
    if (
        any(k in q_lower for k in [
            "group by", "grouped by", "group rows by", "grouping by", "grouping rows by",
            "per category", "for each"
        ])
        or re.search(r"\bgroup(?:ing)?(?:\s+rows)?\s+by\b", q_lower)
        or re.search(r"\b(?:by|per|for each)\s+[a-zA-Z0-9_]+\b", q_lower)
    ):
        group_score = 0.97 if re.search(r"\bgroup(?:ing)?(?:\s+rows)?\s+by\b", q_lower) else 0.93
        add_candidate(QueryIntent.GROUP_BY, group_score, "Matches grouping keywords.")

    # Filtering & Showing data
    if any(k in q_lower for k in ["where", "greater than", "less than", "is equal to", "filtered by", "more than", "above"]):
        add_candidate(QueryIntent.FILTER, 0.85, "Matches filter clause keywords.")

    if (
        (any(k in q_lower for k in ["show me records", "show data", "display rows", "view records", "show the first"])
        or re.search(r"^(?:show|display|view|list|get)\s+(?:me\s+)?(?:all\s+)?([a-zA-Z0-9_]+)\b", q_lower))
        and not any(k in q_lower for k in ["column name", "column names", "data type", "data types", "columns and", "all columns", "list columns", "show columns"])
    ):
        show_score = 0.94 if re.search(r"^(?:show|display|view|list|get)\s+(?:me\s+)?(?:all\s+)?([a-zA-Z0-9_]+)\s+where\b", q_lower) else 0.88
        add_candidate(QueryIntent.SHOW_DATA, show_score, "Matches raw records display inquiry.")

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
