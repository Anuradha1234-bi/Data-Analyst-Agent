import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Database,
  UploadCloud,
  Sparkles,
  ArrowRight,
  FileSpreadsheet,
  FileText,
  BarChart3,
  TrendingUp,
  Layers,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Download,
  Activity,
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  BarChart2,
  Info,
  SlidersHorizontal,
  ExternalLink,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { analyticsService } from '../services/analyticsService';
import { extractErrorMessage } from '../services/api';

export const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // 1. Repository-wide datasets state
  const [datasets, setDatasets] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [datasetError, setDatasetError] = useState('');

  // 2. Active selected dataset state
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);

  // 3. Active dataset profiling and statistics
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [profileError, setProfileError] = useState('');

  // 4. Interactive visualization controls
  const [selectedNumericCol, setSelectedNumericCol] = useState('');
  const [selectedCategoricalCol, setSelectedCategoricalCol] = useState('');
  const [hoveredDonutSlice, setHoveredDonutSlice] = useState(null);

  // 5. Dynamic chart states fetched from analytics API
  const [histogramData, setHistogramData] = useState(null);
  const [loadingHistogram, setLoadingHistogram] = useState(false);
  const [heatmapData, setHeatmapData] = useState(null);
  const [loadingHeatmap, setLoadingHeatmap] = useState(false);
  const [insights, setInsights] = useState([]);
  const [loadingInsights, setLoadingInsights] = useState(false);

  // Request cancellation / race condition prevention
  const requestIdRef = useRef(0);

  // --------------------------------------------------------------------------
  // Step 1: Initial Load — Fetch all datasets for user
  // --------------------------------------------------------------------------
  const fetchDatasets = async () => {
    setLoadingDatasets(true);
    setDatasetError('');
    try {
      const data = await datasetService.getDatasets();
      const list = Array.isArray(data) ? data : [];
      setDatasets(list);

      // Determine initial selected dataset ID from query param, localStorage, or first dataset
      const paramId = searchParams.get('dataset_id') || searchParams.get('id');
      const savedId = localStorage.getItem('selected_dataset_id');

      let targetId = null;
      if (paramId && list.some((d) => d.id === Number(paramId))) {
        targetId = Number(paramId);
      } else if (savedId && list.some((d) => d.id === Number(savedId))) {
        targetId = Number(savedId);
      } else if (list.length > 0) {
        targetId = list[0].id;
      }

      if (targetId) {
        setSelectedDatasetId(targetId);
        setSearchParams({ dataset_id: String(targetId) }, { replace: true });
        localStorage.setItem('selected_dataset_id', String(targetId));
      }
    } catch (err) {
      setDatasetError(extractErrorMessage(err));
    } finally {
      setLoadingDatasets(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------------------------------------------------------------------
  // Step 2: Load Active Dataset Profile & Statistics whenever selectedDatasetId changes
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedDatasetId) {
      setProfile(null);
      setHistogramData(null);
      setHeatmapData(null);
      setInsights([]);
      return;
    }

    const currentReqId = ++requestIdRef.current;
    setLoadingProfile(true);
    setProfileError('');

    const loadDatasetData = async () => {
      try {
        const prof = await datasetService.getDatasetProfile(selectedDatasetId);
        if (currentReqId !== requestIdRef.current) return;

        setProfile(prof);

        // Detect usable numeric columns (excluding pure identifier columns where unique == total rows and name contains 'id')
        const cols = prof?.columns || [];
        const numericCols = cols.filter(
          (c) => c.semantic_type === 'NUMERIC' || Boolean(c.numeric_stats)
        );

        // Auto-select preferred numeric column (prefer non-ID numeric column)
        const nonIdNumeric = numericCols.find(
          (c) => !c.name.toLowerCase().endsWith('id') && !c.name.toLowerCase().endsWith('_id')
        );
        const defaultNumCol = nonIdNumeric ? nonIdNumeric.name : numericCols[0]?.name || '';
        setSelectedNumericCol(defaultNumCol);

        // Detect usable categorical columns (prefer unique count between 2 and 30)
        const catCols = cols.filter(
          (c) =>
            (c.semantic_type === 'CATEGORICAL' || Boolean(c.categorical_stats)) &&
            c.unique_count >= 2 &&
            c.unique_count <= 35 &&
            !c.name.toLowerCase().endsWith('id')
        );
        const defaultCatCol = catCols[0]?.name || cols.find((c) => c.semantic_type === 'CATEGORICAL')?.name || '';
        setSelectedCategoricalCol(defaultCatCol);
      } catch (err) {
        if (currentReqId !== requestIdRef.current) return;
        setProfileError(extractErrorMessage(err));
        setProfile(null);
      } finally {
        if (currentReqId === requestIdRef.current) {
          setLoadingProfile(false);
        }
      }
    };

    loadDatasetData();
  }, [selectedDatasetId]);

  // --------------------------------------------------------------------------
  // Step 3: Load Histogram when selectedNumericCol or selectedDatasetId changes
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedDatasetId || !selectedNumericCol) {
      setHistogramData(null);
      return;
    }

    let isSubscribed = true;
    setLoadingHistogram(true);

    const loadHistogram = async () => {
      try {
        const res = await analyticsService.generateChart({
          dataset_id: selectedDatasetId,
          chart_type: 'histogram',
          x_column: selectedNumericCol,
          y_column: selectedNumericCol,
          bins: 7,
        });
        if (isSubscribed) {
          setHistogramData(res);
        }
      } catch {
        if (isSubscribed) {
          setHistogramData(null);
        }
      } finally {
        if (isSubscribed) {
          setLoadingHistogram(false);
        }
      }
    };

    loadHistogram();
    return () => {
      isSubscribed = false;
    };
  }, [selectedDatasetId, selectedNumericCol]);

  // --------------------------------------------------------------------------
  // Step 4: Load Heatmap & Insights for selected dataset
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedDatasetId) {
      setHeatmapData(null);
      setInsights([]);
      return;
    }

    let isSubscribed = true;
    setLoadingHeatmap(true);
    setLoadingInsights(true);

    // Heatmap request
    analyticsService
      .generateChart({
        dataset_id: selectedDatasetId,
        chart_type: 'heatmap',
      })
      .then((res) => {
        if (isSubscribed) setHeatmapData(res);
      })
      .catch(() => {
        if (isSubscribed) setHeatmapData(null);
      })
      .finally(() => {
        if (isSubscribed) setLoadingHeatmap(false);
      });

    // Insights request
    analyticsService
      .getInsights(selectedDatasetId)
      .then((res) => {
        if (isSubscribed) {
          setInsights(res?.insights || []);
        }
      })
      .catch(() => {
        if (isSubscribed) setInsights([]);
      })
      .finally(() => {
        if (isSubscribed) setLoadingInsights(false);
      });

    return () => {
      isSubscribed = false;
    };
  }, [selectedDatasetId]);

  // --------------------------------------------------------------------------
  // Handler: Dataset selection change
  // --------------------------------------------------------------------------
  const handleDatasetChange = (e) => {
    const newId = Number(e.target.value);
    if (!newId || isNaN(newId)) return;
    setSelectedDatasetId(newId);
    setSearchParams({ dataset_id: String(newId) }, { replace: true });
    localStorage.setItem('selected_dataset_id', String(newId));
  };

  const handleRefresh = () => {
    fetchDatasets();
  };

  // --------------------------------------------------------------------------
  // Computed Properties & Helpers
  // --------------------------------------------------------------------------
  const displayName = user?.full_name || user?.name || user?.username || 'Analyst';
  const totalDatasets = datasets.length;
  const totalRows = datasets.reduce((acc, d) => acc + (d.row_count ?? d.rows ?? 0), 0);
  const totalCols = datasets.reduce((acc, d) => acc + (d.column_count ?? d.columns ?? 0), 0);
  const totalBytes = datasets.reduce((acc, d) => acc + (d.file_size_bytes ?? d.file_size ?? 0), 0);

  const activeDatasetMeta = datasets.find((d) => d.id === selectedDatasetId);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Extract Column Lists
  const columnsList = profile?.columns || [];
  const usableNumericCols = useMemo(() => {
    return columnsList.filter((c) => c.semantic_type === 'NUMERIC' || Boolean(c.numeric_stats));
  }, [columnsList]);

  const usableCategoricalCols = useMemo(() => {
    return columnsList.filter(
      (c) =>
        (c.semantic_type === 'CATEGORICAL' || Boolean(c.categorical_stats)) &&
        c.unique_count >= 2 &&
        c.unique_count <= 50
    );
  }, [columnsList]);

  // Active numeric column profile item
  const activeNumericColProfile = useMemo(() => {
    return usableNumericCols.find((c) => c.name === selectedNumericCol);
  }, [usableNumericCols, selectedNumericCol]);

  // Active categorical column profile item
  const activeCategoricalColProfile = useMemo(() => {
    return usableCategoricalCols.find((c) => c.name === selectedCategoricalCol) || usableCategoricalCols[0];
  }, [usableCategoricalCols, selectedCategoricalCol]);

  // Mutually Exclusive Data Types Breakdown
  const typeBreakdown = useMemo(() => {
    const total = profile?.dataset_info?.columns || columnsList.length || 0;
    if (total === 0) {
      return { total: 0, items: [] };
    }

    const counts = profile?.quality_summary?.type_counts || {};
    let numeric = counts.NUMERIC ?? columnsList.filter((c) => c.semantic_type === 'NUMERIC').length;
    let categorical = counts.CATEGORICAL ?? columnsList.filter((c) => c.semantic_type === 'CATEGORICAL').length;
    let datetime = counts.DATETIME ?? columnsList.filter((c) => c.semantic_type === 'DATETIME').length;
    let boolean = counts.BOOLEAN ?? columnsList.filter((c) => c.semantic_type === 'BOOLEAN').length;
    let textOther = total - (numeric + categorical + datetime + boolean);
    if (textOther < 0) textOther = 0;

    const items = [
      {
        id: 'numeric',
        label: 'Numeric',
        count: numeric,
        percentage: Number(((numeric / total) * 100).toFixed(1)),
        color: '#2563EB',
      },
      {
        id: 'categorical',
        label: 'Categorical',
        count: categorical,
        percentage: Number(((categorical / total) * 100).toFixed(1)),
        color: '#8B5CF6',
      },
      {
        id: 'datetime',
        label: 'Date/Time',
        count: datetime,
        percentage: Number(((datetime / total) * 100).toFixed(1)),
        color: '#10B981',
      },
      {
        id: 'boolean',
        label: 'Boolean',
        count: boolean,
        percentage: Number(((boolean / total) * 100).toFixed(1)),
        color: '#F59E0B',
      },
    ];

    if (textOther > 0) {
      items.push({
        id: 'other',
        label: 'Text / Other',
        count: textOther,
        percentage: Number(((textOther / total) * 100).toFixed(1)),
        color: '#64748B',
      });
    }

    return { total, items };
  }, [profile, columnsList]);

  // Missing Values Information
  const missingInfo = useMemo(() => {
    const totalMissing = profile?.quality_summary?.total_missing_cells ?? 0;
    const totalCells = profile?.dataset_info?.total_cells ?? (profile?.dataset_info?.rows || 0) * (profile?.dataset_info?.columns || 0);
    const missingPct = totalCells > 0 ? ((totalMissing / totalCells) * 100).toFixed(1) : '0.0';

    const missingCols = (profile?.quality_summary?.missing_columns || []).map((m) => ({
      column: m.column,
      count: m.missing_count,
      percentage: Number(m.missing_percentage.toFixed(1)),
    }));

    return {
      totalMissing,
      totalCells,
      missingPct,
      hasMissing: totalMissing > 0,
      columnsWithMissing: missingCols,
    };
  }, [profile]);

  // Fallback Derived Insights if API returns empty
  const displayInsights = useMemo(() => {
    if (insights && insights.length > 0) {
      return insights.slice(0, 4);
    }
    if (!profile) return [];

    const generated = [];
    const q = profile.quality_summary;
    const rows = profile.dataset_info?.rows || 0;

    // Missing data check
    if (q?.total_missing_cells === 0) {
      generated.push({
        id: 'ins_clean',
        type: 'missing_values',
        title: 'Complete Data Integrity',
        statement: `Verified 0 missing cells across all ${profile.dataset_info?.columns || 0} features. Dataset is fully populated and hygiene-ready.`,
        severity: 'Informational',
      });
    } else if (q?.total_missing_cells > 0) {
      generated.push({
        id: 'ins_missing',
        type: 'missing_values',
        title: 'Missing Values Present',
        statement: `Found ${q.total_missing_cells} missing data cells (${q.missing_percentage}%). Data cleaning/imputation is recommended.`,
        severity: 'Warning',
      });
    }

    // High category dominance check
    const domCat = columnsList.find(
      (c) => c.categorical_stats?.top_values && c.categorical_stats.top_values[0]?.percentage >= 45
    );
    if (domCat && domCat.categorical_stats?.top_values[0]) {
      const topV = domCat.categorical_stats.top_values[0];
      generated.push({
        id: 'ins_dom',
        type: 'concentration',
        title: 'Category Concentration',
        statement: `Value '${topV.value}' accounts for ${topV.percentage}% of all records in '${domCat.name}'.`,
        severity: 'Informational',
      });
    }

    // Outlier check in numeric stats
    const highVarianceCol = usableNumericCols.find(
      (c) => c.numeric_stats && c.numeric_stats.max > c.numeric_stats.q3 + 2.5 * c.numeric_stats.iqr && c.numeric_stats.iqr > 0
    );
    if (highVarianceCol) {
      generated.push({
        id: 'ins_skew',
        type: 'outlier',
        title: 'Right-Skewed Distribution',
        statement: `'${highVarianceCol.name}' exhibits significant positive skewness with high extreme values up to ${highVarianceCol.numeric_stats.max}.`,
        severity: 'Informational',
      });
    }

    // Duplicate rows check
    if (q?.duplicate_rows > 0) {
      generated.push({
        id: 'ins_dup',
        type: 'duplicates',
        title: 'Duplicate Observations Found',
        statement: `Detected ${q.duplicate_rows} duplicate rows (${q.duplicate_percentage}%) in the selected dataset.`,
        severity: 'Warning',
      });
    } else {
      generated.push({
        id: 'ins_unique',
        type: 'quality',
        title: 'Row Uniqueness Verified',
        statement: `All ${rows} observations are distinct rows with 0 duplicate records detected.`,
        severity: 'Informational',
      });
    }

    return generated.slice(0, 4);
  }, [insights, profile, columnsList, usableNumericCols]);

  return (
    <div className="w-full space-y-4 font-sans text-[#0F172A] dark:text-[#F8FAFC] pb-10">
      {/* =========================================================================
          1. HEADER BANNER WITH ACTIVE DATASET SELECTOR
      ========================================================================= */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#EFF6FF] via-[#E0E7FF]/40 to-[#DBEAFE]/70 dark:from-[#0B132B] dark:via-[#131F3F] dark:to-[#0E172E] border border-[#BFDBFE] dark:border-[#1E293B] p-6 shadow-2xs">
        <div className="relative z-10 max-w-3xl space-y-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#EFF6FF] dark:bg-[#131F3F] border border-[#BFDBFE] dark:border-[#2563EB]/40 text-[#1D4ED8] dark:text-[#60A5FA] text-xs font-semibold shadow-2xs">
              <Database className="w-3.5 h-3.5 text-[#2563EB]" />
              <span>AI Data Analyst Workspace</span>
            </div>

            {/* Active Dataset Pill */}
            {activeDatasetMeta && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="truncate max-w-[200px]">{activeDatasetMeta.filename || activeDatasetMeta.original_filename}</span>
              </span>
            )}
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A] dark:text-white">
            Welcome, {displayName} 👋
          </h1>

          <p className="text-xs text-[#475569] dark:text-[#94A3B8] leading-relaxed">
            Select an uploaded dataset below to inspect its live data distributions, schema profiling,
            correlation matrix, and AI-grounded insights computed directly from the CSV content.
          </p>

          {/* Dataset Selector & Quick Action Bar */}
          <div className="pt-2 flex flex-wrap items-center gap-3">
            {/* Dynamic Dataset Selector */}
            <div className="relative min-w-[240px] max-w-sm">
              <label htmlFor="dataset-selector" className="sr-only">
                Select Active Dataset
              </label>
              <div className="relative flex items-center">
                <Database className="w-4 h-4 text-[#2563EB] absolute left-3 pointer-events-none" />
                <select
                  id="dataset-selector"
                  value={selectedDatasetId || ''}
                  onChange={handleDatasetChange}
                  disabled={loadingDatasets || datasets.length === 0}
                  className="w-full appearance-none bg-white dark:bg-[#0F172A] border border-[#CBD5E1] dark:border-[#1E293B] rounded-xl pl-9 pr-9 py-2 text-xs font-semibold text-[#0F172A] dark:text-white shadow-2xs focus:outline-none focus:ring-2 focus:ring-[#2563EB]/40 cursor-pointer disabled:opacity-50"
                >
                  {datasets.length === 0 ? (
                    <option value="">No datasets uploaded yet</option>
                  ) : (
                    datasets.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.filename || d.original_filename} ({d.rows || d.row_count || 0} rows, {d.columns || d.column_count || 0} cols)
                      </option>
                    ))
                  )}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-[#64748B] dark:text-slate-400 absolute right-3 pointer-events-none" />
              </div>
            </div>

            {/* Refresh Button */}
            <button
              type="button"
              id="refresh-dashboard-btn"
              onClick={handleRefresh}
              disabled={loadingDatasets || loadingProfile}
              className="flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-[#131F3F] border border-[#CBD5E1] dark:border-[#1E293B] text-[#0F172A] dark:text-slate-200 text-xs font-semibold rounded-xl shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
              title="Refresh dataset analytics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingProfile ? 'spin text-[#2563EB]' : ''}`} />
              <span>Refresh</span>
            </button>

            {/* Upload Dataset Button */}
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="flex items-center gap-2 px-4 py-2 bg-[#1E6BFF] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload CSV</span>
            </button>

            {/* View All Datasets */}
            <button
              type="button"
              onClick={() => navigate('/datasets')}
              className="flex items-center gap-2 px-3.5 py-2 bg-white dark:bg-[#0F172A] hover:bg-slate-50 dark:hover:bg-[#131F3F] border border-[#CBD5E1] dark:border-[#1E293B] text-[#0F172A] dark:text-slate-200 text-xs font-semibold rounded-xl shadow-2xs transition-colors cursor-pointer"
            >
              <Layers className="w-3.5 h-3.5 text-[#2563EB]" />
              <span>Repository ({totalDatasets})</span>
            </button>
          </div>
        </div>
      </div>

      {/* =========================================================================
          ERROR / EMPTY STATE NOTIFICATIONS
      ========================================================================= */}
      {datasetError && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40 text-red-700 dark:text-red-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-500" />
            <span>{datasetError}</span>
          </div>
          <button onClick={fetchDatasets} className="font-semibold underline cursor-pointer ml-4">
            Retry
          </button>
        </div>
      )}

      {profileError && (
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 text-amber-800 dark:text-amber-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500" />
            <span>Failed to profile dataset #{selectedDatasetId}: {profileError}</span>
          </div>
          <button onClick={() => setSelectedDatasetId((prev) => prev)} className="font-semibold underline cursor-pointer ml-4">
            Retry
          </button>
        </div>
      )}

      {/* No Datasets in Workspace Empty State */}
      {!loadingDatasets && datasets.length === 0 && (
        <div className="p-8 text-center bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl shadow-2xs space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-blue-50 dark:bg-[#131F3F] text-[#2563EB] flex items-center justify-center">
            <FileSpreadsheet className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold text-[#0F172A] dark:text-white">No Datasets Uploaded</h2>
          <p className="text-xs text-[#64748B] dark:text-[#94A3B8] max-w-md mx-auto">
            Upload your first CSV or Excel file to unlock automated data profiling, interactive distributions,
            correlation analysis, and AI-powered insights.
          </p>
          <button
            type="button"
            onClick={() => navigate('/upload')}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#1E6BFF] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Your First Dataset</span>
          </button>
        </div>
      )}

      {/* =========================================================================
          2. GROUNDED KPI METRICS CARDS (Grounded in selected dataset + workspace totals)
      ========================================================================= */}
      {selectedDatasetId && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Card 1: Active Dataset Rows */}
          <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] dark:bg-[#131F3F] text-[#2563EB] dark:text-[#60A5FA] flex items-center justify-center shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-[#64748B] dark:text-[#94A3B8] font-medium">Dataset Rows</div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-black text-[#0F172A] dark:text-white leading-tight">
                  {profile ? profile.dataset_info?.rows.toLocaleString() : activeDatasetMeta?.rows?.toLocaleString() || '—'}
                </span>
                <span className="text-[10px] font-bold text-blue-600 dark:text-[#60A5FA] bg-blue-50 dark:bg-blue-950/40 px-1.5 py-0.2 rounded border border-blue-200 dark:border-blue-900/40">
                  Active
                </span>
              </div>
              <span className="text-[10px] text-[#94A3B8] block truncate">
                {totalRows.toLocaleString()} across {totalDatasets} files
              </span>
            </div>
          </div>

          {/* Card 2: Active Dataset Columns */}
          <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#FAF5FF] dark:bg-[#131F3F] text-[#9333EA] dark:text-[#C084FC] flex items-center justify-center shrink-0">
              <Layers className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-[#64748B] dark:text-[#94A3B8] font-medium">Dataset Columns</div>
              <div className="text-2xl font-black text-[#0F172A] dark:text-white leading-tight">
                {profile ? profile.dataset_info?.columns : activeDatasetMeta?.columns || '—'}
              </div>
              <span className="text-[10px] text-[#94A3B8] block truncate">
                {usableNumericCols.length} num • {usableCategoricalCols.length} cat • {totalCols} total
              </span>
            </div>
          </div>

          {/* Card 3: Data Quality Score */}
          <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] dark:bg-[#131F3F] text-[#059669] dark:text-[#34D399] flex items-center justify-center shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-[#64748B] dark:text-[#94A3B8] font-medium">Quality Score</div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-black text-[#0F172A] dark:text-white leading-tight">
                  {profile?.quality_summary ? `${profile.quality_summary.health_score}%` : '—'}
                </span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${
                    missingInfo.hasMissing
                      ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800'
                      : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  }`}
                >
                  {missingInfo.hasMissing ? 'Missing Data' : 'Clean'}
                </span>
              </div>
              <span className="text-[10px] text-[#94A3B8] block truncate">
                {missingInfo.totalMissing} missing cells ({missingInfo.missingPct}%)
              </span>
            </div>
          </div>

          {/* Card 4: Active Dataset Size */}
          <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#FFFBEB] dark:bg-[#131F3F] text-[#D97706] dark:text-[#FBBF24] flex items-center justify-center shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-[#64748B] dark:text-[#94A3B8] font-medium">Dataset File Size</div>
              <div className="text-2xl font-black text-[#0F172A] dark:text-white leading-tight truncate">
                {profile ? formatFileSize(profile.dataset_info?.file_size_bytes) : formatFileSize(activeDatasetMeta?.file_size_bytes)}
              </div>
              <span className="text-[10px] text-[#94A3B8] block truncate">
                {formatFileSize(totalBytes)} across repository
              </span>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          3. ROW OF 3 CORE STATISTICAL VISUALIZATIONS
      ========================================================================= */}
      {selectedDatasetId && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* -------------------------------------------------------------------
              CARD 1: DATA TYPES DISTRIBUTION (Dynamic Interactive Donut)
          ------------------------------------------------------------------- */}
          <div
            id="data-types-donut-card"
            className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-[#2563EB]" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Data Types Distribution</h3>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#EFF6FF] dark:bg-[#131F3F] text-[#2563EB] dark:text-[#60A5FA] border border-[#BFDBFE] dark:border-[#2563EB]/40">
                Total Columns: {typeBreakdown.total}
              </span>
            </div>

            {loadingProfile ? (
              <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#2563EB]" />
                <span>Computing column types...</span>
              </div>
            ) : typeBreakdown.total === 0 ? (
              <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                No column data available.
              </div>
            ) : (
              <div className="flex items-center justify-around gap-3 py-1">
                {/* Dynamic SVG Donut Chart */}
                <div className="relative w-28 h-28 shrink-0 flex items-center justify-center">
                  <svg className="w-28 h-28 -rotate-90" viewBox="0 0 42 42">
                    {/* Background Ring */}
                    <circle
                      cx="21"
                      cy="21"
                      r="15.91549430918954"
                      fill="transparent"
                      stroke="currentColor"
                      strokeWidth="3.8"
                      className="text-slate-100 dark:text-[#1E293B]"
                    />

                    {/* Donut Slices */}
                    {(() => {
                      let accumulatedPercentage = 0;
                      return typeBreakdown.items.map((item) => {
                        if (item.percentage <= 0) return null;
                        const strokeDasharray = `${item.percentage} ${100 - item.percentage}`;
                        const strokeDashoffset = -accumulatedPercentage;
                        accumulatedPercentage += item.percentage;

                        return (
                          <circle
                            key={item.id}
                            cx="21"
                            cy="21"
                            r="15.91549430918954"
                            fill="transparent"
                            stroke={item.color}
                            strokeWidth={hoveredDonutSlice === item.id ? '4.8' : '3.8'}
                            strokeDasharray={strokeDasharray}
                            strokeDashoffset={strokeDashoffset}
                            onMouseEnter={() => setHoveredDonutSlice(item.id)}
                            onMouseLeave={() => setHoveredDonutSlice(null)}
                            className="transition-all duration-200 cursor-pointer"
                          />
                        );
                      });
                    })()}
                  </svg>

                  {/* Centered Total / Hover Label */}
                  <div className="absolute text-center leading-tight pointer-events-none select-none">
                    {hoveredDonutSlice ? (
                      (() => {
                        const hovered = typeBreakdown.items.find((i) => i.id === hoveredDonutSlice);
                        return (
                          <>
                            <div className="text-xs font-black text-[#0F172A] dark:text-white">
                              {hovered?.percentage}%
                            </div>
                            <div className="text-[7.5px] font-bold text-[#64748B] dark:text-slate-400 truncate max-w-[55px]">
                              {hovered?.label}
                            </div>
                          </>
                        );
                      })()
                    ) : (
                      <>
                        <div className="text-sm font-black text-[#0F172A] dark:text-white">
                          {typeBreakdown.total}
                        </div>
                        <div className="text-[8px] text-[#64748B] dark:text-[#94A3B8]">Columns</div>
                      </>
                    )}
                  </div>
                </div>

                {/* Accurate Dynamic Legend */}
                <div className="space-y-1.5 text-[11px] flex-1 min-w-0">
                  {typeBreakdown.items.map((item) => (
                    <div
                      key={item.id}
                      onMouseEnter={() => setHoveredDonutSlice(item.id)}
                      onMouseLeave={() => setHoveredDonutSlice(null)}
                      className={`flex items-center justify-between p-1 rounded-lg transition-colors cursor-pointer ${
                        hoveredDonutSlice === item.id ? 'bg-slate-100 dark:bg-[#131F3F]' : ''
                      }`}
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                        <span className="text-[#64748B] dark:text-slate-300 truncate">{item.label}</span>
                      </div>
                      <span className="font-semibold text-[#0F172A] dark:text-white shrink-0 ml-1">
                        {item.count} ({item.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* -------------------------------------------------------------------
              CARD 2: MISSING VALUES OVERVIEW (Zero-Missing Card or Dynamic Bar Chart)
          ------------------------------------------------------------------- */}
          <div
            id="missing-values-overview-card"
            className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-3.5 h-3.5 text-[#2563EB]" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Missing Values Overview</h3>
              </div>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                  missingInfo.hasMissing
                    ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800'
                    : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                }`}
              >
                Total Missing: {missingInfo.totalMissing} ({missingInfo.missingPct}%)
              </span>
            </div>

            {loadingProfile ? (
              <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#2563EB]" />
                <span>Auditing missing values...</span>
              </div>
            ) : !missingInfo.hasMissing ? (
              /* Grounded Zero-Missing State Card */
              <div className="h-32 flex flex-col items-center justify-center p-3 text-center rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 space-y-1.5">
                <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div className="text-xs font-bold text-emerald-800 dark:text-emerald-300">
                  100% Complete — 0 Missing Cells
                </div>
                <p className="text-[10px] text-emerald-700 dark:text-emerald-400/80 leading-tight">
                  All {columnsList.length} columns have zero nulls across {missingInfo.totalCells.toLocaleString()} verified data cells.
                </p>
              </div>
            ) : (
              /* Grounded Missing Values Bar Distribution */
              <div className="space-y-2">
                <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
                  <span>Columns with missing values:</span>
                  <span className="font-semibold text-amber-600 dark:text-amber-400">{missingInfo.columnsWithMissing.length} column(s)</span>
                </div>
                <div className="space-y-1.5 max-h-28 overflow-y-auto pr-1">
                  {missingInfo.columnsWithMissing.map((m) => (
                    <div key={m.column} className="space-y-0.5">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="font-medium text-[#0F172A] dark:text-white truncate max-w-[140px]" title={m.column}>
                          {m.column}
                        </span>
                        <span className="font-semibold text-amber-600 dark:text-amber-400">
                          {m.count} ({m.percentage}%)
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-100 dark:bg-[#1E293B] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full transition-all"
                          style={{ width: `${Math.min(Math.max(m.percentage, 5), 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* -------------------------------------------------------------------
              CARD 3: NUMERIC COLUMNS DISTRIBUTION (Dynamic Column Selector + Real Histogram)
          ------------------------------------------------------------------- */}
          <div
            id="numeric-columns-distribution-card"
            className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2 min-w-0">
                <BarChart3 className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Numeric Distribution</h3>
              </div>

              {/* Dynamic Numeric Column Selector */}
              {usableNumericCols.length > 0 && (
                <div className="relative shrink-0">
                  <select
                    id="numeric-col-selector"
                    value={selectedNumericCol}
                    onChange={(e) => setSelectedNumericCol(e.target.value)}
                    className="appearance-none bg-[#F8FAFC] dark:bg-[#131F3F] border border-[#CBD5E1] dark:border-[#1E293B] rounded-lg px-2 py-0.5 pr-5 text-[10px] font-bold text-[#0F172A] dark:text-white focus:outline-none cursor-pointer max-w-[130px] truncate"
                  >
                    {usableNumericCols.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-2.5 h-2.5 text-[#64748B] absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              )}
            </div>

            {loadingProfile || loadingHistogram ? (
              <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#2563EB]" />
                <span>Generating histogram bins...</span>
              </div>
            ) : usableNumericCols.length === 0 ? (
              <div className="h-32 flex flex-col items-center justify-center text-center p-3 text-xs text-slate-400">
                <Info className="w-5 h-5 mb-1 text-slate-400" />
                <span>No numeric columns available in this dataset.</span>
              </div>
            ) : histogramData?.data_points && histogramData.data_points.length > 0 ? (
              /* Real Histogram Chart */
              <div className="space-y-1">
                {(() => {
                  const points = histogramData.data_points;
                  const maxVal = Math.max(...points.map((p) => p.value || 0), 1);

                  return (
                    <>
                      <div className="h-24 relative flex items-end">
                        {/* Y-axis Ticks */}
                        <div className="flex flex-col justify-between h-full text-[7px] text-[#94A3B8] font-mono pr-1 select-none">
                          <span>{maxVal}</span>
                          <span>{Math.round(maxVal / 2)}</span>
                          <span>0</span>
                        </div>

                        {/* Histogram Bars */}
                        <div className="flex-1 h-full border-l border-b border-slate-300 dark:border-[#1E293B] flex items-end px-1 gap-1">
                          {points.map((pt, i) => {
                            const heightPct = Math.round(((pt.value || 0) / maxVal) * 100);
                            return (
                              <div
                                key={i}
                                className="flex-1 flex flex-col items-center group relative h-full justify-end"
                              >
                                <div
                                  className="w-full bg-[#2563EB] hover:bg-[#1D4ED8] rounded-t-xs transition-all cursor-pointer"
                                  style={{ height: `${Math.max(heightPct, 4)}%` }}
                                  title={`${pt.label}: ${pt.value} records`}
                                />
                                {/* Bar hover tooltip */}
                                <div className="absolute bottom-full mb-1 hidden group-hover:block z-20 px-1.5 py-0.5 bg-[#0F172A] text-white text-[8px] font-mono rounded shadow-lg whitespace-nowrap pointer-events-none">
                                  {pt.label}: {pt.value}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* X-axis Bounds */}
                      <div className="flex justify-between text-[7px] text-[#94A3B8] font-mono pl-4 pt-0.5">
                        <span className="truncate max-w-[80px]">{points[0]?.label.split('-')[0]?.trim()}</span>
                        <span className="truncate max-w-[80px]">{points[points.length - 1]?.label.split('-')[1]?.trim() || points[points.length - 1]?.label}</span>
                      </div>
                    </>
                  );
                })()}

                {/* Grounded Numeric Moments Chips */}
                {activeNumericColProfile?.numeric_stats && (
                  <div className="pt-1 flex items-center justify-between text-[9px] text-[#64748B] dark:text-slate-400 border-t border-slate-100 dark:border-[#1E293B]">
                    <span>Min: <strong className="text-[#0F172A] dark:text-white">{activeNumericColProfile.numeric_stats.min}</strong></span>
                    <span>Mean: <strong className="text-[#0F172A] dark:text-white">{activeNumericColProfile.numeric_stats.mean}</strong></span>
                    <span>Median: <strong className="text-[#0F172A] dark:text-white">{activeNumericColProfile.numeric_stats.median}</strong></span>
                    <span>Max: <strong className="text-[#0F172A] dark:text-white">{activeNumericColProfile.numeric_stats.max}</strong></span>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                Insufficient data to plot histogram.
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          4. 3-COLUMN ADVANCED ANALYTICS GRID (Correlation, Categorical, Insights)
      ========================================================================= */}
      {selectedDatasetId && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5">
          {/* -------------------------------------------------------------------
              COL 1: CORRELATION HEATMAP (Numeric Features) (col-span-5)
          ------------------------------------------------------------------- */}
          <div
            id="correlation-heatmap-card"
            className="lg:col-span-5 bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-[#2563EB]" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Correlation Matrix (Numeric)</h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Pearson r</span>
            </div>

            {loadingHeatmap ? (
              <div className="h-44 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#2563EB]" />
                <span>Computing correlation coefficients...</span>
              </div>
            ) : !heatmapData?.matrix || !heatmapData?.categories || heatmapData.categories.length < 2 ? (
              <div className="h-44 flex flex-col items-center justify-center p-4 text-center rounded-xl bg-slate-50 dark:bg-[#131F3F] border border-slate-200 dark:border-[#1E293B] space-y-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Info className="w-5 h-5 text-slate-400" />
                <div className="font-semibold text-[#0F172A] dark:text-white">Insufficient Numeric Columns</div>
                <p className="text-[10px]">
                  Correlation analysis requires at least 2 numeric features. The selected dataset has {usableNumericCols.length} numeric column(s).
                </p>
              </div>
            ) : (
              /* Real Color-Coded Pearson Correlation Heatmap Table */
              <div className="space-y-2">
                <div className="overflow-x-auto">
                  <table className="w-full text-center border-collapse text-[10px]">
                    <thead>
                      <tr>
                        <th className="p-1 text-left font-semibold text-slate-500 dark:text-slate-400"></th>
                        {heatmapData.categories.map((cat, i) => (
                          <th key={i} className="p-1 font-semibold text-[#64748B] dark:text-slate-300 truncate max-w-[70px]" title={cat}>
                            {cat}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {heatmapData.categories.map((rowCat, rIdx) => (
                        <tr key={rIdx}>
                          <td className="p-1 text-right font-semibold text-[#64748B] dark:text-slate-300 truncate max-w-[75px]" title={rowCat}>
                            {rowCat}
                          </td>
                          {heatmapData.matrix[rIdx]?.map((val, cIdx) => {
                            const isSelf = rIdx === cIdx;
                            let bg = '#F1F5F9';
                            let textCol = '#0F172A';

                            if (val === null || val === undefined) {
                              bg = 'transparent';
                              textCol = '#94A3B8';
                            } else if (isSelf) {
                              bg = '#1D4ED8';
                              textCol = '#FFFFFF';
                            } else if (val > 0) {
                              const alpha = Math.min(Math.abs(val), 1);
                              bg = `rgba(37, 99, 235, ${alpha * 0.7})`;
                              textCol = alpha > 0.4 ? '#FFFFFF' : '#0F172A';
                            } else if (val < 0) {
                              const alpha = Math.min(Math.abs(val), 1);
                              bg = `rgba(239, 68, 68, ${alpha * 0.7})`;
                              textCol = alpha > 0.4 ? '#FFFFFF' : '#0F172A';
                            }

                            return (
                              <td
                                key={cIdx}
                                className="p-1"
                                title={`${rowCat} ↔ ${heatmapData.categories[cIdx]}: r = ${val !== null ? val : 'N/A'}`}
                              >
                                <div
                                  className="py-1.5 px-0.5 rounded font-bold font-mono text-[10px] transition-transform hover:scale-105"
                                  style={{ backgroundColor: bg, color: textCol }}
                                >
                                  {val !== null && val !== undefined ? val.toFixed(2) : '—'}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Scale Legend */}
                <div className="flex items-center justify-between text-[8px] font-mono text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-100 dark:border-[#1E293B]">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-xs bg-[#EF4444]"></span> -1.0 (Inverse)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-xs bg-slate-200"></span> 0.0 (None)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-xs bg-[#2563EB]"></span> +1.0 (Direct)
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* -------------------------------------------------------------------
              COL 2: CATEGORICAL FEATURE DISTRIBUTION (col-span-3)
          ------------------------------------------------------------------- */}
          <div
            id="categorical-distribution-card"
            className="lg:col-span-3 bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2 min-w-0">
                <BarChart2 className="w-3.5 h-3.5 text-[#8B5CF6] shrink-0" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Categories</h3>
              </div>

              {usableCategoricalCols.length > 0 && (
                <div className="relative shrink-0">
                  <select
                    id="categorical-col-selector"
                    value={selectedCategoricalCol}
                    onChange={(e) => setSelectedCategoricalCol(e.target.value)}
                    className="appearance-none bg-[#F8FAFC] dark:bg-[#131F3F] border border-[#CBD5E1] dark:border-[#1E293B] rounded-lg px-2 py-0.5 pr-5 text-[10px] font-bold text-[#0F172A] dark:text-white focus:outline-none cursor-pointer max-w-[100px] truncate"
                  >
                    {usableCategoricalCols.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-2.5 h-2.5 text-[#64748B] absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              )}
            </div>

            {loadingProfile ? (
              <div className="h-44 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#8B5CF6]" />
                <span>Loading categories...</span>
              </div>
            ) : !activeCategoricalColProfile?.categorical_stats?.top_values ? (
              <div className="h-44 flex flex-col items-center justify-center text-center p-3 text-xs text-slate-400">
                <Info className="w-5 h-5 mb-1 text-slate-400" />
                <span>No categorical frequencies available.</span>
              </div>
            ) : (
              /* Real Categorical Distribution Bars */
              <div className="space-y-2 py-1">
                <div className="text-[10px] text-slate-400 flex items-center justify-between">
                  <span>Feature: <strong>{activeCategoricalColProfile.name}</strong></span>
                  <span>{activeCategoricalColProfile.unique_count} unique</span>
                </div>

                <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                  {activeCategoricalColProfile.categorical_stats.top_values.slice(0, 5).map((tv, idx) => (
                    <div key={idx} className="space-y-0.5">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="font-medium text-[#0F172A] dark:text-white truncate max-w-[110px]" title={tv.value}>
                          {tv.value}
                        </span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">
                          {tv.count} ({tv.percentage}%)
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-100 dark:bg-[#1E293B] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#8B5CF6] rounded-full transition-all"
                          style={{ width: `${Math.min(Math.max(tv.percentage, 4), 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* -------------------------------------------------------------------
              COL 3: KEY INSIGHTS (AI Generated from actual data) (col-span-4)
          ------------------------------------------------------------------- */}
          <div
            id="key-insights-card"
            className="lg:col-span-4 bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
              <div className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
                <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Grounded Insights</h3>
              </div>
              <button
                type="button"
                onClick={() => navigate(`/insights?dataset_id=${selectedDatasetId}`)}
                className="text-xs font-semibold text-[#2563EB] hover:underline cursor-pointer flex items-center gap-0.5"
              >
                <span>View All</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {loadingInsights && displayInsights.length === 0 ? (
              <div className="h-44 flex items-center justify-center text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 spin mr-2 text-[#2563EB]" />
                <span>Deriving evidence-grounded insights...</span>
              </div>
            ) : displayInsights.length === 0 ? (
              <div className="h-44 flex items-center justify-center text-xs text-slate-400">
                No automated insights found.
              </div>
            ) : (
              <div className="space-y-2.5">
                {displayInsights.map((ins, i) => (
                  <div key={ins.id || i} className="flex items-start gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] dark:bg-[#131F3F] text-[#2563EB] dark:text-[#60A5FA] flex items-center justify-center shrink-0 mt-0.5">
                      {ins.type === 'missing_values' ? (
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      ) : ins.type === 'outlier' ? (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      ) : ins.type === 'concentration' ? (
                        <TrendingUp className="w-3.5 h-3.5" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-[#0F172A] dark:text-white truncate">
                        {ins.title}
                      </div>
                      <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8] leading-tight line-clamp-2">
                        {ins.statement}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          5. RECENT DATASETS IN REPOSITORY & QUICK ACTIONS
      ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5">
        {/* Recent Datasets List (col-span-6) */}
        <div className="lg:col-span-6 bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-2.5">
          <div className="flex items-center justify-between pb-1 border-b border-slate-100 dark:border-[#1E293B]">
            <div className="flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-[#2563EB]" />
              <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Recent Datasets in Workspace</h3>
            </div>
            <button
              onClick={() => navigate('/datasets')}
              className="text-xs font-semibold text-[#2563EB] hover:underline cursor-pointer flex items-center gap-0.5"
            >
              <span>View All</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {datasets.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">No datasets available.</div>
          ) : (
            <div className="space-y-2">
              {datasets.slice(0, 3).map((d) => {
                const isSelected = d.id === selectedDatasetId;
                return (
                  <div
                    key={d.id}
                    onClick={() => {
                      setSelectedDatasetId(d.id);
                      setSearchParams({ dataset_id: String(d.id) }, { replace: true });
                      localStorage.setItem('selected_dataset_id', String(d.id));
                    }}
                    className={`flex items-center justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/70 dark:bg-[#131F3F] border-[#2563EB] ring-1 ring-[#2563EB]/30'
                        : 'bg-[#F8FAFC] dark:bg-[#070D1E] border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#2563EB]/50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] dark:bg-[#1E293B] text-[#2563EB] dark:text-[#60A5FA] flex items-center justify-center shrink-0">
                        <FileSpreadsheet className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-xs text-[#0F172A] dark:text-white truncate">
                          {d.filename || d.original_filename}
                        </div>
                        <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8]">
                          {d.rows || d.row_count || 0} rows • {d.columns || d.column_count || 0} cols • {formatFileSize(d.file_size_bytes || d.file_size)}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {isSelected ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#1E6BFF] text-white">
                          Selected
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-[#1E293B] text-slate-600 dark:text-slate-300">
                          Switch
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Quick Analytical Actions (col-span-6) */}
        <div className="lg:col-span-6 bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3">
          <div className="flex items-center gap-2 pb-1 border-b border-slate-100 dark:border-[#1E293B]">
            <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
            <h3 className="text-xs font-bold text-[#0F172A] dark:text-white">Quick Actions</h3>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Action 1: Upload Dataset */}
            <button
              type="button"
              onClick={() => navigate('/upload')}
              className="p-3 bg-[#F8FAFC] dark:bg-[#070D1E] border border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#2563EB] hover:bg-white dark:hover:bg-[#131F3F] rounded-xl transition-all cursor-pointer flex items-center gap-3 text-left shadow-2xs"
            >
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] dark:bg-[#1E293B] text-[#2563EB] flex items-center justify-center shrink-0">
                <UploadCloud className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Upload CSV</div>
                <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block truncate">Ingest new dataset</span>
              </div>
            </button>

            {/* Action 2: Run AI Analysis */}
            <button
              type="button"
              onClick={() => navigate(selectedDatasetId ? `/data-analyst?dataset_id=${selectedDatasetId}` : '/data-analyst')}
              className="p-3 bg-[#F8FAFC] dark:bg-[#070D1E] border border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#9333EA] hover:bg-white dark:hover:bg-[#131F3F] rounded-xl transition-all cursor-pointer flex items-center gap-3 text-left shadow-2xs"
            >
              <div className="w-8 h-8 rounded-lg bg-[#FAF5FF] dark:bg-[#1E293B] text-[#9333EA] flex items-center justify-center shrink-0">
                <BarChart3 className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Ask AI Analyst</div>
                <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block truncate">Natural language query</span>
              </div>
            </button>

            {/* Action 3: Generate Report */}
            <button
              type="button"
              onClick={() => navigate(selectedDatasetId ? `/reports?dataset_id=${selectedDatasetId}` : '/reports')}
              className="p-3 bg-[#F8FAFC] dark:bg-[#070D1E] border border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#059669] hover:bg-white dark:hover:bg-[#131F3F] rounded-xl transition-all cursor-pointer flex items-center gap-3 text-left shadow-2xs"
            >
              <div className="w-8 h-8 rounded-lg bg-[#ECFDF5] dark:bg-[#1E293B] text-[#059669] flex items-center justify-center shrink-0">
                <FileText className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Executive Report</div>
                <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block truncate">Export structured summary</span>
              </div>
            </button>

            {/* Action 4: Data Quality & Cleaning */}
            <button
              type="button"
              onClick={() => navigate(selectedDatasetId ? `/data-quality?dataset_id=${selectedDatasetId}` : '/data-quality')}
              className="p-3 bg-[#F8FAFC] dark:bg-[#070D1E] border border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#D97706] hover:bg-white dark:hover:bg-[#131F3F] rounded-xl transition-all cursor-pointer flex items-center gap-3 text-left shadow-2xs"
            >
              <div className="w-8 h-8 rounded-lg bg-[#FFFBEB] dark:bg-[#1E293B] text-[#D97706] flex items-center justify-center shrink-0">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#0F172A] dark:text-white truncate">Data Quality</div>
                <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block truncate">Inspect nulls & validity</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
