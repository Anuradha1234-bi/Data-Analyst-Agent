"""Column Resolver with Semantic Matching, Lineage Inspection, and Ambiguity Safeguards.

Resolves natural language column mentions against dataset columns using:
1. Exact matching (preferred unconditionally when unambiguous).
2. Lineage inspection: distinguishes original base columns from join-generated suffixed duplicates.
3. Token overlap, string distance, and semantic synonyms.
4. Genuine ambiguity safeguards: when multiple distinct business metrics match, prompts for clarification with readable labels.
"""

from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Union
import re
import pandas as pd

from query.column_lineage import inspect_column_lineage, ColumnLineageInfo


# Semantic synonyms commonly found in analytical tabular datasets
SEMANTIC_SYNONYMS: Dict[str, List[str]] = {
    "price": ["cost", "rate", "amount", "modal_price", "min_price", "max_price", "value", "unit_price"],
    "sales": ["revenue", "turnover", "income", "amount", "total_sales", "receipts"],
    "quantity": ["qty", "volume", "units", "count", "arrivals", "arrival_quantity", "stock"],
    "market": ["mandi", "bazaar", "location", "center", "city", "region", "district", "place"],
    "commodity": ["product", "item", "crop", "good", "produce", "category"],
    "date": ["time", "day", "timestamp", "period", "month", "year", "created_at", "transaction_date"],
    "customer": ["client", "buyer", "user", "consumer", "account"],
    "profit": ["margin", "gain", "earnings", "net_profit"],
    "state": ["province", "region", "territory", "zone"],
}

# Extraction and system metadata patterns (PDF/OCR pagination, row/line offsets, system IDs)
EXTRACTION_METADATA_PATTERNS: List[str] = [
    r"^pdf[_\s]?page",
    r"^page[_\s]?(?:num|number|no|idx|index)?$",
    r"^line[_\s]?(?:num|number|no|idx|index)?$",
    r"^row[_\s]?(?:num|number|no|idx|index|id)?$",
    r"^unnamed",
    r"^(?:id|_id|index|idx)$",
    r"^bbox",
    r"^offset",
    r"^char[_\s]?(?:start|end|offset)",
    r"^token[_\s]?(?:idx|index|id)",
]

# Conversational and analytical stopwords that must not fuzzy-match to column names
RESOLVER_STOPWORDS = {
    "flagged", "failed", "passed", "case", "cases", "based", "criteria",
    "evidence", "explain", "record", "records", "data", "dataset",
    "which", "what", "where", "when", "show", "list", "find", "give",
    "tell", "highest", "lowest", "average", "mean", "total", "sum",
    "count", "each", "every", "all", "between", "across", "about",
    "risk", "level", "levels", "value", "values", "number", "numbers",
    "row", "rows", "column", "columns", "feature", "features", "metric",
    "metrics", "stat", "stats", "statistic", "statistics", "first",
    "second", "third", "last", "any", "some", "none", "true", "false",
}


def is_metadata_column(column_name: str) -> bool:
    """Check if a column represents technical or extraction metadata rather than a domain metric."""
    if not column_name:
        return False
    norm = re.sub(r"[^a-zA-Z0-9_]", "_", str(column_name).strip().lower())
    for pattern in EXTRACTION_METADATA_PATTERNS:
        if re.search(pattern, norm):
            return True
    return False


def filter_metadata_columns(columns: List[str]) -> List[str]:
    """Filter out technical and extraction metadata columns, returning domain columns."""
    return [c for c in columns if not is_metadata_column(c)]


