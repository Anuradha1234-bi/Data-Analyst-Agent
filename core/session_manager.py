"""Session state manager for Streamlit application.

Safely initializes, manages, and synchronizes application session state variables
for both single-dataset and multi-dataset cross-file analysis sessions.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
try:
    from streamlit.logger import get_logger
    for _logger_name in [
        'streamlit',
        'streamlit.runtime.scriptrunner_utils.script_run_context',
        'streamlit.runtime.state.session_state_proxy',
    ]:
        get_logger(_logger_name).disabled = True
except Exception:
    pass
import streamlit as st


class SessionManager:
    """Manages Streamlit session state lifecycle, multi-dataset persistence, and defaults."""

    DEFAULT_STATE: Dict[str, Any] = {
        # Single-file / active dataset backward compatibility
        "dataset": None,
        "original_df": None,
        "cleaned_df": None,
        "active_dataset_view": "original",
        "has_cleaned": False,
        "cleaning_config": None,
        "cleaning_summary": None,
        "cleaning_log": [],
        "dataset_name": None,
        "dataset_type": None,
        "dataset_loaded": False,
        "profile": None,
        "original_profile": None,
        "cleaned_profile": None,
        "analysis_history": [],
        "current_question": "",
        "current_result": None,

        # Multi-dataset state (Exact Section 18 keys)
        "datasets": {},                   # Dict[str, pd.DataFrame] (active views: cleaned or orig)
        "original_datasets": {},          # Dict[str, pd.DataFrame] (untouched uploads)
        "cleaned_datasets": {},           # Dict[str, pd.DataFrame] (cleaned versions)
        "dataset_metadata": {},           # Dict[str, DatasetMetadata]
        "relationships": [],              # List[Relationship]
        "join_audit": [],                 # List[JoinAudit]
        "analysis_history": [],           # List[Dict[str, Any]]

        # Internal multi-dataset tracking
        "dataset_types": {},              # Dict[str, str] (e.g. "CSV", "XLSX", "XLS")
        "dataset_metadata_map": {},       # Dict[str, DatasetMetadata]
        "dataset_profiles": {},           # Dict[str, Dict[str, ProfileResult]]
        "dataset_cleaning_summaries": {}, # Dict[str, Any]
        "dataset_cleaning_configs": {},   # Dict[str, Any]
        "active_selected_dataset": None,  # str (active dataset name for inspection)
        "detected_relationships": [],     # List[Relationship]
        "join_audit_log": [],             # List[JoinAudit]
        "confirmed_joins": {},            # Dict[str, bool] (key_id -> bool)

        # Phase 4 Anomaly & Outlier Detection state
        "anomaly_results": {},            # Dict[str, Dict[str, Any]] (dataset_name -> {method -> result})
        "anomaly_datasets": {},           # Dict[str, pd.DataFrame] (flagged dataset versions)
        "treated_datasets": {},           # Dict[str, pd.DataFrame] (treated dataset versions)
        "anomaly_config": {},             # Dict[str, Any] (method and parameters)
        "anomaly_audit_log": [],          # List[Dict[str, Any]] (treatment audits)

        # Phase 5 Intelligent Data Analysis & Insight Generation
        "analysis_results": {},           # Dict[str, Any] (dataset_name -> DatasetAnalysisResult)
        "insights": {},                   # Dict[str, List[Any]] (dataset_name -> List[Insight])
        "trend_results": {},              # Dict[str, List[Any]] (dataset_name -> List[TrendAnalysisResult])
        "correlation_results": {},        # Dict[str, Any] (dataset_name -> CorrelationAnalysisResult)
        "category_analysis": {},          # Dict[str, Dict[str, Any]] (dataset_name -> {col -> CategoryBreakdownResult})
        "phase5_analysis": None,          # Dict[str, Any] (latest run_phase5_analysis payload)
        "phase5_config": {},              # Dict[str, Any] (user configuration for Phase 5 analysis)

        # Phase 6 Intelligent Ask Analyst & Natural-Language Data Query
        "ask_analyst_history": [],        # List[Dict[str, Any]] (session-scoped natural language query history)
        "ask_analyst_context": {},        # Dict[str, Any] (conversation follow-up context)
        "query_config": {},               # Dict[str, Any] (Phase 6 query engine configuration)

        # Phase 5 Intelligent Prediction & Forecasting Engine
        "prediction_results": {},         # Dict[str, Any] (dataset_name -> PredictionResult)
        "prediction_history": [],         # List[Dict[str, Any]] (lightweight execution history)
        "prediction_config": {},          # Dict[str, Any] (user configuration for Prediction Engine)
    }

    @classmethod
    def init(cls) -> None:
        """Initialize all session state keys with safe defaults if not present."""
        for key, default_value in cls.DEFAULT_STATE.items():
            if key not in st.session_state:
                if isinstance(default_value, list):
                    st.session_state[key] = list(default_value)
                elif isinstance(default_value, dict):
                    st.session_state[key] = dict(default_value)
                else:
                    st.session_state[key] = default_value

    @classmethod
    def initialize(cls) -> None:
        """Alias for init()."""
        cls.init()

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get value from session state with optional fallback."""
        return st.session_state.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set key in session state."""
        st.session_state[key] = value

    # =========================================================================
    # MULTI-DATASET REGISTRATION & LIFECYCLE
    # =========================================================================

    @classmethod
    def add_dataset(cls, df: pd.DataFrame, filename: str, file_type: str) -> None:
        """Add or update an uploaded dataset in multi-dataset storage without replacing other files."""
        cls.init()
        datasets = st.session_state.get("datasets", {})
        original_datasets = st.session_state.get("original_datasets", {})
        cleaned_datasets = st.session_state.get("cleaned_datasets", {})
        dataset_types = st.session_state.get("dataset_types", {})

        # Deep copies to guarantee independence and immutability of originals
        df_orig = df.copy(deep=True)
        df_clean = df.copy(deep=True)

        original_datasets[filename] = df_orig
        cleaned_datasets[filename] = df_clean
        datasets[filename] = df_orig.copy(deep=True)
        dataset_types[filename] = file_type

        st.session_state["datasets"] = datasets
        st.session_state["original_datasets"] = original_datasets
        st.session_state["cleaned_datasets"] = cleaned_datasets
        st.session_state["dataset_types"] = dataset_types
        st.session_state["dataset_loaded"] = True

        # Sync Section 18 keys
        try:
            from core.dataset_manager import DatasetManager
            meta = DatasetManager.extract_metadata(df_orig, filename, file_type)
            metadata_map = st.session_state.get("dataset_metadata_map", {})
            metadata_map[filename] = meta
            st.session_state["dataset_metadata_map"] = metadata_map
            st.session_state["dataset_metadata"] = metadata_map
        except Exception:
            pass

        # If no active selected dataset, or only one dataset, set active
        current_active = st.session_state.get("active_selected_dataset")
        if not current_active or current_active not in datasets or len(datasets) == 1:
            cls.set_active_dataset(filename)

    @classmethod
    def remove_dataset(cls, filename: str) -> None:
        """Remove a single dataset from session without affecting other uploaded datasets."""
        datasets = st.session_state.get("datasets", {})
        original_datasets = st.session_state.get("original_datasets", {})
        cleaned_datasets = st.session_state.get("cleaned_datasets", {})
        dataset_types = st.session_state.get("dataset_types", {})
        dataset_profiles = st.session_state.get("dataset_profiles", {})
        dataset_cleaning_summaries = st.session_state.get("dataset_cleaning_summaries", {})
        dataset_cleaning_configs = st.session_state.get("dataset_cleaning_configs", {})
        dataset_metadata_map = st.session_state.get("dataset_metadata_map", {})

        datasets.pop(filename, None)
        original_datasets.pop(filename, None)
        cleaned_datasets.pop(filename, None)
        dataset_types.pop(filename, None)
        dataset_profiles.pop(filename, None)
        dataset_cleaning_summaries.pop(filename, None)
        dataset_cleaning_configs.pop(filename, None)
        dataset_metadata_map.pop(filename, None)
        anomaly_results = st.session_state.get("anomaly_results", {})
        anomaly_results.pop(filename, None)
        st.session_state["anomaly_results"] = anomaly_results

        # Phase 5 cache eviction
        analysis_results = st.session_state.get("analysis_results", {})
        analysis_results.pop(filename, None)
        st.session_state["analysis_results"] = analysis_results
        insights = st.session_state.get("insights", {})
        insights.pop(filename, None)
        st.session_state["insights"] = insights
        st.session_state.pop(f"analysis_result_{filename}", None)

        st.session_state["datasets"] = datasets
        st.session_state["original_datasets"] = original_datasets
        st.session_state["cleaned_datasets"] = cleaned_datasets
        st.session_state["dataset_types"] = dataset_types
        st.session_state["dataset_profiles"] = dataset_profiles
        st.session_state["dataset_cleaning_summaries"] = dataset_cleaning_summaries
        st.session_state["dataset_cleaning_configs"] = dataset_cleaning_configs
        st.session_state["dataset_metadata_map"] = dataset_metadata_map
        st.session_state["dataset_metadata"] = dataset_metadata_map

        # Filter out relationships that referenced the deleted file
        existing_rels = st.session_state.get("detected_relationships", [])
        updated_rels = [
            r for r in existing_rels
            if getattr(r, "source_dataset", None) != filename and getattr(r, "target_dataset", None) != filename
        ]
        st.session_state["detected_relationships"] = updated_rels
        st.session_state["relationships"] = updated_rels

        # Update active selected dataset
        if datasets:
            first_key = next(iter(datasets.keys()))
            cls.set_active_dataset(first_key)
        else:
            cls.reset_dataset()

    @classmethod
    def set_dataset(cls, df: pd.DataFrame, filename: str, file_type: str) -> None:
        """Register an uploaded dataset in session state.

        Supports both single-file operations and acts as add_dataset for multi-file sessions.
        """
        cls.add_dataset(df, filename, file_type)
        cls.sync_active_to_legacy()

    @classmethod
    def set_active_dataset(cls, filename: str) -> None:
        """Set the active dataset to inspect in single-dataset views."""
        st.session_state["active_selected_dataset"] = filename
        st.session_state["dataset_name"] = filename
        datasets = st.session_state.get("datasets", {})
        if filename in datasets:
            cls.sync_active_to_legacy()

    @classmethod
    def set_active_dataset_name(cls, filename: str) -> None:
        """Set the active dataset name."""
        cls.set_active_dataset(filename)

    @classmethod
    def get_active_dataset_name(cls) -> Optional[str]:
        """Return the filename of the active selected dataset."""
        active = st.session_state.get("active_selected_dataset")
        if active and active in st.session_state.get("datasets", {}):
            return active
        datasets = st.session_state.get("datasets", {})
        if datasets:
            return next(iter(datasets.keys()))
        return st.session_state.get("dataset_name")

    @classmethod
    def sync_active_to_legacy(cls) -> None:
        """Synchronize the active dataset's attributes to legacy single-dataset session keys."""
        active_name = cls.get_active_dataset_name()
        if not active_name:
            return

        orig_df = st.session_state.get("original_datasets", {}).get(active_name)
        clean_df = st.session_state.get("cleaned_datasets", {}).get(active_name)
        active_df = st.session_state.get("datasets", {}).get(active_name)
        file_type = st.session_state.get("dataset_types", {}).get(active_name, "CSV")
        summary = st.session_state.get("dataset_cleaning_summaries", {}).get(active_name)
        config = st.session_state.get("dataset_cleaning_configs", {}).get(active_name)
        profiles = st.session_state.get("dataset_profiles", {}).get(active_name, {})

        st.session_state["dataset_name"] = active_name
        st.session_state["dataset_type"] = file_type
        st.session_state["original_df"] = orig_df
        st.session_state["cleaned_df"] = clean_df
        st.session_state["dataset"] = active_df
        st.session_state["has_cleaned"] = summary is not None
        st.session_state["cleaning_summary"] = summary
        st.session_state["cleaning_config"] = config
        st.session_state["original_profile"] = profiles.get("original")
        st.session_state["cleaned_profile"] = profiles.get("cleaned")
        active_view = st.session_state.get("active_dataset_view", "original")
        st.session_state["profile"] = profiles.get(active_view)
        st.session_state["dataset_loaded"] = True

    # =========================================================================
    # RETRIEVAL HELPERS
    # =========================================================================

    @classmethod
    def get_datasets(cls) -> Dict[str, pd.DataFrame]:
        """Return the dictionary of active datasets."""
        datasets = st.session_state.get("datasets", {})
        if not datasets and st.session_state.get("dataset") is not None:
            name = st.session_state.get("dataset_name") or "dataset.csv"
            return {name: st.session_state["dataset"]}
        return datasets

    @classmethod
    def get_all_active_datasets(cls) -> Dict[str, pd.DataFrame]:
        """Alias for get_datasets for compatibility."""
        return cls.get_datasets()

    @classmethod
    def get_original_datasets(cls) -> Dict[str, pd.DataFrame]:
        """Return dictionary of untouched original datasets."""
        origs = st.session_state.get("original_datasets", {})
        if not origs and st.session_state.get("original_df") is not None:
            name = st.session_state.get("dataset_name") or "dataset.csv"
            return {name: st.session_state["original_df"]}
        return origs

    @classmethod
    def get_cleaned_datasets(cls) -> Dict[str, pd.DataFrame]:
        """Return dictionary of cleaned datasets."""
        cleans = st.session_state.get("cleaned_datasets", {})
        if not cleans and st.session_state.get("cleaned_df") is not None:
            name = st.session_state.get("dataset_name") or "dataset.csv"
            return {name: st.session_state["cleaned_df"]}
        return cleans

    @classmethod
    def get_all_filenames(cls) -> List[str]:
        """Return list of all uploaded dataset filenames."""
        return list(cls.get_datasets().keys())

    @classmethod
    def get_dataset_by_name(cls, filename: str, view: str = "active") -> Optional[pd.DataFrame]:
        """Retrieve a specific dataset by name for a given view ('active', 'original', 'cleaned')."""
        if view == "original":
            return st.session_state.get("original_datasets", {}).get(filename)
        elif view == "cleaned":
            return st.session_state.get("cleaned_datasets", {}).get(filename)
        return st.session_state.get("datasets", {}).get(filename)

    @classmethod
    def get_dataset_count(cls) -> int:
        """Return count of uploaded datasets."""
        return len(cls.get_all_filenames())

    @classmethod
    def get_total_rows(cls) -> int:
        """Return sum of rows across all uploaded datasets."""
        return sum(len(df) for df in cls.get_datasets().values())

    @classmethod
    def get_total_columns(cls) -> int:
        """Return sum of columns across all uploaded datasets."""
        return sum(len(df.columns) for df in cls.get_datasets().values())

    # =========================================================================
    # SINGLE-FILE / ACTIVE DATASET COMPATIBILITY METHODS
    # =========================================================================

    @classmethod
    def reset_dataset(cls) -> None:
        """Reset dataset, profile, and all active analytical states."""
        for key, default_value in cls.DEFAULT_STATE.items():
            if isinstance(default_value, list):
                st.session_state[key] = []
            elif isinstance(default_value, dict):
                st.session_state[key] = {}
            else:
                st.session_state[key] = default_value

    @classmethod
    def set_cleaned_dataset(cls, df: pd.DataFrame, summary: Any, config: Any = None, filename: Optional[str] = None) -> None:
        """Register a cleaned dataframe and summary for a specific or currently active dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            target_name = st.session_state.get("dataset_name") or "dataset.csv"

        cleaned_df_copy = df.copy(deep=True)

        cleaned_datasets = st.session_state.get("cleaned_datasets", {})
        cleaned_datasets[target_name] = cleaned_df_copy
        st.session_state["cleaned_datasets"] = cleaned_datasets

        datasets = st.session_state.get("datasets", {})
        datasets[target_name] = cleaned_df_copy.copy(deep=True)
        st.session_state["datasets"] = datasets

        summaries = st.session_state.get("dataset_cleaning_summaries", {})
        summaries[target_name] = summary
        st.session_state["dataset_cleaning_summaries"] = summaries

        if config is not None:
            configs = st.session_state.get("dataset_cleaning_configs", {})
            configs[target_name] = config
            st.session_state["dataset_cleaning_configs"] = configs

        # Invalidate cached cleaned profile for this dataset
        profiles = st.session_state.get("dataset_profiles", {})
        if target_name in profiles:
            profiles[target_name]["cleaned"] = None
        st.session_state["dataset_profiles"] = profiles

        # If this is the active dataset, sync to legacy session keys
        if target_name == cls.get_active_dataset_name():
            st.session_state["cleaned_df"] = cleaned_df_copy
            st.session_state["dataset"] = cleaned_df_copy.copy(deep=True)
            st.session_state["cleaning_summary"] = summary
            if config is not None:
                st.session_state["cleaning_config"] = config
            st.session_state["has_cleaned"] = True
            st.session_state["active_dataset_view"] = "cleaned"
            st.session_state["cleaned_profile"] = None
            st.session_state["profile"] = None

        # Append summary changes to session cleaning log
        if hasattr(summary, "log_entries") and summary.log_entries:
            curr_log = st.session_state.get("cleaning_log", [])
            curr_log.extend(summary.log_entries)
            st.session_state["cleaning_log"] = curr_log

    @classmethod
    def reset_to_original(cls, filename: Optional[str] = None) -> None:
        """Revert cleaned dataset back to the untouched original uploaded version."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            return

        orig = st.session_state.get("original_datasets", {}).get(target_name)
        if orig is not None:
            cleaned_datasets = st.session_state.get("cleaned_datasets", {})
            cleaned_datasets[target_name] = orig.copy(deep=True)
            st.session_state["cleaned_datasets"] = cleaned_datasets

            datasets = st.session_state.get("datasets", {})
            datasets[target_name] = orig.copy(deep=True)
            st.session_state["datasets"] = datasets

            summaries = st.session_state.get("dataset_cleaning_summaries", {})
            summaries.pop(target_name, None)
            st.session_state["dataset_cleaning_summaries"] = summaries

            configs = st.session_state.get("dataset_cleaning_configs", {})
            configs.pop(target_name, None)
            st.session_state["dataset_cleaning_configs"] = configs

            profiles = st.session_state.get("dataset_profiles", {})
            if target_name in profiles:
                profiles[target_name]["cleaned"] = None
            st.session_state["dataset_profiles"] = profiles

            if target_name == cls.get_active_dataset_name():
                st.session_state["cleaned_df"] = orig.copy(deep=True)
                st.session_state["dataset"] = orig.copy(deep=True)
                st.session_state["has_cleaned"] = False
                st.session_state["active_dataset_view"] = "original"
                st.session_state["cleaning_summary"] = None
                st.session_state["cleaning_config"] = None
                st.session_state["cleaned_profile"] = None
                st.session_state["profile"] = profiles.get(target_name, {}).get("original")

    @classmethod
    def get_original_df(cls, filename: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Return an independent copy of the untouched original DataFrame of the active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name and target_name in st.session_state.get("original_datasets", {}):
            return st.session_state["original_datasets"][target_name].copy(deep=True)
        orig = st.session_state.get("original_df")
        return orig.copy(deep=True) if orig is not None else None

    @classmethod
    def get_cleaned_df(cls, filename: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Return the working cleaned DataFrame of the active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name and target_name in st.session_state.get("cleaned_datasets", {}):
            return st.session_state["cleaned_datasets"][target_name].copy(deep=True)
        cleaned = st.session_state.get("cleaned_df")
        return cleaned.copy(deep=True) if cleaned is not None else None

    @classmethod
    def get_cleaning_config(cls, filename: Optional[str] = None) -> Optional[Any]:
        """Return the CleaningConfig for a specific dataset or active dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name and target_name in st.session_state.get("dataset_cleaning_configs", {}):
            return st.session_state["dataset_cleaning_configs"][target_name]
        return st.session_state.get("cleaning_config")

    @classmethod
    def get_active_df(cls) -> Optional[pd.DataFrame]:
        """Return the DataFrame corresponding to the active view ('cleaned' vs 'original') for active dataset."""
        active_name = cls.get_active_dataset_name()
        view = st.session_state.get("active_dataset_view", "original")
        if active_name:
            if view == "cleaned" and active_name in st.session_state.get("cleaned_datasets", {}):
                return st.session_state["cleaned_datasets"][active_name]
            return st.session_state.get("original_datasets", {}).get(active_name)
        if view == "cleaned" and st.session_state.get("cleaned_df") is not None:
            return st.session_state.get("cleaned_df")
        return st.session_state.get("original_df")

    @classmethod
    def set_active_view(cls, view: str) -> None:
        """Switch active dataset view between 'original' and 'cleaned'."""
        if view in ("original", "cleaned"):
            st.session_state["active_dataset_view"] = view
            active_name = cls.get_active_dataset_name()
            if active_name:
                active_df = cls.get_active_df()
                st.session_state["dataset"] = active_df
                if active_name in st.session_state.get("datasets", {}):
                    st.session_state["datasets"][active_name] = active_df
                profiles = st.session_state.get("dataset_profiles", {}).get(active_name, {})
                st.session_state["profile"] = profiles.get(view)
            else:
                st.session_state["dataset"] = cls.get_active_df()
                if view == "original":
                    st.session_state["profile"] = st.session_state.get("original_profile")
                else:
                    st.session_state["profile"] = st.session_state.get("cleaned_profile")

    @classmethod
    def get_active_view(cls) -> str:
        """Get current active dataset view identifier ('original' or 'cleaned')."""
        return st.session_state.get("active_dataset_view", "original")

    @classmethod
    def has_cleaned_dataset(cls, filename: Optional[str] = None) -> bool:
        """Check if cleaning operations have been applied to produce a cleaned dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name:
            return bool(st.session_state.get("dataset_cleaning_summaries", {}).get(target_name) is not None)
        return bool(st.session_state.get("has_cleaned", False) and st.session_state.get("cleaned_df") is not None)

    @classmethod
    def set_profile(cls, profile: Any, for_view: Optional[str] = None, filename: Optional[str] = None) -> None:
        """Store dataset profile in session state for active view or specific dataset view."""
        target_name = filename or cls.get_active_dataset_name()
        view = for_view or cls.get_active_view()

        if target_name:
            profiles = st.session_state.get("dataset_profiles", {})
            if target_name not in profiles:
                profiles[target_name] = {}
            profiles[target_name][view] = profile
            st.session_state["dataset_profiles"] = profiles

        if not target_name or target_name == cls.get_active_dataset_name():
            if view == "original":
                st.session_state["original_profile"] = profile
            else:
                st.session_state["cleaned_profile"] = profile
            st.session_state["profile"] = profile

    @classmethod
    def get_profile(cls, for_view: Optional[str] = None, filename: Optional[str] = None) -> Optional[Any]:
        """Retrieve cached dataset profile for active or specific view and dataset."""
        target_name = filename or cls.get_active_dataset_name()
        view = for_view or cls.get_active_view()

        if target_name:
            profiles = st.session_state.get("dataset_profiles", {}).get(target_name, {})
            if view in profiles:
                return profiles[view]

        if view == "original":
            return st.session_state.get("original_profile")
        return st.session_state.get("cleaned_profile")

    @classmethod
    def has_profile(cls, for_view: Optional[str] = None, filename: Optional[str] = None) -> bool:
        """Check if profile is cached for active or specific view."""
        return cls.get_profile(for_view, filename) is not None

    @classmethod
    def get_all_profiles(cls, view: str = "original") -> Dict[str, Any]:
        """Retrieve cached profiles for all uploaded datasets."""
        res: Dict[str, Any] = {}
        profiles = st.session_state.get("dataset_profiles", {})
        for ds_name, pdict in profiles.items():
            if isinstance(pdict, dict) and view in pdict and pdict[view] is not None:
                res[ds_name] = pdict[view]
            elif isinstance(pdict, dict) and "original" in pdict and pdict["original"] is not None:
                res[ds_name] = pdict["original"]
        # Fallback to single profile in session state
        if not res and st.session_state.get("profile") is not None:
            name = st.session_state.get("dataset_name") or "dataset.csv"
            res[name] = st.session_state["profile"]
        return res

    @classmethod
    def is_dataset_loaded(cls) -> bool:
        """Check if any active dataset is currently loaded in session."""
        datasets = st.session_state.get("datasets", {})
        if datasets:
            return True
        return bool(
            st.session_state.get("dataset_loaded", False)
            and (st.session_state.get("original_df") is not None or st.session_state.get("dataset") is not None)
        )

    @classmethod
    def get_dataset(cls) -> Optional[pd.DataFrame]:
        """Return the active DataFrame from session state."""
        return cls.get_active_df()

    @classmethod
    def get_dataset_name(cls) -> Optional[str]:
        """Return the active dataset filename or None."""
        return cls.get_active_dataset_name()

    @classmethod
    def get_dataset_type(cls) -> Optional[str]:
        """Return the active dataset format type (CSV/XLSX/XLS) or None."""
        active_name = cls.get_active_dataset_name()
        if active_name and active_name in st.session_state.get("dataset_types", {}):
            return st.session_state["dataset_types"][active_name]
        return st.session_state.get("dataset_type")

    @classmethod
    def get_row_count(cls) -> int:
        """Return row count of active dataset or 0."""
        df = cls.get_active_df()
        return len(df) if df is not None else 0

    @classmethod
    def get_column_count(cls) -> int:
        """Return column count of active dataset or 0."""
        df = cls.get_active_df()
        return len(df.columns) if df is not None else 0

    # =========================================================================
    # RELATIONSHIPS & JOIN AUDIT LOGGING
    # =========================================================================

    @classmethod
    def set_relationships(cls, relationships: List[Any]) -> None:
        """Cache detected dataset relationships in session state."""
        st.session_state["detected_relationships"] = list(relationships)
        st.session_state["relationships"] = list(relationships)

    @classmethod
    def get_relationships(cls) -> List[Any]:
        """Retrieve detected dataset relationships."""
        return st.session_state.get("relationships") or st.session_state.get("detected_relationships", [])

    @classmethod
    def confirm_relationship(cls, key_id: str) -> None:
        """Mark a relationship as confirmed by the user."""
        confirmed = st.session_state.get("confirmed_joins", {})
        confirmed[key_id] = True
        st.session_state["confirmed_joins"] = confirmed
        # Also mark confirmed in relationship objects
        for rel in st.session_state.get("detected_relationships", []):
            if getattr(rel, "key_id", None) == key_id:
                setattr(rel, "confirmed_by_user", True)

    @classmethod
    def is_relationship_confirmed(cls, key_id: str) -> bool:
        """Check if user has confirmed a specific candidate relationship."""
        return bool(st.session_state.get("confirmed_joins", {}).get(key_id, False))

    @classmethod
    def add_join_audit(cls, audit: Any) -> None:
        """Append a join audit record to internal log."""
        log = st.session_state.get("join_audit_log", [])
        log.append(audit)
        st.session_state["join_audit_log"] = log
        st.session_state["join_audit"] = log

    @classmethod
    def get_join_audits(cls) -> List[Any]:
        """Retrieve full join audit history."""
        return st.session_state.get("join_audit") or st.session_state.get("join_audit_log", [])

    @classmethod
    def get_join_audit(cls) -> List[Any]:
        """Retrieve full join audit history (alias for get_join_audits)."""
        return cls.get_join_audits()


    # =========================================================================
    # PHASE 4 ANOMALY DETECTION STATE MANAGEMENT
    # =========================================================================

    @classmethod
    def set_anomaly_results(cls, results: Dict[str, Any], filename: Optional[str] = None) -> None:
        """Store anomaly detection results for active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            target_name = st.session_state.get("dataset_name") or "dataset.csv"

        anomaly_results = st.session_state.get("anomaly_results", {})
        anomaly_results[target_name] = results
        st.session_state["anomaly_results"] = anomaly_results

    @classmethod
    def get_anomaly_results(cls, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve anomaly detection results for active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            target_name = st.session_state.get("dataset_name") or "dataset.csv"
        return st.session_state.get("anomaly_results", {}).get(target_name)

    @classmethod
    def clear_anomaly_results(cls, filename: Optional[str] = None) -> None:
        """Clear anomaly detection results for a given dataset or active dataset."""
        target_name = filename or cls.get_active_dataset_name()
        anomaly_results = st.session_state.get("anomaly_results", {})
        if target_name in anomaly_results:
            anomaly_results.pop(target_name, None)
            st.session_state["anomaly_results"] = anomaly_results

    @classmethod
    def get_all_anomaly_results(cls) -> Dict[str, Dict[str, Any]]:
        """Retrieve anomaly detection results across all datasets."""
        return st.session_state.get("anomaly_results", {})

    @classmethod
    def add_anomaly_treatment_audit(cls, audit: Any) -> None:
        """Append an outlier treatment record to session audit history."""
        audits = st.session_state.get("anomaly_audit_log", [])
        audits.append(audit)
        st.session_state["anomaly_audit_log"] = audits

    @classmethod
    def get_anomaly_treatment_audits(cls) -> List[Any]:
        """Retrieve outlier treatment audit history."""
        return st.session_state.get("anomaly_audit_log", [])

    @classmethod
    def set_anomaly_dataset(cls, df: pd.DataFrame, filename: Optional[str] = None) -> None:
        """Store anomaly-flagged dataset in session state."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name:
            ad = st.session_state.get("anomaly_datasets", {})
            ad[target_name] = df.copy(deep=True)
            st.session_state["anomaly_datasets"] = ad

    @classmethod
    def get_anomaly_dataset(cls, filename: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Retrieve anomaly-flagged dataset from session state."""
        target_name = filename or cls.get_active_dataset_name()
        return st.session_state.get("anomaly_datasets", {}).get(target_name)

    @classmethod
    def set_treated_dataset(cls, df: pd.DataFrame, filename: Optional[str] = None) -> None:
        """Store treated dataset version in session state."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name:
            td = st.session_state.get("treated_datasets", {})
            td[target_name] = df.copy(deep=True)
            st.session_state["treated_datasets"] = td

    @classmethod
    def get_treated_dataset(cls, filename: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Retrieve treated dataset version from session state."""
        target_name = filename or cls.get_active_dataset_name()
        return st.session_state.get("treated_datasets", {}).get(target_name)

    @classmethod
    def get_anomaly_config(cls) -> Dict[str, Any]:
        """Retrieve anomaly detection configuration from session state."""
        from analysis.config import get_default_anomaly_config
        return st.session_state.get("anomaly_config") or get_default_anomaly_config()

    @classmethod
    def set_anomaly_config(cls, config: Dict[str, Any]) -> None:
        """Store anomaly detection configuration in session state."""
        st.session_state["anomaly_config"] = config

    # =========================================================================
    # PHASE 5 INTELLIGENT DATA ANALYSIS & INSIGHTS STATE MANAGEMENT
    # =========================================================================

    @classmethod
    def set_analysis_result(cls, result: Any, filename: Optional[str] = None) -> None:
        """Store comprehensive analysis result for active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            target_name = st.session_state.get("dataset_name") or "dataset.csv"

        analysis_map = st.session_state.get("analysis_results", {})
        analysis_map[target_name] = result
        st.session_state["analysis_results"] = analysis_map
        st.session_state[f"analysis_result_{target_name}"] = result

    @classmethod
    def get_analysis_result(cls, filename: Optional[str] = None) -> Optional[Any]:
        """Retrieve analysis result for active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            target_name = st.session_state.get("dataset_name") or "dataset.csv"
        return st.session_state.get("analysis_results", {}).get(target_name)

    @classmethod
    def get_all_analysis_results(cls) -> Dict[str, Any]:
        """Retrieve analysis results across all datasets."""
        return st.session_state.get("analysis_results", {})

    @classmethod
    def clear_analysis_result(cls, filename: Optional[str] = None) -> None:
        """Clear cached analysis and insights for active or specified dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if target_name:
            analysis_map = st.session_state.get("analysis_results", {})
            analysis_map.pop(target_name, None)
            st.session_state["analysis_results"] = analysis_map

            insights_map = st.session_state.get("insights", {})
            insights_map.pop(target_name, None)
            st.session_state["insights"] = insights_map

            st.session_state.pop(f"analysis_result_{target_name}", None)

    @classmethod
    def get_all_insights(cls) -> List[Any]:
        """Retrieve all flattened insights across all datasets."""
        insights_map = st.session_state.get("insights", {})
        all_ins = []
        for ins_list in insights_map.values():
            if isinstance(ins_list, list):
                all_ins.extend(ins_list)
        return all_ins

    @classmethod
    def set_phase5_analysis(cls, payload: Dict[str, Any]) -> None:
        """Store the complete latest Phase 5 analysis pipeline result."""
        st.session_state["phase5_analysis"] = payload

    @classmethod
    def get_phase5_analysis(cls) -> Optional[Dict[str, Any]]:
        """Retrieve the latest Phase 5 analysis pipeline result."""
        return st.session_state.get("phase5_analysis")

    @classmethod
    def set_phase5_config(cls, config: Dict[str, Any]) -> None:
        """Store Phase 5 analysis configuration settings."""
        st.session_state["phase5_config"] = config

    @classmethod
    def get_phase5_config(cls) -> Dict[str, Any]:
        """Retrieve Phase 5 analysis configuration settings."""
        return st.session_state.get("phase5_config", {})

    # =========================================================================
    # PREDICTION & FORECASTING ACCESSORS
    # =========================================================================

    @classmethod
    def set_prediction_result(cls, filename: str, result: Any) -> None:
        """Store PredictionResult for a specific dataset."""
        pred_map = st.session_state.get("prediction_results", {})
        pred_map[filename] = result
        st.session_state["prediction_results"] = pred_map

    @classmethod
    def get_prediction_result(cls, filename: Optional[str] = None) -> Optional[Any]:
        """Retrieve PredictionResult for the specified or active dataset."""
        target_name = filename or cls.get_active_dataset_name()
        if not target_name:
            return None
        return st.session_state.get("prediction_results", {}).get(target_name)

    @classmethod
    def get_all_prediction_results(cls) -> Dict[str, Any]:
        """Retrieve dictionary of all stored PredictionResults."""
        return st.session_state.get("prediction_results", {})

    @classmethod
    def get_prediction_results(cls, filename: Optional[str] = None) -> Any:
        """Retrieve stored prediction results conforming to the canonical schema v1.0.

        Returns:
            Canonical Prediction Result Schema dictionary if available, or {} if no prediction exists.
        """
        pred_map = st.session_state.get("prediction_results", {})
        if not pred_map:
            # Fallback to phase5_analysis or phase5_results if stored under alternate legacy keys
            pred_map = st.session_state.get("phase5_analysis", {}) or st.session_state.get("phase5_results", {})

        target_item = None
        if filename:
            if isinstance(pred_map, dict):
                target_item = pred_map.get(filename)
        else:
            active_name = cls.get_active_dataset_name()
            if isinstance(pred_map, dict):
                if active_name and active_name in pred_map:
                    target_item = pred_map[active_name]
                elif "schema_version" in pred_map or "task" in pred_map:
                    # Single canonical result stored directly
                    target_item = pred_map
                elif len(pred_map) > 0:
                    target_item = next(iter(pred_map.values()))
            elif hasattr(pred_map, "to_canonical_dict") or hasattr(pred_map, "status"):
                target_item = pred_map

        if target_item is None:
            return {}

        if hasattr(target_item, "to_canonical_dict"):
            return target_item.to_canonical_dict()
        elif isinstance(target_item, dict):
            return target_item
        return {}

    @classmethod
    def set_prediction_results(cls, results: Dict[str, Any]) -> None:
        """Store entire prediction results mapping."""
        st.session_state["prediction_results"] = results

    @classmethod
    def add_prediction_history(cls, entry: Dict[str, Any]) -> None:
        """Append lightweight audit entry to session prediction history."""
        history = st.session_state.get("prediction_history", [])
        history.append(entry)
        st.session_state["prediction_history"] = history

    @classmethod
    def get_prediction_history(cls) -> List[Dict[str, Any]]:
        """Retrieve full chronological prediction history list."""
        return st.session_state.get("prediction_history", [])

    @classmethod
    def set_prediction_config(cls, config: Dict[str, Any]) -> None:
        """Store user prediction configuration."""
        st.session_state["prediction_config"] = config

    @classmethod
    def get_prediction_config(cls) -> Dict[str, Any]:
        """Retrieve stored user prediction configuration."""
        return st.session_state.get("prediction_config", {})



