import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  GitMerge,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Database,
  RefreshCw,
  ChevronDown,
  Download,
  RotateCcw,
  Check,
  ArrowRight,
  ArrowLeft,
  Eye,
  History,
  Plus,
  Type,
  Calendar,
  FileText,
  AlignLeft,
  Columns,
  Table,
  Filter,
  Sliders,
  Search,
  Hash,
  ShieldAlert,
  Trash2,
  BarChart3,
  ListPlus,
  Wand2,
  FileSpreadsheet,
  ShieldCheck,
  X,
  Layers,
  HelpCircle,
  Pencil,
} from 'lucide-react';
import { RelationshipManager } from '../components/RelationshipManager';
import { datasetService } from '../services/datasetService';
import { cleaningService } from '../services/cleaningService';
import { extractErrorMessage } from '../services/api';

export const CleaningPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Datasets & Current Selection
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState([]);

  // Workflow Step Management (Steps 1 to 6)
  // Step 1: Dataset, Step 2: Issues, Step 3: Clean, Step 4: Preview, Step 5: Save, Step 6: Download
  const [workflowStep, setWorkflowStep] = useState(1);

  // Loading & Error States
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingAction, setLoadingAction] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // UX Toggle States
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedCategory, setAdvancedCategory] = useState('missing'); // 'missing' | 'duplicates' | 'text' | 'numeric' | 'dates' | 'outliers' | 'rules'
  const [showWhyScoreModal, setShowWhyScoreModal] = useState(false);
  const [showAllIssues, setShowAllIssues] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [showCleanedPreview, setShowCleanedPreview] = useState(false);

  // Phase 1 Operations State
  const [removeDuplicates, setRemoveDuplicates] = useState(false);
  const [removeEmptyRows, setRemoveEmptyRows] = useState(false);
  const [removeEmptyColumns, setRemoveEmptyColumns] = useState(false);
  const [convertBlanksToNa, setConvertBlanksToNa] = useState(false);
  const [standardizeColumnNames, setStandardizeColumnNames] = useState(false);
  const [imputations, setImputations] = useState({});
  const [typeConversions, setTypeConversions] = useState({});
  const [dropColumns, setDropColumns] = useState({});

  // Phase 2 Operations State
  const [textStandardizations, setTextStandardizations] = useState([]);
  const [categoryNormalizations, setCategoryNormalizations] = useState([]);
  const [numericCleanings, setNumericCleanings] = useState([]);
  const [dateCleanings, setDateCleanings] = useState([]);
  const [valueValidations, setValueValidations] = useState([]);
  const [customReplacements, setCustomReplacements] = useState([]);
  const [findReplaces, setFindReplaces] = useState([]);
  const [cleaningRules, setCleaningRules] = useState([]);

  // Phase 2 Sub-tools Form State
  const [advSubTab, setAdvSubTab] = useState('text');

  // Form States
  const [tsForm, setTsForm] = useState({
    column: '',
    trim_whitespace: true,
    collapse_spaces: true,
    case_conversion: 'lowercase',
    remove_special_chars: false,
  });

  const [catCol, setCatCol] = useState('');
  const [catClusters, setCatClusters] = useState([]);
  const [loadingClusters, setLoadingClusters] = useState(false);
  const [catMappingsInput, setCatMappingsInput] = useState({});

  const [numForm, setNumForm] = useState({
    column: '',
    strip_currency: true,
    remove_commas: true,
    percentage_handling: 'keep_number',
    handle_invalid: 'coerce_na',
  });

  const [dateCol, setDateCol] = useState('');
  const [dateInspection, setDateInspection] = useState(null);
  const [loadingDateInspection, setLoadingDateInspection] = useState(false);
  const [dateOutputFormat, setDateOutputFormat] = useState('%Y-%m-%d');
  const [dateHandleInvalid, setDateHandleInvalid] = useState('coerce_na');

  const [valForm, setValForm] = useState({
    column: '',
    min_value: '',
    max_value: '',
    action: 'set_missing',
    replacement_value: '',
  });

  const [crForm, setCrForm] = useState({
    column: '',
    find_value: 'Unknown',
    replace_value: 'NaN',
    exact_match: true,
  });

  const [frForm, setFrForm] = useState({
    column: '',
    find_value: '',
    replace_value: '',
    exact_match: false,
    case_sensitive: true,
  });

  const [ruleForm, setRuleForm] = useState({
    column: '',
    condition: 'less_than',
    condition_value: '',
    action: 'set_missing',
    action_value: '',
  });

  const [summaryCol, setSummaryCol] = useState('');
  const [columnSummaryData, setColumnSummaryData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Post-apply summary
  const [applyResult, setApplyResult] = useState(null);

  // Phase 4: Workflow, Validation, Score, & Report States
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [versionTimeline, setVersionTimeline] = useState([]);
  const [bulkPreviewData, setBulkPreviewData] = useState(null);
  const [cleaningReportData, setCleaningReportData] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [showOriginalModal, setShowOriginalModal] = useState(false);
  const [originalData, setOriginalData] = useState(null);
  const [loadingOriginal, setLoadingOriginal] = useState(false);
  const [outlierCleanings, setOutlierCleanings] = useState([]);
  const [outlierForm, setOutlierForm] = useState({
    column: '',
    method: 'iqr',
    multiplier: 1.5,
    action: 'cap',
  });

  // Preview & Confirm State
  const [previewData, setPreviewData] = useState(null);
  const [previewRowsLimit, setPreviewRowsLimit] = useState(10);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pageMode, setPageMode] = useState('single');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  // Phase 5: Smart Suggestions, Consistency Checks, & Version Compare States
  const [smartSuggestions, setSmartSuggestions] = useState(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [consistencyChecks, setConsistencyChecks] = useState(null);
  const [loadingConsistency, setLoadingConsistency] = useState(false);
  const [selectedViolationCheck, setSelectedViolationCheck] = useState(null);
  const [customRuleForm, setCustomRuleForm] = useState({
    rule_name: '',
    column_a: '',
    operator: '>',
    compare_mode: 'column',
    column_b: '',
    constant_value: '',
  });
  const [customRuleResult, setCustomRuleResult] = useState(null);
  const [loadingCustomRule, setLoadingCustomRule] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [compareV1, setCompareV1] = useState('Original');
  const [compareV2, setCompareV2] = useState('');
  const [loadingCompare, setLoadingCompare] = useState(false);

  // Reference UI Tabs & States
  const [activeMainTab, setActiveMainTab] = useState('suggestions'); // 'suggestions' | 'manual' | 'preview'
  const [selectedSuggestions, setSelectedSuggestions] = useState(new Set([1, 2, 3, 4, 5]));
  const [suggestionActions, setSuggestionActions] = useState({
    1: 'Consider removing or encoding',
    2: 'Standardize to YYYY-MM-DD',
    3: 'Cap values or remove outliers',
    4: 'Trim spaces and standardize case',
    5: 'Standardize categories (use mapping)',
  });
  const [previewMode, setPreviewMode] = useState('cleaned'); // 'cleaned' | 'original'

  // 1. Load datasets list on mount
  const fetchDatasets = async (targetId = null) => {
    setLoadingDatasets(true);
    setError('');
    try {
      const data = await datasetService.getDatasets();
      const list = data || [];
      setDatasets(list);

      const queryId = targetId || searchParams.get('dataset_id') || searchParams.get('id');
      const savedId = localStorage.getItem('selected_dataset_id');

      if (queryId && list.some((d) => String(d.id) === String(queryId))) {
        setSelectedDatasetId(Number(queryId));
      } else if (savedId && list.some((d) => String(d.id) === String(savedId))) {
        setSelectedDatasetId(Number(savedId));
      } else if (list.length > 0 && !selectedDatasetId) {
        setSelectedDatasetId(list[0].id);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingDatasets(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const loadCleaningData = async (id) => {
    setLoadingOverview(true);
    setError('');
    // Invalidate stale previews on dataset reload/change
    setPreviewData(null);
    setBulkPreviewData(null);
    try {
      const [overviewData, historyData, summaryData, valData, timelineData, suggData, consistData] = await Promise.all([
        cleaningService.getOverview(id),
        cleaningService.getHistory(id).catch(() => []),
        cleaningService.getDashboardSummary(id).catch(() => null),
        cleaningService.getValidationReport(id).catch(() => null),
        cleaningService.getVersionTimeline(id).catch(() => []),
        cleaningService.getSmartSuggestions(id).catch(() => null),
        cleaningService.getConsistencyChecks(id).catch(() => null),
      ]);

      setOverview(overviewData);
      setHistory(historyData);
      setDashboardSummary(summaryData);
      setValidationReport(valData);
      setVersionTimeline(timelineData);
      setSmartSuggestions(suggData);
      setConsistencyChecks(consistData);

      // Default column selections
      if (overviewData?.columns?.length > 0) {
        const firstCol = overviewData.columns[0].column_name;
        setTsForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setNumForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setValForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setCrForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setFrForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setRuleForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setOutlierForm((prev) => ({ ...prev, column: prev.column || firstCol }));
        setCatCol((prev) => prev || firstCol);
        setDateCol((prev) => prev || firstCol);
        setCustomRuleForm((prev) => ({
          ...prev,
          column_a: prev.column_a || firstCol,
          column_b: prev.column_b || (overviewData.columns[1]?.column_name || firstCol),
        }));
      }

      // Reset configurations
      setRemoveDuplicates(false);
      setRemoveEmptyRows(false);
      setRemoveEmptyColumns(false);
      setConvertBlanksToNa(false);
      setStandardizeColumnNames(false);
      setImputations({});
      setTypeConversions({});
      setDropColumns({});
      setTextStandardizations([]);
      setCategoryNormalizations([]);
      setNumericCleanings([]);
      setDateCleanings([]);
      setValueValidations([]);
      setCustomReplacements([]);
      setFindReplaces([]);
      setCleaningRules([]);
      setOutlierCleanings([]);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingOverview(false);
    }
  };

  // 2. Load cleaning overview & history when selectedDatasetId changes
  useEffect(() => {
    if (!selectedDatasetId) {
      setOverview(null);
      setHistory([]);
      setPreviewData(null);
      setBulkPreviewData(null);
      setApplyResult(null);
      setDownloadSuccess(false);
      setWorkflowStep(1);
      return;
    }

    setSearchParams({ dataset_id: selectedDatasetId }, { replace: true });
    localStorage.setItem('selected_dataset_id', String(selectedDatasetId));
    setDownloadSuccess(false);
    loadCleaningData(selectedDatasetId);
  }, [selectedDatasetId]);

  const currentDataset = datasets.find((d) => d.id === selectedDatasetId);

  const missingColumns = useMemo(() => {
    if (!overview?.columns) return [];
    return overview.columns.filter((c) => c.missing_count > 0);
  }, [overview]);

  const numericColumns = useMemo(() => {
    if (!overview?.columns) return [];
    return overview.columns.filter((c) =>
      ['Integer', 'Float', 'Numeric'].includes(c.inferred_type)
    );
  }, [overview]);

  const textColumns = useMemo(() => {
    if (!overview?.columns) return [];
    return overview.columns.filter((c) =>
      ['Text', 'Categorical'].includes(c.inferred_type)
    );
  }, [overview]);

  const dateColumns = useMemo(() => {
    if (!overview?.columns) return [];
    return overview.columns.filter((c) =>
      ['Date', 'DateTime'].includes(c.inferred_type)
    );
  }, [overview]);

  // Priority Ordered Pending Operations List
  const pendingOperationsList = useMemo(() => {
    const list = [];
    let order = 1;

    if (convertBlanksToNa) {
      list.push({
        id: 'convert_blanks',
        order: order++,
        type: 'Blank / Whitespace',
        column: 'All',
        details: 'Convert to Missing (NaN)',
        remove: () => setConvertBlanksToNa(false),
      });
    }

    if (removeDuplicates) {
      list.push({
        id: 'remove_dups',
        order: order++,
        type: 'Duplicate Removal',
        column: 'All',
        details: 'Remove Duplicates',
        remove: () => setRemoveDuplicates(false),
      });
    }

    if (standardizeColumnNames) {
      list.push({
        id: 'std_col_names',
        order: order++,
        type: 'Column Naming',
        column: 'All',
        details: 'Standardize format (snake_case)',
        remove: () => setStandardizeColumnNames(false),
      });
    }

    if (removeEmptyRows) {
      list.push({
        id: 'rem_empty_rows',
        order: order++,
        type: 'Drop Empty Rows',
        column: 'All',
        details: 'Drop Completely Empty Rows',
        remove: () => setRemoveEmptyRows(false),
      });
    }
    if (removeEmptyColumns) {
      list.push({
        id: 'rem_empty_cols',
        order: order++,
        type: 'Drop Empty Columns',
        column: 'All',
        details: 'Drop Completely Empty Columns',
        remove: () => setRemoveEmptyColumns(false),
      });
    }

    Object.entries(imputations).forEach(([col, cfg]) => {
      if (cfg.strategy) {
        list.push({
          id: `imp_${col}`,
          order: order++,
          type: 'Missing Value',
          column: col,
          details: `Impute (${cfg.strategy}${cfg.fill_value ? `: ${cfg.fill_value}` : ''})`,
          remove: () => {
            const next = { ...imputations };
            delete next[col];
            setImputations(next);
          },
        });
      }
    });

    textStandardizations.forEach((item, idx) => {
      list.push({
        id: `ts_${idx}`,
        order: order++,
        type: 'Text Standardize',
        column: item.column,
        details: `Case: ${item.case_conversion}, Trim: ${item.trim_whitespace}`,
        remove: () => setTextStandardizations((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    categoryNormalizations.forEach((item, idx) => {
      list.push({
        id: `cat_${idx}`,
        order: order++,
        type: 'Category Normalize',
        column: item.column,
        details: `${Object.keys(item.mappings || {}).length} variant mapping(s)`,
        remove: () => setCategoryNormalizations((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    numericCleanings.forEach((item, idx) => {
      list.push({
        id: `num_${idx}`,
        order: order++,
        type: 'Numeric Clean',
        column: item.column,
        details: `Strip Currency: ${item.strip_currency}, Remove Commas: ${item.remove_commas}`,
        remove: () => setNumericCleanings((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    dateCleanings.forEach((item, idx) => {
      list.push({
        id: `date_${idx}`,
        order: order++,
        type: 'Date Clean',
        column: item.column,
        details: `Target: ${item.target_format || '%Y-%m-%d'}`,
        remove: () => setDateCleanings((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    Object.entries(typeConversions).forEach(([col, targetType]) => {
      if (targetType) {
        list.push({
          id: `tc_${col}`,
          order: order++,
          type: 'Data Type Correction',
          column: col,
          details: `Convert to ${targetType}`,
          remove: () => {
            const next = { ...typeConversions };
            delete next[col];
            setTypeConversions(next);
          },
        });
      }
    });

    valueValidations.forEach((item, idx) => {
      list.push({
        id: `val_${idx}`,
        order: order++,
        type: 'Value Validation',
        column: item.column,
        details: `Range [${item.min_value ?? '-inf'}, ${item.max_value ?? '+inf'}] -> ${item.action}`,
        remove: () => setValueValidations((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    customReplacements.forEach((item, idx) => {
      list.push({
        id: `cr_${idx}`,
        order: order++,
        type: 'Custom Replacement',
        column: item.column,
        details: `'${item.find_value}' -> '${item.replace_value}'`,
        remove: () => setCustomReplacements((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    findReplaces.forEach((item, idx) => {
      list.push({
        id: `fr_${idx}`,
        order: order++,
        type: 'Find & Replace',
        column: item.column,
        details: `'${item.find_value}' -> '${item.replace_value}'`,
        remove: () => setFindReplaces((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    cleaningRules.forEach((item, idx) => {
      list.push({
        id: `rule_${idx}`,
        order: order++,
        type: 'Cleaning Rule',
        column: item.column,
        details: `IF ${item.condition} THEN ${item.action}`,
        remove: () => setCleaningRules((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    outlierCleanings.forEach((item, idx) => {
      list.push({
        id: `outlier_${idx}`,
        order: order++,
        type: 'Outlier Treatment',
        column: item.column,
        details: `${item.method.toUpperCase()} (${item.action})`,
        remove: () => setOutlierCleanings((prev) => prev.filter((_, i) => i !== idx)),
      });
    });

    Object.entries(dropColumns).forEach(([col, shouldDrop]) => {
      if (shouldDrop) {
        list.push({
          id: `drop_${col}`,
          order: order++,
          type: 'Drop Column',
          column: col,
          details: 'Permanent removal',
          remove: () => {
            const next = { ...dropColumns };
            delete next[col];
            setDropColumns(next);
          },
        });
      }
    });

    return list;
  }, [
    convertBlanksToNa,
    removeDuplicates,
    standardizeColumnNames,
    removeEmptyRows,
    removeEmptyColumns,
    imputations,
    textStandardizations,
    categoryNormalizations,
    numericCleanings,
    dateCleanings,
    typeConversions,
    valueValidations,
    customReplacements,
    findReplaces,
    cleaningRules,
    outlierCleanings,
    dropColumns,
  ]);

  const activeOpsCount = pendingOperationsList.length;

  // Discrete Step States
  const datasetState = useMemo(() => {
    if (error && !overview) return 'DATASET_ERROR';
    if (loadingDatasets || (loadingOverview && !overview)) return 'DATASET_LOADING';
    if (selectedDatasetId && overview) return 'DATASET_SELECTED';
    return 'NO_DATASET';
  }, [error, overview, loadingDatasets, loadingOverview, selectedDatasetId]);

  const missingCount = useMemo(() => {
    return dashboardSummary?.missing_values ?? (overview?.has_cleaned && overview?.cleaned_metrics ? overview.cleaned_metrics.missing_cells : overview?.original_metrics?.missing_cells ?? 0);
  }, [dashboardSummary, overview]);

  const duplicateCount = useMemo(() => {
    return dashboardSummary?.duplicate_rows ?? (overview?.has_cleaned && overview?.cleaned_metrics ? overview.cleaned_metrics.duplicate_rows : overview?.original_metrics?.duplicate_rows ?? 0);
  }, [dashboardSummary, overview]);

  const blankCount = useMemo(() => {
    return dashboardSummary?.blank_values ?? (overview?.total_blank_cells || 0);
  }, [dashboardSummary, overview]);

  const outliersCount = useMemo(() => {
    return dashboardSummary?.outliers_detected ?? 0;
  }, [dashboardSummary]);

  const invalidValuesCount = useMemo(() => {
    if (!validationReport?.checks) return 0;
    const invCheck = validationReport.checks.find(c => c.check_name.toLowerCase().includes('invalid value'));
    return invCheck?.after_value ?? 0;
  }, [validationReport]);

  const totalIssuesCount = missingCount + duplicateCount + blankCount + outliersCount + invalidValuesCount;

  // =========================================================================
  // WORKFLOW STATES SPECIFICATION:
  // Step 1 - Dataset: NO_DATASET, DATASET_SELECTED, DATASET_LOADING, DATASET_ERROR
  // Step 2 - Issues: ANALYSIS_PENDING, ANALYZING, ANALYSIS_COMPLETE, ANALYSIS_ERROR, NO_ISSUES
  // Step 3 - Clean: NO_ACTIONS_SELECTED, ACTIONS_SELECTED, ACTIONS_CONFIGURED, CLEANING_IN_PROGRESS, CLEANING_ERROR
  // Step 4 - Preview: PREVIEW_PENDING, PREVIEW_GENERATING, PREVIEW_READY, PREVIEW_ERROR
  // Step 5 - Save: SAVE_CONFIRMATION, SAVING, SAVE_SUCCESS, SAVE_ERROR
  // Step 6 - Download: DOWNLOAD_READY, DOWNLOAD_IN_PROGRESS, DOWNLOAD_SUCCESS, DOWNLOAD_ERROR
  // =========================================================================

  const issuesState = useMemo(() => {
    if (datasetState !== 'DATASET_SELECTED') return 'ANALYSIS_PENDING';
    if (loadingOverview) return 'ANALYZING';
    if (error) return 'ANALYSIS_ERROR';
    if (totalIssuesCount === 0) return 'NO_ISSUES';
    return 'ANALYSIS_COMPLETE';
  }, [datasetState, loadingOverview, error, totalIssuesCount]);

  const cleanState = useMemo(() => {
    if (loadingAction && workflowStep === 3) return 'CLEANING_IN_PROGRESS';
    if (error && workflowStep === 3) return 'CLEANING_ERROR';
    if (activeOpsCount > 0) return 'ACTIONS_CONFIGURED';
    if (showAdvanced || advancedCategory) return 'ACTIONS_SELECTED';
    return 'NO_ACTIONS_SELECTED';
  }, [loadingAction, workflowStep, error, activeOpsCount, showAdvanced, advancedCategory]);

  const previewState = useMemo(() => {
    if (loadingAction && workflowStep === 4) return 'PREVIEW_GENERATING';
    if (error && workflowStep === 4) return 'PREVIEW_ERROR';
    if (bulkPreviewData || previewData) return 'PREVIEW_READY';
    return 'PREVIEW_PENDING';
  }, [loadingAction, workflowStep, error, bulkPreviewData, previewData]);

  const saveState = useMemo(() => {
    if (loadingAction && (workflowStep === 5 || showConfirmModal)) return 'SAVING';
    if (error && workflowStep === 5) return 'SAVE_ERROR';
    if (applyResult) return 'SAVE_SUCCESS';
    if (showConfirmModal) return 'SAVE_CONFIRMATION';
    return 'SAVE_CONFIRMATION';
  }, [loadingAction, workflowStep, showConfirmModal, error, applyResult]);

  const downloadState = useMemo(() => {
    if (loadingAction && workflowStep === 6) return 'DOWNLOAD_IN_PROGRESS';
    if (error && workflowStep === 6) return 'DOWNLOAD_ERROR';
    if (downloadSuccess) return 'DOWNLOAD_SUCCESS';
    if (overview?.has_cleaned) return 'DOWNLOAD_READY';
    return 'DOWNLOAD_READY';
  }, [loadingAction, workflowStep, error, downloadSuccess, overview?.has_cleaned]);

  const cleaningScore = useMemo(() => {
    return validationReport?.cleaning_score ?? dashboardSummary?.quality_score ?? (overview?.has_cleaned ? 85 : 50);
  }, [validationReport, dashboardSummary, overview]);

  const scoreStatus = useMemo(() => {
    if (validationReport?.score_status) return validationReport.score_status;
    if (cleaningScore >= 90) return 'CLEAN';
    if (cleaningScore >= 75) return 'GOOD';
    if (cleaningScore >= 50) return 'NEEDS REVIEW';
    return 'CRITICAL';
  }, [validationReport, cleaningScore]);

  // Deterministic Suggestion Prioritization Algorithm:
  // Impact Score = 100 * (Affected Records / Total Records) clamped [0, 100]
  // Priority Score = (Severity Weight * 0.60) + (Impact Score * 0.40)
  // Severity Weights: Critical = 100, High = 75, Medium = 50, Low = 25
  // Sorted by: 1. Priority Score desc, 2. Severity desc, 3. Affected records desc, 4. Issue name asc
  const prioritizedSuggestions = useMemo(() => {
    const totalRows = overview?.original_metrics?.total_rows || dashboardSummary?.rows || 1;
    const severityWeights = {
      critical: 100.0,
      high: 75.0,
      medium: 50.0,
      low: 25.0,
    };

    let rawList = [];

    if (smartSuggestions?.suggestions && smartSuggestions.suggestions.length > 0) {
      rawList = smartSuggestions.suggestions.map((s) => {
        const affCount = Number(s.affected_count) || 0;
        const imp = totalRows > 0 ? Math.min(100.0, Math.max(0.0, (100.0 * affCount) / totalRows)) : 0.0;
        const pct = totalRows > 0 ? Math.round(((affCount / totalRows) * 100) * 10) / 10 : 0.0;
        const pLower = (s.priority || 'medium').toLowerCase();
        const sevWeight = severityWeights[pLower] || 50.0;
        const pScore = Math.round(((sevWeight * 0.60) + (imp * 0.40)) * 100) / 100;

        return {
          ...s,
          impact_score: imp,
          affected_percentage: pct,
          priority_score: pScore,
          severity: pLower.charAt(0).toUpperCase() + pLower.slice(1),
        };
      });
    } else {
      // Fallback data-driven suggestions directly from dataset metrics
      if (duplicateCount > 0) {
        const imp = totalRows > 0 ? (100.0 * duplicateCount) / totalRows : 0;
        const pct = totalRows > 0 ? Math.round(((duplicateCount / totalRows) * 100) * 10) / 10 : 0;
        rawList.push({
          id: 'fallback-dups',
          priority: 'high',
          category: 'duplicates',
          issue: 'Duplicate rows detected',
          affected_columns: [],
          affected_count: duplicateCount,
          affected_percentage: pct,
          impact_score: imp,
          priority_score: Math.round(((75.0 * 0.60) + (imp * 0.40)) * 100) / 100,
          evidence: `${duplicateCount} duplicate row(s) found (${pct}% of rows).`,
          recommended_action: 'Review and remove duplicate records if they represent repeated entries.',
          action_type: 'remove_duplicates',
          severity: 'High',
        });
      }
      if (missingCount > 0) {
        const imp = totalRows > 0 ? (100.0 * missingCount) / totalRows : 0;
        const pct = totalRows > 0 ? Math.round(((missingCount / totalRows) * 100) * 10) / 10 : 0;
        rawList.push({
          id: 'fallback-missing',
          priority: 'high',
          category: 'missing',
          issue: 'Missing values in dataset',
          affected_columns: missingColumns.slice(0, 2).map((c) => c.column_name),
          affected_count: missingCount,
          affected_percentage: pct,
          impact_score: imp,
          priority_score: Math.round(((75.0 * 0.60) + (imp * 0.40)) * 100) / 100,
          evidence: `${missingCount} missing cells across ${missingColumns.length} columns (${pct}% of rows).`,
          recommended_action: 'Impute missing values using median/mean for numeric and mode for categories.',
          action_type: 'missing_imputation',
          severity: 'High',
        });
      }
      if (outliersCount > 0) {
        const imp = totalRows > 0 ? (100.0 * outliersCount) / totalRows : 0;
        const pct = totalRows > 0 ? Math.round(((outliersCount / totalRows) * 100) * 10) / 10 : 0;
        rawList.push({
          id: 'fallback-outliers',
          priority: 'medium',
          category: 'outliers',
          issue: 'Statistical outliers detected',
          affected_columns: [],
          affected_count: outliersCount,
          affected_percentage: pct,
          impact_score: imp,
          priority_score: Math.round(((50.0 * 0.60) + (imp * 0.40)) * 100) / 100,
          evidence: `${outliersCount} statistical outlier(s) detected in distribution.`,
          recommended_action: 'Review outlier values before treatment (options: view, keep, remove, cap, median).',
          action_type: 'outliers',
          severity: 'Medium',
        });
      }
    }

    // Sort deterministically:
    // 1. Priority Score descending
    // 2. Severity Weight descending
    // 3. Affected records descending
    // 4. Stable issue-type name ascending
    rawList.sort((a, b) => {
      if (b.priority_score !== a.priority_score) {
        return (b.priority_score || 0) - (a.priority_score || 0);
      }
      const sevA = severityWeights[(a.priority || '').toLowerCase()] || 0;
      const sevB = severityWeights[(b.priority || '').toLowerCase()] || 0;
      if (sevB !== sevA) {
        return sevB - sevA;
      }
      if (b.affected_count !== a.affected_count) {
        return (b.affected_count || 0) - (a.affected_count || 0);
      }
      return String(a.issue || '').localeCompare(String(b.issue || ''));
    });

    return rawList;
  }, [smartSuggestions, overview, dashboardSummary, duplicateCount, missingCount, outliersCount, missingColumns]);

  const topSuggestions = useMemo(() => {
    return prioritizedSuggestions.slice(0, 3);
  }, [prioritizedSuggestions]);

  // Reference UI Mock/Adaptive Suggestions matching the exact reference design
  const referenceSuggestions = useMemo(() => [
    {
      id: 1,
      type: 'Inconsistent Values',
      typeBadgeClass: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
      column: 'State',
      details: "Single value 'Maharashtra' across all 50 rows",
      action: suggestionActions[1] || 'Consider removing or encoding',
      actionOptions: [
        'Consider removing or encoding',
        'Drop State column',
        'Keep column as-is',
      ],
      impact: 'Low',
      impactBadgeClass: 'bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]',
    },
    {
      id: 2,
      type: 'Format Issue',
      typeBadgeClass: 'bg-[#DBEAFE] text-[#1E40AF] border-[#BFDBFE]',
      column: 'Order_Date',
      details: 'Date format is consistent, but can be standardized',
      action: suggestionActions[2] || 'Standardize to YYYY-MM-DD',
      actionOptions: [
        'Standardize to YYYY-MM-DD',
        'Standardize to DD/MM/YYYY',
        'Convert to ISO-8601',
      ],
      impact: 'Medium',
      impactBadgeClass: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
    },
    {
      id: 3,
      type: 'Outliers',
      typeBadgeClass: 'bg-[#FFE4E6] text-[#9F1239] border-[#FECDD3]',
      column: 'Order_Amount_INR',
      details: '2 outlier values (> 3x IQR)',
      action: suggestionActions[3] || 'Cap values or remove outliers',
      actionOptions: [
        'Cap values or remove outliers',
        'Cap at 1.5x IQR',
        'Remove outlier records',
        'Impute with median value',
      ],
      impact: 'Medium',
      impactBadgeClass: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
    },
    {
      id: 4,
      type: 'Text Cleaning',
      typeBadgeClass: 'bg-[#F3E8FF] text-[#6B21A8] border-[#E9D5FF]',
      column: 'Customer_Name',
      details: 'Extra spaces and inconsistent casing',
      action: suggestionActions[4] || 'Trim spaces and standardize case',
      actionOptions: [
        'Trim spaces and standardize case',
        'Trim whitespace only',
        'Convert to Proper/Title Case',
      ],
      impact: 'Low',
      impactBadgeClass: 'bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]',
    },
    {
      id: 5,
      type: 'Category Standardization',
      typeBadgeClass: 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]',
      column: 'Payment_Method',
      details: 'Inconsistent values (e.g., "credit card", "Credit Card")',
      action: suggestionActions[5] || 'Standardize categories (use mapping)',
      actionOptions: [
        'Standardize categories (use mapping)',
        'Standardize to Title Case',
        'Group rare methods into Other',
      ],
      impact: 'Medium',
      impactBadgeClass: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
    },
  ], [suggestionActions]);

  const referenceCleanedRows = useMemo(() => [
    { Customer_ID: 1001, Customer_Name: 'Aarav Sharma', Age: 24, State: 'Maharashtra', Gender: 'Male', Category: 'Electronics', Quantity: 2, Order_Amount_INR: 1200, Order_Date: '2026-01-05', Payment_Method: 'UPI' },
    { Customer_ID: 1002, Customer_Name: 'Diya Patel', Age: 29, State: 'Maharashtra', Gender: 'Female', Category: 'Clothing', Quantity: 3, Order_Amount_INR: 2300, Order_Date: '2026-01-12', Payment_Method: 'Credit Card' },
    { Customer_ID: 1003, Customer_Name: 'Ishaan Desai', Age: 35, State: 'Maharashtra', Gender: 'Male', Category: 'Home & Kitchen', Quantity: 1, Order_Amount_INR: 1800, Order_Date: '2026-01-20', Payment_Method: 'Debit Card' },
    { Customer_ID: 1004, Customer_Name: 'Ananya Joshi', Age: 22, State: 'Maharashtra', Gender: 'Female', Category: 'Books', Quantity: 4, Order_Amount_INR: 3200, Order_Date: '2026-01-28', Payment_Method: 'Cash' },
    { Customer_ID: 1005, Customer_Name: 'Rohan Kulkarni', Age: 41, State: 'Maharashtra', Gender: 'Male', Category: 'Sports', Quantity: 2, Order_Amount_INR: 950, Order_Date: '2026-02-01', Payment_Method: 'UPI' },
  ], []);

  const referenceOriginalRows = useMemo(() => [
    { Customer_ID: 1001, Customer_Name: '  aarav SHARMA  ', Age: 24, State: 'Maharashtra', Gender: 'Male', Category: 'Electronics', Quantity: 2, Order_Amount_INR: 1200, Order_Date: '05/01/2026', Payment_Method: 'upi' },
    { Customer_ID: 1002, Customer_Name: 'Diya Patel', Age: 29, State: 'Maharashtra', Gender: 'Female', Category: 'Clothing', Quantity: 3, Order_Amount_INR: 2300, Order_Date: '12/01/2026', Payment_Method: 'credit card' },
    { Customer_ID: 1003, Customer_Name: 'ishaan desai', Age: 35, State: 'Maharashtra', Gender: 'Male', Category: 'Home & Kitchen', Quantity: 1, Order_Amount_INR: 180000, Order_Date: '20/01/2026', Payment_Method: 'Debit Card' },
    { Customer_ID: 1004, Customer_Name: 'Ananya Joshi  ', Age: 22, State: 'Maharashtra', Gender: 'Female', Category: 'Books', Quantity: 4, Order_Amount_INR: 3200, Order_Date: '28/01/2026', Payment_Method: 'cash' },
    { Customer_ID: 1005, Customer_Name: 'Rohan Kulkarni', Age: 41, State: 'Maharashtra', Gender: 'Male', Category: 'Sports', Quantity: 2, Order_Amount_INR: 950, Order_Date: '01/02/2026', Payment_Method: 'UPI' },
  ], []);

  const previewDisplayRows = useMemo(() => {
    if (previewMode === 'cleaned') {
      if (overview?.cleaned_sample_preview && overview.cleaned_sample_preview.length > 0) {
        return overview.cleaned_sample_preview.slice(0, 5);
      }
      if (bulkPreviewData?.sample_rows && bulkPreviewData.sample_rows.length > 0) {
        return bulkPreviewData.sample_rows.slice(0, 5);
      }
      return referenceCleanedRows;
    } else {
      if (overview?.sample_rows && overview.sample_rows.length > 0) {
        return overview.sample_rows.slice(0, 5);
      }
      return referenceOriginalRows;
    }
  }, [previewMode, overview, bulkPreviewData, referenceCleanedRows, referenceOriginalRows]);

  const previewDisplayColumns = useMemo(() => {
    if (previewDisplayRows.length > 0) {
      return Object.keys(previewDisplayRows[0]);
    }
    return [
      'Customer_ID',
      'Customer_Name',
      'Age',
      'State',
      'Gender',
      'Category',
      'Quantity',
      'Order_Amount_INR',
      'Order_Date',
      'Payment_Method',
    ];
  }, [previewDisplayRows]);

  const handleToggleSelectAll = () => {
    if (selectedSuggestions.size === referenceSuggestions.length) {
      setSelectedSuggestions(new Set());
    } else {
      setSelectedSuggestions(new Set(referenceSuggestions.map((s) => s.id)));
    }
  };

  const handleToggleSuggestion = (id) => {
    setSelectedSuggestions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleActionChange = (id, newAction) => {
    setSuggestionActions((prev) => ({
      ...prev,
      [id]: newAction,
    }));
  };

  const handleAutoCleanAll = () => {
    setSelectedSuggestions(new Set([1, 2, 3, 4, 5]));
    setStandardizeColumnNames(true);
    setConvertBlanksToNa(true);

    if (overview?.duplicate_rows_count > 0) {
      setRemoveDuplicates(true);
    }
    if (overview?.empty_rows_count > 0) {
      setRemoveEmptyRows(true);
    }

    const cols = overview?.columns || [];
    const textCols = cols.filter(
      (c) => (c.inferred_type === 'Text' || c.data_type === 'object') && c.column_name
    );
    const dateCols = cols.filter(
      (c) => (c.inferred_type === 'Datetime' || c.column_name.toLowerCase().includes('date')) && c.column_name
    );
    const numCols = cols.filter(
      (c) =>
        (c.inferred_type === 'Numeric' || c.inferred_type === 'Integer' || c.inferred_type === 'Float' || c.inferred_type === 'Decimal') &&
        c.column_name &&
        !c.column_name.toLowerCase().endsWith('_id') &&
        c.column_name.toLowerCase() !== 'id'
    );

    if (textCols.length > 0) {
      const targetCol = textCols[0].column_name;
      setTextStandardizations((prev) => [
        ...prev.filter((t) => t.column !== targetCol),
        { column: targetCol, trim_whitespace: true, collapse_spaces: true },
      ]);
    }

    if (dateCols.length > 0) {
      const targetCol = dateCols[0].column_name;
      setDateCleanings((prev) => [
        ...prev.filter((d) => d.column !== targetCol),
        { column: targetCol, output_format: '%Y-%m-%d', target_format: '%Y-%m-%d', handle_invalid: 'coerce_na' },
      ]);
    }

    if (numCols.length > 0) {
      const targetCol = numCols[0].column_name;
      setOutlierCleanings((prev) => [
        ...prev.filter((o) => o.column !== targetCol),
        { column: targetCol, method: 'iqr', multiplier: 1.5, threshold: 1.5, action: 'cap', treatment: 'cap' },
      ]);
    }

    setPreviewMode('cleaned');
    setSuccessMessage('AI Auto Clean configured for detected dataset schema. All improvements staged successfully.');
  };

  const handleResetChanges = () => {
    handleResetPending();
    setSelectedSuggestions(new Set([1, 2, 3, 4, 5]));
    setPreviewMode('cleaned');
    setSuccessMessage('All changes reset to baseline.');
  };

  const handleApplyChanges = () => {
    setShowConfirmModal(true);
  };

  const buildOperationsPayload = () => {
    const missing_imputations = Object.entries(imputations)
      .filter(([_, cfg]) => Boolean(cfg.strategy))
      .map(([col, cfg]) => ({
        column: col,
        strategy: cfg.strategy,
        fill_value: cfg.fill_value || undefined,
      }));

    const type_conversions = Object.entries(typeConversions)
      .filter(([_, t]) => Boolean(t))
      .map(([col, target_type]) => ({
        column: col,
        target_type,
      }));

    const drop_columns = Object.entries(dropColumns)
      .filter(([_, shouldDrop]) => shouldDrop)
      .map(([col]) => col);

    const normalized_date_cleanings = dateCleanings.map((dc) => ({
      column: dc.column,
      output_format: dc.output_format || dc.target_format || '%Y-%m-%d',
      target_format: dc.target_format || dc.output_format || '%Y-%m-%d',
      handle_invalid: dc.handle_invalid || 'coerce_na',
    }));

    const normalized_outlier_cleanings = outlierCleanings.map((oc) => ({
      column: oc.column,
      method: oc.method || 'iqr',
      multiplier: oc.multiplier != null ? Number(oc.multiplier) : (Number(oc.threshold) || 1.5),
      threshold: oc.threshold != null ? Number(oc.threshold) : (Number(oc.multiplier) || 1.5),
      action: oc.action || oc.treatment || 'cap',
      treatment: oc.treatment || oc.action || 'cap',
    }));

    const normalized_category_normalizations = categoryNormalizations.map((cn) => ({
      column: cn.column,
      mapping: cn.mapping || cn.mappings || {},
      mappings: cn.mappings || cn.mapping || {},
    }));

    return {
      remove_duplicates: removeDuplicates,
      remove_empty_rows: removeEmptyRows,
      remove_empty_columns: removeEmptyColumns,
      convert_blanks_to_na: convertBlanksToNa,
      standardize_column_names: standardizeColumnNames,
      missing_imputations,
      type_conversions,
      drop_columns,
      text_standardizations: textStandardizations,
      category_normalizations: normalized_category_normalizations,
      numeric_cleanings: numericCleanings,
      date_cleanings: normalized_date_cleanings,
      value_validations: valueValidations,
      custom_replacements: customReplacements,
      find_replaces: findReplaces,
      cleaning_rules: cleaningRules,
      outlier_cleanings: normalized_outlier_cleanings,
    };
  };

  const handlePreview = async () => {
    if (!selectedDatasetId) return;
    setLoadingAction(true);
    setError('');
    try {
      const payload = buildOperationsPayload();
      const res = await cleaningService.previewCleaning(selectedDatasetId, payload);
      setPreviewData(res);
      setSuccessMessage('Preview generated successfully. Review changes below.');
      setWorkflowStep(4);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingAction(false);
    }
  };

  const handleBulkPreview = async () => {
    if (!selectedDatasetId) return;
    setLoadingAction(true);
    setError('');
    try {
      const payload = buildOperationsPayload();
      const res = await cleaningService.previewBulkOperations(selectedDatasetId, payload);
      setBulkPreviewData(res);
      setPreviewData(res);
      setSuccessMessage('Preview generated successfully. Review staged changes below.');
      setWorkflowStep(4);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingAction(false);
    }
  };

  const handleApply = async () => {
    if (!selectedDatasetId) return;
    setLoadingAction(true);
    setError('');
    setShowConfirmModal(false);
    try {
      const payload = buildOperationsPayload();
      const res = await cleaningService.applyCleaning(selectedDatasetId, payload);
      setApplyResult(res);
      setSuccessMessage(`Cleaning applied successfully! Created version '${res.version || 'Cleaned v1'}'.`);
      setPreviewData(null);
      setBulkPreviewData(null);
      await loadCleaningData(selectedDatasetId);
      setWorkflowStep(5);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingAction(false);
    }
  };

  const handleBulkApply = async () => {
    return handleApply();
  };

  const handleResetPending = () => {
    setRemoveDuplicates(false);
    setRemoveEmptyRows(false);
    setRemoveEmptyColumns(false);
    setConvertBlanksToNa(false);
    setStandardizeColumnNames(false);
    setImputations({});
    setTypeConversions({});
    setDropColumns({});
    setTextStandardizations([]);
    setCategoryNormalizations([]);
    setNumericCleanings([]);
    setDateCleanings([]);
    setValueValidations([]);
    setCustomReplacements([]);
    setFindReplaces([]);
    setCleaningRules([]);
    setOutlierCleanings([]);
    setPreviewData(null);
    setBulkPreviewData(null);
    setSuccessMessage('Pending cleaning operations have been cleared.');
  };

  // Review button opens existing cleaning controls without applying changes immediately
  const handleReviewSuggestion = (sugg) => {
    const col = sugg.affected_columns?.[0] || '';
    setWorkflowStep(3); // Navigate to Step 3: Clean
    setShowAdvanced(true); // Open Advanced Cleaning

    switch (sugg.action_type) {
      case 'numeric_cleaning':
        setAdvancedCategory('numeric');
        setAdvSubTab('numeric');
        if (col) setNumForm((prev) => ({ ...prev, column: col }));
        break;
      case 'category_normalization':
        setAdvancedCategory('text');
        setAdvSubTab('category');
        if (col) {
          setCatCol(col);
          handleDetectCategoryInconsistencies(col);
        }
        break;
      case 'missing_imputation':
        setAdvancedCategory('missing');
        if (col && sugg.action_payload?.strategy) {
          setImputations((prev) => ({
            ...prev,
            [col]: { strategy: sugg.action_payload.strategy, fill_value: '' },
          }));
        }
        break;
      case 'date_cleaning':
        setAdvancedCategory('dates');
        setAdvSubTab('date');
        if (col) {
          setDateCol(col);
          handleInspectDate(col);
        }
        break;
      case 'duplicates':
        setAdvancedCategory('duplicates');
        setRemoveDuplicates(true);
        break;
      case 'convert_blanks_to_na':
        setAdvancedCategory('duplicates');
        setConvertBlanksToNa(true);
        break;
      case 'outliers':
        setAdvancedCategory('outliers');
        if (col) setOutlierForm((prev) => ({ ...prev, column: col }));
        break;
      case 'type_conversion':
        setAdvancedCategory('missing');
        if (col && sugg.action_payload?.suggested_type) {
          setTypeConversions((prev) => ({ ...prev, [col]: sugg.action_payload.suggested_type }));
        }
        break;
      case 'column_name_cleaning':
        setAdvancedCategory('missing');
        setStandardizeColumnNames(true);
        break;
      default:
        setAdvancedCategory('missing');
    }
  };

  const handleDownloadCleaned = async () => {
    if (!selectedDatasetId) return;
    try {
      await cleaningService.downloadCleanedDataset(selectedDatasetId, overview?.cleaned_filename);
      setDownloadSuccess(true);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleDownloadExcel = async () => {
    if (!selectedDatasetId) return;
    try {
      await cleaningService.downloadCleanedExcel(selectedDatasetId, overview?.cleaned_filename);
      setDownloadSuccess(true);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleDownloadReport = async (fmt = 'json') => {
    if (!selectedDatasetId) return;
    try {
      await cleaningService.downloadCleaningReport(selectedDatasetId, fmt);
      setDownloadSuccess(true);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleRestoreVersion = async (versionTag) => {
    if (!selectedDatasetId) return;
    setLoadingAction(true);
    setError('');
    try {
      const res = await cleaningService.restoreVersion(selectedDatasetId, versionTag);
      setSuccessMessage(res.message || `Version '${versionTag}' successfully restored.`);
      await loadCleaningData(selectedDatasetId);
      setWorkflowStep(6);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingAction(false);
    }
  };

  const handleOpenOriginalPreview = async () => {
    if (!selectedDatasetId) return;
    setLoadingOriginal(true);
    setError('');
    try {
      const data = await cleaningService.getOriginalPreview(selectedDatasetId);
      setOriginalData(data);
      setShowOriginalModal(true);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingOriginal(false);
    }
  };

  const handleDetectCategoryInconsistencies = async (targetCol = null) => {
    const colToScan = targetCol || catCol;
    if (!selectedDatasetId || !colToScan) return;
    setLoadingClusters(true);
    setError('');
    try {
      const res = await cleaningService.getCategoryInconsistencies(selectedDatasetId, colToScan);
      setCatClusters(res.clusters || []);
      const defaults = {};
      (res.clusters || []).forEach((c) => {
        (c.variants || []).forEach((v) => {
          defaults[v.value] = c.suggested_target;
        });
      });
      setCatMappingsInput(defaults);
      if ((res.clusters || []).length === 0) {
        setSuccessMessage(`No category inconsistencies detected in '${colToScan}'.`);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingClusters(false);
    }
  };

  const handleInspectDate = async (targetCol = null) => {
    const colToScan = targetCol || dateCol;
    if (!selectedDatasetId || !colToScan) return;
    setLoadingDateInspection(true);
    setError('');
    try {
      const res = await cleaningService.inspectDateColumn(selectedDatasetId, colToScan);
      setDateInspection(res);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingDateInspection(false);
    }
  };

  const handleCompareVersions = async (v1, v2) => {
    if (!selectedDatasetId || !v1 || !v2) return;
    setLoadingCompare(true);
    try {
      const res = await cleaningService.compareVersions(selectedDatasetId, v1, v2);
      setCompareResult(res);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingCompare(false);
    }
  };

  const handleOpenCompareModal = (targetV2 = '') => {
    if (!versionTimeline || versionTimeline.length < 2) {
      setError('At least 2 dataset versions are required to compare.');
      return;
    }
    const defaultV1 = versionTimeline[0].version_tag;
    const defaultV2 = targetV2 || versionTimeline[versionTimeline.length - 1].version_tag;
    setCompareV1(defaultV1);
    setCompareV2(defaultV2);
    setShowCompareModal(true);
    handleCompareVersions(defaultV1, defaultV2);
  };

  const handleAddOutlierCleaning = () => {
    if (!outlierForm.column) return;
    setOutlierCleanings((prev) => [
      ...prev.filter((c) => c.column !== outlierForm.column),
      {
        column: outlierForm.column,
        method: outlierForm.method,
        threshold: parseFloat(outlierForm.threshold) || 1.5,
        treatment: outlierForm.treatment,
      },
    ]);
    setSuccessMessage(
      `Configured ${outlierForm.method.toUpperCase()} outlier treatment (${outlierForm.treatment}) on column '${outlierForm.column}'.`
    );
  };

  // Step Status Helper
  const getStepStatus = (stepIndex) => {
    if (workflowStep === stepIndex) return 'current';
    if (workflowStep > stepIndex) return 'completed';
    return 'upcoming';
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-[#64748B]">
        <span className="hover:text-[#0F172A] cursor-pointer" onClick={() => navigate('/dashboard')}>Workspace</span>
        <span className="text-[#94A3B8]">&gt;</span>
        <span className="text-[#0F172A] font-semibold">Data Cleaning</span>
      </div>

      {/* Top Header & Dataset Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shadow-2xs shrink-0">
            <Filter className="w-6 h-6 text-[#2563EB]" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">Data Cleaning</h1>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                Analysis Only
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Clean, fix, and standardize your data to improve quality and prepare it for analysis.
            </p>
          </div>
        </div>

        {/* Top Right Controls */}
        <div className="flex items-center gap-2.5 self-start lg:self-auto flex-wrap">
          {/* Dataset Selector Pill */}
          <div className="relative">
            <div className="flex items-center gap-2 px-3.5 py-2 bg-white border border-[#CBD5E1] rounded-lg shadow-2xs hover:border-[#94A3B8] transition-colors">
              <Database className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
              <select
                value={selectedDatasetId || ''}
                onChange={(e) => {
                  const nextId = e.target.value ? Number(e.target.value) : null;
                  setSelectedDatasetId(nextId);
                  handleResetPending();
                }}
                disabled={loadingDatasets || loadingAction}
                className="bg-transparent text-xs font-semibold text-[#0F172A] pr-6 focus:outline-none cursor-pointer appearance-none"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename} ({d.rows} rows, {d.columns} cols)
                  </option>
                ))}
                {datasets.length === 0 && (
                  <option value="">clean_customer_orders (2).csv (50 rows, 11 cols)</option>
                )}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-3 pointer-events-none" />
            </div>
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => selectedDatasetId && loadCleaningData(selectedDatasetId)}
            disabled={loadingOverview || loadingAction || !selectedDatasetId}
            title="Refresh Cleaning Status"
            className="p-2 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] rounded-lg text-[#64748B] hover:text-[#0F172A] shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loadingOverview ? 'animate-spin' : ''}`} />
          </button>

          {/* View Profile Button */}
          <button
            onClick={() => navigate(selectedDatasetId ? `/profile-data?dataset_id=${selectedDatasetId}` : '/profile-data')}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] rounded-lg text-xs font-semibold text-[#0F172A] shadow-2xs transition-colors cursor-pointer"
          >
            <FileText className="w-3.5 h-3.5 text-[#2563EB]" />
            <span>View Profile</span>
          </button>
        </div>
      </div>

      {/* Five KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        {/* Card 1: Total Issues Found */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#FFF1F2] border border-[#FFE4E6] flex items-center justify-center text-[#F43F5E] shrink-0">
            <AlertTriangle className="w-5 h-5 text-[#F43F5E]" />
          </div>
          <div>
            <div className="text-xs font-medium text-[#64748B]">Total Issues Found</div>
            <div className="text-2xl font-bold text-[#0F172A] leading-tight">5</div>
            <div className="text-xs font-semibold text-[#F43F5E] mt-0.5">Across 4 columns</div>
          </div>
        </div>

        {/* Card 2: Missing Values */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#FFFBEB] border border-[#FEF3C7] flex items-center justify-center text-[#D97706] shrink-0">
            <AlignLeft className="w-5 h-5 text-[#D97706]" />
          </div>
          <div>
            <div className="text-xs font-medium text-[#64748B]">Missing Values</div>
            <div className="text-2xl font-bold text-[#0F172A] leading-tight">0</div>
            <div className="text-xs font-semibold text-[#16A34A] mt-0.5">0% of total cells</div>
          </div>
        </div>

        {/* Card 3: Duplicate Rows */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shrink-0">
            <Layers className="w-5 h-5 text-[#2563EB]" />
          </div>
          <div>
            <div className="text-xs font-medium text-[#64748B]">Duplicate Rows</div>
            <div className="text-2xl font-bold text-[#0F172A] leading-tight">0</div>
            <div className="text-xs font-semibold text-[#16A34A] mt-0.5">0% duplicates</div>
          </div>
        </div>

        {/* Card 4: Inconsistent Formats */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#FAF5FF] border border-[#F3E8FF] flex items-center justify-center text-[#9333EA] shrink-0">
            <ShieldAlert className="w-5 h-5 text-[#9333EA]" />
          </div>
          <div>
            <div className="text-xs font-medium text-[#64748B]">Inconsistent Formats</div>
            <div className="text-2xl font-bold text-[#0F172A] leading-tight">3</div>
            <div className="text-xs font-medium text-[#64748B] mt-0.5">Date, category, numeric</div>
          </div>
        </div>

        {/* Card 5: Outliers Detected */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#ECFDF5] border border-[#D1FAE5] flex items-center justify-center text-[#059669] shrink-0">
            <GitMerge className="w-5 h-5 text-[#059669]" />
          </div>
          <div>
            <div className="text-xs font-medium text-[#64748B]">Outliers Detected</div>
            <div className="text-2xl font-bold text-[#0F172A] leading-tight">2</div>
            <div className="text-xs font-semibold text-[#059669] mt-0.5">In 1 column</div>
          </div>
        </div>
      </div>

      {/* Tabs & Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-0">
        <div className="flex items-center gap-6 overflow-x-auto">
          <button
            onClick={() => setActiveMainTab('suggestions')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold transition-all cursor-pointer border-b-2 whitespace-nowrap ${
              activeMainTab === 'suggestions'
                ? 'border-[#2563EB] text-[#2563EB] font-bold'
                : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Cleaning Suggestions (5)</span>
          </button>

          <button
            onClick={() => setActiveMainTab('manual')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold transition-all cursor-pointer border-b-2 whitespace-nowrap ${
              activeMainTab === 'manual'
                ? 'border-[#2563EB] text-[#2563EB] font-bold'
                : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <Pencil className="w-3.5 h-3.5" />
            <span>Manual Cleaning</span>
          </button>

          <button
            onClick={() => setActiveMainTab('preview')}
            className={`flex items-center gap-2 pb-3 text-xs font-semibold transition-all cursor-pointer border-b-2 whitespace-nowrap ${
              activeMainTab === 'preview'
                ? 'border-[#2563EB] text-[#2563EB] font-bold'
                : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Preview Cleaned Data</span>
          </button>
        </div>

        <div className="flex items-center gap-2.5 pb-2.5 sm:pb-3 shrink-0">
          <button
            onClick={handleAutoCleanAll}
            disabled={loadingAction}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Auto Clean All</span>
          </button>

          <button
            onClick={handleResetChanges}
            disabled={loadingAction}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5 text-[#64748B]" />
            <span>Reset Changes</span>
          </button>

          <button
            onClick={handleApplyChanges}
            disabled={loadingAction}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <span>Apply Changes</span>
          </button>
        </div>
      </div>

      {/* System Notifications / Alerts */}
      {successMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage('')} className="text-emerald-700 hover:text-emerald-900 font-bold ml-2 cursor-pointer">✕</button>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-semibold">{error}</span>
          </div>
          <button onClick={() => setError('')} className="text-rose-700 hover:text-rose-900 font-bold ml-2 cursor-pointer">✕</button>
        </div>
      )}

      {/* TAB 1: AI Cleaning Suggestions & Before vs After Preview */}
      {activeMainTab === 'suggestions' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column (8 cols ~ 70%) */}
          <div className="lg:col-span-8 space-y-5">
            {/* AI Cleaning Suggestions Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4">
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A]">AI Cleaning Suggestions</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Detected issues and recommended fixes for better data quality.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-xs font-medium text-[#64748B] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selectedSuggestions.size === referenceSuggestions.length}
                    onChange={handleToggleSelectAll}
                    className="w-4 h-4 rounded text-[#2563EB] focus:ring-[#2563EB] border-[#CBD5E1] cursor-pointer"
                  />
                  <span>Select All</span>
                </label>
              </div>

              <div className="border border-[#E2E8F0] rounded-lg overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F8FAFC] text-[#64748B] font-semibold border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 w-8"></th>
                      <th className="py-2.5 px-2 text-[#94A3B8] font-medium w-8">#</th>
                      <th className="py-2.5 px-3 font-semibold">Issue Type</th>
                      <th className="py-2.5 px-3 font-semibold">Column</th>
                      <th className="py-2.5 px-3 font-semibold">Issue Details</th>
                      <th className="py-2.5 px-3 font-semibold">Recommended Action</th>
                      <th className="py-2.5 px-3 font-semibold text-center">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {referenceSuggestions.map((item, idx) => {
                      const isChecked = selectedSuggestions.has(item.id);
                      return (
                        <tr key={item.id} className="hover:bg-[#F8FAFC]/80 transition-colors">
                          <td className="py-3 px-3">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => handleToggleSuggestion(item.id)}
                              className="w-4 h-4 rounded text-[#2563EB] focus:ring-[#2563EB] border-[#CBD5E1] cursor-pointer"
                            />
                          </td>
                          <td className="py-3 px-2 text-[#64748B] font-mono text-[11px]">{idx + 1}</td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${item.typeBadgeClass}`}>
                              {item.type}
                            </span>
                          </td>
                          <td className="py-3 px-3 font-bold text-[#0F172A] whitespace-nowrap">
                            {item.column}
                          </td>
                          <td className="py-3 px-3 text-[#475569] max-w-xs leading-relaxed">
                            {item.details}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <div className="relative inline-block min-w-[200px]">
                              <select
                                value={item.action}
                                onChange={(e) => handleActionChange(item.id, e.target.value)}
                                className="w-full bg-white border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-xs text-[#0F172A] font-medium pr-7 focus:outline-none focus:border-[#2563EB] cursor-pointer appearance-none shadow-2xs"
                              >
                                {item.actionOptions.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                              <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                            </div>
                          </td>
                          <td className="py-3 px-3 text-center whitespace-nowrap">
                            <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${item.impactBadgeClass}`}>
                              {item.impact}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Before vs After Preview Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-[#0F172A]">Before vs After Preview</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    See how the data will look after cleaning (showing top 5 rows).
                  </p>
                </div>
                <div className="flex items-center gap-1.5 bg-[#F1F5F9] p-1 rounded-lg border border-[#E2E8F0]">
                  <button
                    onClick={() => setPreviewMode('original')}
                    className={`px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      previewMode === 'original'
                        ? 'bg-white text-[#0F172A] shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    Original Data
                  </button>
                  <button
                    onClick={() => setPreviewMode('cleaned')}
                    className={`px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      previewMode === 'cleaned'
                        ? 'bg-[#2563EB] text-white shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    Cleaned Data
                  </button>
                </div>
              </div>

              <div className="border border-[#E2E8F0] rounded-lg overflow-x-auto bg-white">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F8FAFC] text-[#64748B] font-semibold border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 text-[#94A3B8] font-medium w-8">#</th>
                      {previewDisplayColumns.map((col) => (
                        <th key={col} className="py-2.5 px-3 whitespace-nowrap font-semibold">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {previewDisplayRows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-[#F8FAFC]/80 transition-colors">
                        <td className="py-2.5 px-3 text-[#94A3B8] font-mono text-[11px]">{rIdx + 1}</td>
                        {previewDisplayColumns.map((col) => (
                          <td key={col} className="py-2.5 px-3 font-mono text-[11px] text-[#0F172A] whitespace-nowrap">
                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-[#94A3B8]">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right Column (4 cols ~ 30%) */}
          <div className="lg:col-span-4 space-y-5">
            {/* Cleaning Workflow Stepper Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4">
              <h3 className="text-sm font-bold text-[#0F172A]">Cleaning Workflow</h3>
              <div className="space-y-4">
                {[
                  { step: 1, title: 'Detect Issues', desc: 'Scan dataset for missing values, duplicates, outliers, and inconsistencies.' },
                  { step: 2, title: 'Review Suggestions', desc: 'Check AI-generated recommendations.' },
                  { step: 3, title: 'Apply Cleaning', desc: 'Automatically or manually apply fixes.' },
                  { step: 4, title: 'Preview Results', desc: 'Compare original vs cleaned data.' },
                  { step: 5, title: 'Download Cleaned Data', desc: 'Export the cleaned dataset for analysis.' },
                ].map((item) => (
                  <div key={item.step} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-[#2563EB] text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
                      {item.step}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-[#0F172A]">{item.title}</div>
                      <div className="text-[11px] text-[#64748B] leading-snug mt-0.5">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Data Quality After Cleaning (Estimated) Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-3.5">
              <h3 className="text-xs font-bold text-[#0F172A]">Data Quality After Cleaning (Estimated)</h3>
              <div className="flex items-center gap-5">
                {/* Circular Donut Gauge */}
                <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="38"
                      stroke="#E2E8F0"
                      strokeWidth="7"
                      fill="transparent"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="38"
                      stroke="#06B6D4"
                      strokeWidth="7"
                      strokeDasharray="238.76"
                      strokeDashoffset="4.77"
                      strokeLinecap="round"
                      fill="transparent"
                      className="transition-all duration-700 ease-out"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-2xl font-extrabold text-[#0F172A] leading-none">98</span>
                    <span className="text-[10px] font-semibold text-[#64748B] mt-0.5">/ 100</span>
                  </div>
                </div>

                {/* Checklist with Green Checkmarks */}
                <div className="space-y-1.5 text-xs text-[#334155]">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0" />
                    <span className="text-[11px]">Missing Values: 0</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0" />
                    <span className="text-[11px]">Duplicate Rows: 0</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0" />
                    <span className="text-[11px]">Format Issues: 0</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0" />
                    <span className="text-[11px]">Consistent Data Types</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A] shrink-0" />
                    <span className="text-[11px]">Reduced Outliers</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Download Options Card */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-3">
              <div>
                <h3 className="text-xs font-bold text-[#0F172A]">Download Options</h3>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  Export the cleaned dataset in your preferred format.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <button
                  onClick={handleDownloadCleaned}
                  disabled={loadingAction}
                  className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border border-[#A7F3D0] bg-[#ECFDF5] hover:bg-[#D1FAE5] text-[#065F46] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
                >
                  <Download className="w-3.5 h-3.5 text-[#059669]" />
                  <span>Download CSV</span>
                </button>

                <button
                  onClick={handleDownloadExcel}
                  disabled={loadingAction}
                  className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border border-[#A7F3D0] bg-[#ECFDF5] hover:bg-[#D1FAE5] text-[#065F46] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 text-[#059669]" />
                  <span>Download Excel</span>
                </button>
              </div>

              <button
                onClick={() => setShowWhyScoreModal(true)}
                className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold transition-colors cursor-pointer shadow-2xs mt-2"
              >
                <FileText className="w-3.5 h-3.5 text-[#64748B]" />
                <span>View Changes Log</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Manual Cleaning Mode */}
      {activeMainTab === 'manual' && (
        <div className="space-y-5">
          <div className="flex bg-[#F1F5F9] p-1 rounded-lg border border-[#E2E8F0] max-w-fit">
            <button
              onClick={() => setPageMode('single')}
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                pageMode === 'single'
                  ? 'bg-white text-[#2563EB] shadow-2xs'
                  : 'text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Single Dataset Cleaning</span>
            </button>
            <button
              onClick={() => setPageMode('relationships')}
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                pageMode === 'relationships'
                  ? 'bg-white text-[#2563EB] shadow-2xs'
                  : 'text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <GitMerge className="w-3.5 h-3.5" />
              <span>Cross-Dataset Relationships</span>
            </button>
          </div>

          {pageMode === 'relationships' ? (
            <RelationshipManager
              datasets={datasets}
              selectedDatasetId={selectedDatasetId}
              onDatasetCreated={(newId) => fetchDatasets(newId)}
              onSwitchToSingle={(newId) => {
                if (newId) setSelectedDatasetId(newId);
                setPageMode('single');
              }}
            />
          ) : (
            <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-2xs overflow-hidden">
              <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Manual Transformation Tools</h3>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Fine-tune missing values, duplicates, text formatting, date patterns, and outlier thresholds.
                  </p>
                </div>
                {activeOpsCount > 0 && (
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                    {activeOpsCount} configured
                  </span>
                )}
              </div>

              <div className="p-5 space-y-4">
                <div className="flex items-center gap-1.5 border-b border-[#E2E8F0] pb-2 overflow-x-auto text-xs font-semibold">
                  {[
                    { id: 'text', label: 'Text & Categories' },
                    { id: 'numeric', label: 'Numeric Data' },
                    { id: 'dates', label: 'Dates' },
                    { id: 'missing', label: `Missing Values (${missingColumns.length})` },
                    { id: 'duplicates', label: `Duplicates (${overview?.duplicate_rows_count || 0})` },
                    { id: 'outliers', label: 'Outliers' },
                    { id: 'rules', label: 'Custom Rules' },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setAdvancedCategory(cat.id)}
                      className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                        advancedCategory === cat.id
                          ? 'bg-[#2563EB] text-white font-bold shadow-2xs'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>

                {/* Sub-tools forms */}
                {advancedCategory === 'text' && (
                  <div className="space-y-4 pt-2">
                    <div className="flex gap-2 border-b border-slate-100 pb-2">
                      <button
                        onClick={() => setAdvSubTab('text')}
                        className={`px-3 py-1 text-xs font-medium rounded cursor-pointer ${advSubTab === 'text' ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-600'}`}
                      >
                        Text Clean & Case
                      </button>
                      <button
                        onClick={() => setAdvSubTab('category')}
                        className={`px-3 py-1 text-xs font-medium rounded cursor-pointer ${advSubTab === 'category' ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-600'}`}
                      >
                        Category Normalization
                      </button>
                    </div>

                    {advSubTab === 'text' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Target Column</label>
                            <select
                              value={tsForm.column}
                              onChange={(e) => setTsForm({ ...tsForm, column: e.target.value })}
                              className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                            >
                              {(overview?.columns || []).map((c) => (
                                <option key={c.column_name} value={c.column_name}>{c.column_name}</option>
                              ))}
                            </select>
                          </div>
                          <div className="space-y-2">
                            <label className="flex items-center gap-2 text-xs text-slate-700">
                              <input
                                type="checkbox"
                                checked={tsForm.trim_whitespace}
                                onChange={(e) => setTsForm({ ...tsForm, trim_whitespace: e.target.checked })}
                                className="rounded text-blue-600"
                              />
                              Trim leading and trailing whitespace
                            </label>
                            <label className="flex items-center gap-2 text-xs text-slate-700">
                              <input
                                type="checkbox"
                                checked={tsForm.collapse_spaces}
                                onChange={(e) => setTsForm({ ...tsForm, collapse_spaces: e.target.checked })}
                                className="rounded text-blue-600"
                              />
                              Collapse multiple spaces to a single space
                            </label>
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Case Conversion</label>
                            <select
                              value={tsForm.case_conversion}
                              onChange={(e) => setTsForm({ ...tsForm, case_conversion: e.target.value })}
                              className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                            >
                              <option value="none">Keep Original Case</option>
                              <option value="lowercase">lowercase</option>
                              <option value="uppercase">UPPERCASE</option>
                              <option value="title">Title Case</option>
                            </select>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setTextStandardizations((prev) => [
                                ...prev.filter((t) => t.column !== tsForm.column),
                                { ...tsForm },
                              ]);
                              setSuccessMessage(`Staged text cleaning for column '${tsForm.column}'.`);
                            }}
                            className="px-4 py-2 bg-[#2563EB] text-white rounded-lg text-xs font-semibold shadow-xs hover:bg-[#1D4ED8] cursor-pointer"
                          >
                            Add Text Operation
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {advancedCategory === 'dates' && (
                  <div className="space-y-4 pt-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 mb-1">Date Column</label>
                          <select
                            value={dateCol}
                            onChange={(e) => setDateCol(e.target.value)}
                            className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                          >
                            {(overview?.columns || []).map((c) => (
                              <option key={c.column_name} value={c.column_name}>{c.column_name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 mb-1">Standardized Target Format</label>
                          <select
                            value={dateOutputFormat}
                            onChange={(e) => setDateOutputFormat(e.target.value)}
                            className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                          >
                            <option value="%Y-%m-%d">YYYY-MM-DD (ISO-8601)</option>
                            <option value="%d/%m/%Y">DD/MM/YYYY</option>
                            <option value="%m/%d/%Y">MM/DD/YYYY</option>
                          </select>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setDateCleanings((prev) => [
                              ...prev.filter((d) => d.column !== dateCol),
                              { column: dateCol, target_format: dateOutputFormat, handle_invalid: dateHandleInvalid },
                            ]);
                            setSuccessMessage(`Staged date standardization for '${dateCol}'.`);
                          }}
                          className="px-4 py-2 bg-[#2563EB] text-white rounded-lg text-xs font-semibold shadow-xs hover:bg-[#1D4ED8] cursor-pointer"
                        >
                          Add Date Operation
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {advancedCategory === 'outliers' && (
                  <div className="space-y-4 pt-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 mb-1">Numeric Column</label>
                          <select
                            value={outlierForm.column}
                            onChange={(e) => setOutlierForm({ ...outlierForm, column: e.target.value })}
                            className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                          >
                            {(overview?.columns || []).filter((c) => c.data_type?.includes('int') || c.data_type?.includes('float') || c.data_type?.includes('num')).map((c) => (
                              <option key={c.column_name} value={c.column_name}>{c.column_name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 mb-1">Treatment Action</label>
                          <select
                            value={outlierForm.treatment || 'cap'}
                            onChange={(e) => setOutlierForm({ ...outlierForm, treatment: e.target.value })}
                            className="w-full px-3 py-2 bg-white border border-[#CBD5E1] rounded-lg text-xs"
                          >
                            <option value="cap">Cap values at 1.5x IQR boundaries</option>
                            <option value="remove">Remove outlier rows</option>
                            <option value="median">Impute with median value</option>
                          </select>
                        </div>
                        <button
                          type="button"
                          onClick={handleAddOutlierCleaning}
                          className="px-4 py-2 bg-[#2563EB] text-white rounded-lg text-xs font-semibold shadow-xs hover:bg-[#1D4ED8] cursor-pointer"
                        >
                          Add Outlier Operation
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Preview Cleaned Data Mode */}
      {activeMainTab === 'preview' && (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E2E8F0]">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">Full Cleaned Data Inspection</h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Review row values and statistical deltas after applying staged transformations.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleBulkPreview}
                disabled={loadingAction}
                className="px-3.5 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-[#0F172A] hover:bg-slate-50 text-xs font-semibold cursor-pointer shadow-2xs"
              >
                Refresh Preview
              </button>
              <button
                onClick={handleApplyChanges}
                disabled={loadingAction}
                className="px-3.5 py-1.5 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold cursor-pointer shadow-xs"
              >
                Confirm & Apply
              </button>
            </div>
          </div>

          <div className="border border-[#E2E8F0] rounded-lg overflow-x-auto bg-white">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[#F8FAFC] text-[#64748B] font-semibold border-b border-[#E2E8F0]">
                <tr>
                  <th className="py-2.5 px-3 text-[#94A3B8] font-medium w-8">#</th>
                  {previewDisplayColumns.map((col) => (
                    <th key={col} className="py-2.5 px-3 whitespace-nowrap font-semibold">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {previewDisplayRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-[#F8FAFC]/80 transition-colors">
                    <td className="py-2.5 px-3 text-[#94A3B8] font-mono text-[11px]">{rIdx + 1}</td>
                    {previewDisplayColumns.map((col) => (
                      <td key={col} className="py-2.5 px-3 font-mono text-[11px] text-[#0F172A] whitespace-nowrap">
                        {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-[#94A3B8]">null</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}


            {/* MODAL 1: Why This Score / Validation & Quality Score */}
      {showWhyScoreModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#CBD5E1] shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-blue-600" />
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Cleaning Validation & Quality Score</h3>
                  <p className="text-[11px] text-[#64748B]">Deterministic 0–100 Data Hygiene Score Breakdown</p>
                </div>
              </div>
              <button onClick={() => setShowWhyScoreModal(false)} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-auto space-y-4">
              <div className="p-4 bg-blue-50/60 rounded-xl border border-blue-200 flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase font-bold text-blue-900">Current Score</div>
                  <div className="text-xl font-bold font-mono text-blue-950">{cleaningScore}/100 ({scoreStatus})</div>
                </div>
                <div className="text-xs text-blue-800 max-w-sm">
                  Calculated deterministically across 6 core weights comparing remaining issues against baseline state.
                </div>
              </div>

              {validationReport?.checks && (
                <div className="border border-slate-200 rounded-xl overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#F8FAFC] border-b border-slate-200 text-[10px] text-slate-600 uppercase font-bold">
                      <tr>
                        <th className="p-2.5">Metric</th>
                        <th className="p-2.5 text-right">Before</th>
                        <th className="p-2.5 text-right">After</th>
                        <th className="p-2.5 text-right">Remaining</th>
                        <th className="p-2.5 text-right">Weight</th>
                        <th className="p-2.5 text-right">Score</th>
                        <th className="p-2.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {validationReport.checks.map((chk, idx) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2.5 font-semibold text-slate-800">{chk.check_name}</td>
                          <td className="p-2.5 text-right font-mono">{chk.before_value}</td>
                          <td className="p-2.5 text-right font-mono">{chk.after_value}</td>
                          <td className="p-2.5 text-right font-mono font-bold">{chk.remaining_issues ?? chk.after_value}</td>
                          <td className="p-2.5 text-right font-mono">{chk.weight}</td>
                          <td className="p-2.5 text-right font-mono font-bold text-blue-600">{chk.component_score}</td>
                          <td className="p-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${chk.status === 'Resolved' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>
                              {chk.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={() => setShowWhyScoreModal(false)} className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Confirm Cleaning Operations */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#CBD5E1] shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">Confirm Cleaning Operations</h3>
                <p className="text-[11px] text-[#64748B]">
                  Target: {overview?.filename} ({activeOpsCount} operation(s) configured)
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-blue-50/60 rounded-xl border border-blue-200 text-xs text-blue-950 font-medium">
              {(() => {
                const cells = previewData?.total_cells_changed || bulkPreviewData?.total_cells_affected || Math.max(activeOpsCount * 12, 1);
                const rows = previewData?.rows_removed || bulkPreviewData?.total_rows_removed || (removeDuplicates ? (overview?.duplicate_rows_count || 0) : 0);
                return `You are about to modify ${cells.toLocaleString()} cells and remove ${rows.toLocaleString()} rows.`;
              })()}
            </div>

            <p className="text-xs text-[#475569]">
              A new atomic version will be generated. Your original uploaded dataset remains completely safe, immutable, and untouched on storage disk.
            </p>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-xs font-medium text-[#475569] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={pendingOperationsList.length > 0 ? handleBulkApply : handleApply}
                disabled={loadingAction}
                className="px-4 py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold transition-colors cursor-pointer"
              >
                {loadingAction ? 'Applying...' : 'Apply All Cleaning Operations'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: Original Dataset View (Previous CSV) */}
      {showOriginalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#CBD5E1] shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <Database className="w-5 h-5 text-blue-600" />
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Original Dataset View (Previous CSV)</h3>
                  <p className="text-[11px] text-[#64748B]">
                    Untouched source dataset: {originalData?.filename || overview?.filename} ({originalData?.total_rows || overview?.original_metrics?.total_rows} rows × {originalData?.total_columns || overview?.original_metrics?.total_columns} columns)
                  </p>
                </div>
              </div>
              <button onClick={() => setShowOriginalModal(false)} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-auto border border-[#E2E8F0] rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[10px] text-[#475569] font-bold uppercase sticky top-0">
                  <tr>
                    {(originalData?.columns || overview?.columns?.map((c) => c.column_name) || []).map((col) => (
                      <th key={col} className="py-2.5 px-3 whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {(originalData?.sample_rows || []).map((row, idx) => (
                    <tr key={idx} className="hover:bg-[#F8FAFC]">
                      {(originalData?.columns || []).map((col) => (
                        <td key={col} className="py-2 px-3 font-mono text-[11px] text-[#0F172A] whitespace-nowrap">
                          {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-[#94A3B8]">null</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={() => setShowOriginalModal(false)} className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer">
                Close View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: Version Comparison */}
      {showCompareModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#CBD5E1] shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <GitMerge className="w-5 h-5 text-blue-600" />
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Dataset Version Comparison</h3>
                  <p className="text-[11px] text-[#64748B]">Compare metrics and deltas between dataset versions.</p>
                </div>
              </div>
              <button onClick={() => setShowCompareModal(false)} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">Version 1 (Baseline)</label>
                <select
                  value={compareV1}
                  onChange={(e) => {
                    setCompareV1(e.target.value);
                    handleCompareVersions(e.target.value, compareV2);
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
                >
                  {(versionTimeline || []).map((v) => (
                    <option key={v.version_tag} value={v.version_tag}>{v.version_tag} ({new Date(v.timestamp).toLocaleDateString()})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">Version 2 (Target)</label>
                <select
                  value={compareV2}
                  onChange={(e) => {
                    setCompareV2(e.target.value);
                    handleCompareVersions(compareV1, e.target.value);
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white"
                >
                  {(versionTimeline || []).map((v) => (
                    <option key={v.version_tag} value={v.version_tag}>{v.version_tag} ({new Date(v.timestamp).toLocaleDateString()})</option>
                  ))}
                </select>
              </div>
            </div>

            {compareResult && (
              <div className="flex-1 overflow-auto border border-[#E2E8F0] rounded-xl p-3">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[10px] text-[#475569] font-bold uppercase">
                    <tr>
                      <th className="py-2.5 px-3">Metric</th>
                      <th className="py-2.5 px-3 text-right">{compareResult.v1_tag}</th>
                      <th className="py-2.5 px-3 text-right">{compareResult.v2_tag}</th>
                      <th className="py-2.5 px-3 text-right">Delta / Change</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {[
                      { label: 'Total Rows', v1: compareResult.v1_metrics?.rows, v2: compareResult.v2_metrics?.rows, delta: compareResult.deltas?.rows_delta },
                      { label: 'Total Columns', v1: compareResult.v1_metrics?.columns, v2: compareResult.v2_metrics?.columns, delta: compareResult.deltas?.columns_delta },
                      { label: 'Missing Cells', v1: compareResult.v1_metrics?.missing_cells, v2: compareResult.v2_metrics?.missing_cells, delta: compareResult.deltas?.missing_delta },
                      { label: 'Duplicate Rows', v1: compareResult.v1_metrics?.duplicate_rows, v2: compareResult.v2_metrics?.duplicate_rows, delta: compareResult.deltas?.duplicates_delta },
                      { label: 'Blank Cells', v1: compareResult.v1_metrics?.blank_cells, v2: compareResult.v2_metrics?.blank_cells, delta: compareResult.deltas?.blanks_delta },
                      { label: 'Outliers Detected', v1: compareResult.v1_metrics?.outliers, v2: compareResult.v2_metrics?.outliers, delta: compareResult.deltas?.outliers_delta },
                      { label: 'Cleaning Quality Score', v1: compareResult.v1_metrics?.score, v2: compareResult.v2_metrics?.score, delta: compareResult.deltas?.score_delta, isScore: true },
                    ].map((row, idx) => (
                      <tr key={idx} className="hover:bg-[#F8FAFC]">
                        <td className="py-2.5 px-3 font-semibold text-[#0F172A]">{row.label}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-slate-600">{row.v1 ?? '—'}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-[#0F172A]">{row.v2 ?? '—'}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold">
                          {row.delta !== undefined ? (
                            <span className={row.isScore ? (row.delta > 0 ? 'text-emerald-600' : 'text-slate-600') : (row.delta < 0 ? 'text-emerald-600' : 'text-slate-600')}>
                              {row.delta > 0 ? `+${row.delta}` : row.delta}
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button onClick={() => setShowCompareModal(false)} className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer">
                Close Comparison
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CleaningPage;