def _normalize_name(name: str) -> str:
    """Normalize string by removing special characters, spaces, and converting to lowercase."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).lower())


def _extract_columns_from_metadata(metadata: Any) -> List[str]:
    """Extract list of column names from various metadata structures."""
    if not metadata:
        return []
    if isinstance(metadata, list):
        return [str(c) for c in metadata]
    if isinstance(metadata, dict):
        if "column_names" in metadata:
            return [str(c) for c in metadata["column_names"]]
        if "data_types" in metadata and isinstance(metadata["data_types"], dict):
            return [str(c) for c in metadata["data_types"].keys()]
        if "columns" in metadata:
            cols = metadata["columns"]
            if isinstance(cols, list):
                return [str(c) for c in cols]
            if isinstance(cols, dict):
                return [str(c) for c in cols.keys()]
            if isinstance(cols, int):
                pass
        if all(isinstance(v, (str, dict)) for v in metadata.values()):
            return [str(k) for k in metadata.keys() if k not in ("filename", "file_type", "rows", "columns")]
    if hasattr(metadata, "column_names"):
        return list(getattr(metadata, "column_names", []))
    if hasattr(metadata, "columns"):
        return list(getattr(metadata, "columns", []))
    return []


def resolve_column(
    requested_column: str,
    dataset_metadata: Any,
    column_type_filter: Optional[str] = None,  # "numeric", "categorical", "date", or None
    df: Optional[pd.DataFrame] = None,
    join_history: Optional[Dict[str, Any]] = None,
    lineage_map: Optional[Dict[str, ColumnLineageInfo]] = None,
) -> Dict[str, Any]:
    """Resolve a requested column string to an actual dataset column with lineage awareness.

    Contract:
    Returns:
    {
        "resolved": True/False,
        "column": "unit_price",
        "confidence": 1.0,
        "candidates": [...],
        "is_ambiguous": bool,
        "clarification_options": [...],
        "clarification_candidates": [...],
        "selection_explanation": Optional[str],
    }
    """
    if not requested_column or not str(requested_column).strip():
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    raw_req = str(requested_column).strip()
    norm_req = _normalize_name(raw_req)
    req_lower = raw_req.lower()

    columns = _extract_columns_from_metadata(dataset_metadata)
    if not columns:
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    # Extract data types if available from metadata or DataFrame
    dtypes: Dict[str, str] = {}
    if isinstance(dataset_metadata, dict) and "data_types" in dataset_metadata:
        dtypes = {str(k): str(v) for k, v in dataset_metadata["data_types"].items()}
    elif df is not None:
        dtypes = {str(c): str(df[c].dtype) for c in df.columns}

    # Inspect column lineage
    if lineage_map is None:
        ds_name = dataset_metadata.get("filename") if isinstance(dataset_metadata, dict) else None
        lineage_map = inspect_column_lineage(columns, data_types=dtypes, join_history=join_history, dataset_name=ds_name)

    # -------------------------------------------------------------------------
    # STEP 1: Exact Column-Name Match (Case-Insensitive or Normalized)
    # -------------------------------------------------------------------------
    exact_match: Optional[str] = None
    for col in columns:
        if col.lower() == req_lower:
            exact_match = col
            break

    if not exact_match:
        for col in columns:
            if _normalize_name(col) == norm_req:
                exact_match = col
                break

    if exact_match:
        # Check if there are join-generated suffixed duplicates of this exact match
        exact_lineage = lineage_map.get(exact_match)
        base = exact_lineage.base_name if exact_lineage else exact_match
        suffixed_dups = [
            c for c in columns
            if c != exact_match and lineage_map.get(c) and lineage_map[c].base_name.lower() == base.lower() and lineage_map[c].is_join_generated
        ]

        explanation = None
        if suffixed_dups:
            explanation = (
                f"Selected exact matching primary column '{exact_match}' "
                f"(preferred over join-generated duplicate '{suffixed_dups[0]}')."
            )

        return {
            "resolved": True,
            "column": exact_match,
            "confidence": 1.0,
            "candidates": [{"column": exact_match, "score": 1.0, "match_type": "exact"}],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": explanation,
        }

    # -------------------------------------------------------------------------
    # STEP 2: Score Candidate Columns Semantically
    # -------------------------------------------------------------------------
    candidates: List[Dict[str, Any]] = []

    # If the requested token is an ordinary English/analytical stopword, skip fuzzy matching
    is_stopword = (req_lower in RESOLVER_STOPWORDS or norm_req in RESOLVER_STOPWORDS)

    if not is_stopword:
        for col in columns:
            col_lower = col.lower()
            norm_col = _normalize_name(col)
            score = 0.0
            match_type = "none"

            col_lineage = lineage_map.get(col)
            base_lower = col_lineage.base_name.lower() if col_lineage else col_lower
            norm_base = _normalize_name(base_lower)

            # 1. Check substring containment on base name and full name (tokens >= 3 chars)
            if len(norm_req) >= 3 and len(norm_base) >= 3:
                if norm_req in norm_base:
                    score = 0.80 + (0.15 * (len(norm_req) / max(len(norm_base), 1)))
                    match_type = "base_substring"
                elif norm_base in norm_req and (len(norm_base) / max(len(norm_req), 1)) >= 0.5:
                    score = 0.75 + (0.15 * (len(norm_base) / max(len(norm_req), 1)))
                    match_type = "base_superstring"
                elif norm_req in norm_col:
                    score = 0.70 + (0.15 * (len(norm_req) / max(len(norm_col), 1)))
                    match_type = "substring"
                elif norm_col in norm_req and (len(norm_col) / max(len(norm_req), 1)) >= 0.5:
                    score = 0.65 + (0.15 * (len(norm_col) / max(len(norm_req), 1)))
                    match_type = "superstring"

            # 2. Fuzzy sequence matching against base name (require tokens >= 4 chars and score >= 0.72)
            if len(req_lower) >= 4 and len(base_lower) >= 4:
                seq_base = SequenceMatcher(None, req_lower, base_lower).ratio()
                if seq_base >= 0.72 and seq_base > score:
                    score = seq_base
                    match_type = "fuzzy_base"

                seq_full = SequenceMatcher(None, req_lower, col_lower).ratio()
                if seq_full >= 0.72 and seq_full > score:
                    score = seq_full
                    match_type = "fuzzy"

            # 3. Check semantic synonyms against base name
            for concept, syns in SEMANTIC_SYNONYMS.items():
                req_matches_concept = (req_lower == concept or req_lower in syns or norm_req in [_normalize_name(s) for s in syns])
                col_matches_concept = (base_lower == concept or any(s in base_lower for s in syns))
                if req_matches_concept and col_matches_concept:
                    syn_score = 0.85
                    if syn_score > score:
                        score = syn_score
                        match_type = f"synonym_{concept}"

            if score >= 0.70:
                candidates.append({
                    "column": col,
                    "score": round(score, 3),
                    "match_type": match_type,
                    "base_name": col_lineage.base_name if col_lineage else col,
                    "is_join_generated": col_lineage.is_join_generated if col_lineage else False,
                })

    # Sort candidates by descending score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    if not candidates:
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    # -------------------------------------------------------------------------
    # STEP 3: Inspect Lineage and Ambiguity Among Top Candidates
    # -------------------------------------------------------------------------
    top_candidate = candidates[0]
    top_score = top_candidate["score"]

    if top_score < 0.70:
        return {
            "resolved": False,
            "column": None,
            "confidence": top_score,
            "candidates": candidates,
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    plausible_candidates = [
        c for c in candidates
        if c["score"] >= 0.70 and (top_score - c["score"]) <= 0.15
    ]

    # Also check token containment columns (e.g. "price" inside "modal_price", "min_price")
    matching_token_cols = []
    if not is_stopword:
        matching_token_cols = [
            col for col in columns
            if norm_req in _normalize_name(col).split("_")
            or any(norm_req == token for token in re.findall(r"[a-zA-Z]+", col.lower()))
        ]

    all_matched_cols = list(set([c["column"] for c in plausible_candidates] + matching_token_cols))

    if len(all_matched_cols) > 1:
        # Group candidate columns by their base name using lineage
        unique_bases = set()
        base_to_cols: Dict[str, List[str]] = {}

        for col in all_matched_cols:
            lin = lineage_map.get(col)
            base = lin.base_name if lin else col
            unique_bases.add(base.lower())
            base_to_cols.setdefault(base.lower(), []).append(col)

        # SUB-CASE A: All candidate columns share the EXACT SAME base name!
        # e.g. "unit_price" and "unit_price_joined_orders__1__customers_1"
        if len(unique_bases) == 1:
            matching_cols = list(base_to_cols.values())[0]
            # Check if there is an original (un-suffixed) base column
            original_candidates = [
                c for c in matching_cols
                if lineage_map.get(c) and not lineage_map[c].is_join_generated
            ]
            joined_candidates = [
                c for c in matching_cols
                if lineage_map.get(c) and lineage_map[c].is_join_generated
            ]

            if original_candidates:
                chosen_col = original_candidates[0]
                explanation = (
                    f"Selected primary column '{chosen_col}' "
                    f"(preferred over join-generated duplicate '{joined_candidates[0]}')."
                    if joined_candidates else None
                )
                return {
                    "resolved": True,
                    "column": chosen_col,
                    "confidence": 0.95,
                    "candidates": candidates,
                    "is_ambiguous": False,
                    "clarification_options": [],
                    "clarification_candidates": [],
                    "selection_explanation": explanation,
                }

        # SUB-CASE B: Multiple distinct base names exist!
        # e.g. "Modal_Price", "Min_Price", "Max_Price"
        # Ambiguity is genuine and material!
        candidate_lineage_dicts = [
            lineage_map[c].to_dict() for c in all_matched_cols if c in lineage_map
        ]
        labels = [
            lineage_map[c].clarification_label for c in all_matched_cols if c in lineage_map
        ]

        return {
            "resolved": False,
            "column": None,
            "confidence": top_score,
            "candidates": candidates,
            "is_ambiguous": True,
            "clarification_options": all_matched_cols,
            "clarification_candidates": candidate_lineage_dicts,
            "clarification_labels": labels,
            "selection_explanation": None,
        }

    # Single unambiguous candidate
    chosen = top_candidate["column"]
    chosen_lineage = lineage_map.get(chosen)
    explanation = None
    if chosen_lineage and chosen_lineage.is_join_generated:
        explanation = f"Selected column '{chosen}' ({chosen_lineage.clarification_label})."

    return {
        "resolved": True,
        "column": chosen,
        "confidence": top_score,
        "candidates": candidates,
        "is_ambiguous": False,
        "clarification_options": [],
        "clarification_candidates": [],
        "selection_explanation": explanation,
    }
