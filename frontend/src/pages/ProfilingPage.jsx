import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  FileSearch,
  Database,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  Search,
  Hash,
  Columns,
  Layers,
  Calendar,
  Sparkles,
  ShieldCheck,
  Activity,
  Plus,
  ArrowRight,
  Filter,
  Check,
  CheckSquare,
  Square,
  GitMerge,
  BarChart3,
  Table,
  SlidersHorizontal,
  Info,
  ShieldAlert,
  X,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { extractErrorMessage } from '../services/api';

export const ProfilingPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Dataset repository & selection state
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  // Analysis result state
  const [multiResult, setMultiResult] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');

  // Active view tab state: 'combined' | 'comparison' | 'individual' | 'relationships'
  const [activeTab, setActiveTab] = useState('combined');
  const [selectedIndividualId, setSelectedIndividualId] = useState(null);

  // Column search & filters inside individual profile
  const [columnSearch, setColumnSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Comparison matrix search
  const [comparisonSearch, setComparisonSearch] = useState('');
  const [comparisonFilter, setComparisonFilter] = useState('ALL'); // 'ALL' | 'SHARED' | 'UNIQUE' | 'MISMATCH'

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };

  // 1. Initial Load: Fetch user datasets and parse query parameters
  useEffect(() => {
    const fetchDatasets = async () => {
      setLoadingDatasets(true);
      setError('');
      try {
        const data = await datasetService.getDatasets();
        const list = data || [];
        setDatasets(list);

        // Check query parameters: dataset_ids (comma separated) or single dataset_id / id or saved ID
        const rawIds = searchParams.get('dataset_ids');
        const singleId = searchParams.get('dataset_id') || searchParams.get('id');
        const savedId = localStorage.getItem('selected_dataset_id');

        let initialIds = [];
        if (rawIds) {
          initialIds = rawIds
            .split(',')
            .map((s) => Number(s.trim()))
            .filter((n) => !isNaN(n) && list.some((d) => d.id === n));
        } else if (singleId) {
          const num = Number(singleId);
          if (!isNaN(num) && list.some((d) => d.id === num)) {
            initialIds = [num];
          }
        } else if (savedId) {
          const num = Number(savedId);
          if (!isNaN(num) && list.some((d) => d.id === num)) {
            initialIds = [num];
          }
        }

        if (initialIds.length > 0) {
          setSelectedDatasetIds(initialIds);
          runAnalysis(initialIds);
        } else if (list.length > 0) {
          // Default: select the most recently uploaded dataset
          const defaultId = list[0].id;
          setSelectedDatasetIds([defaultId]);
          runAnalysis([defaultId]);
        }
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingDatasets(false);
      }
    };

    fetchDatasets();
  }, []);

  // 2. Run multi-dataset analysis for a list of dataset IDs
  const runAnalysis = async (ids) => {
    if (!ids || ids.length === 0) {
      setMultiResult(null);
      return;
    }

    setIsAnalyzing(true);
    setError('');

    // Sync URL search params
    if (ids.length === 1) {
      setSearchParams({ dataset_id: ids[0] }, { replace: true });
      localStorage.setItem('selected_dataset_id', String(ids[0]));
    } else {
      setSearchParams({ dataset_ids: ids.join(',') }, { replace: true });
    }

    try {
      const resp = await datasetService.analyzeMultiDatasets(ids, 'all');
      setMultiResult(resp);

      // Choose appropriate default tab
      if (ids.length >= 2) {
        setActiveTab('combined');
      } else {
        setActiveTab('individual');
      }

      // Default the individual profile viewer to the first successful dataset
      if (resp?.individual_profiles && Object.keys(resp.individual_profiles).length > 0) {
        const keys = Object.keys(resp.individual_profiles);
        const firstSuccessId = Number(keys[0]);
        setSelectedIndividualId((prev) => {
          if (prev && (resp.individual_profiles[prev] || resp.individual_profiles[String(prev)])) {
            return prev;
          }
          return firstSuccessId;
        });
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Selection handlers
  const handleToggleDataset = (id) => {
    const isSelected = selectedDatasetIds.includes(id);
    let next;
    if (isSelected) {
      next = selectedDatasetIds.filter((dId) => dId !== id);
    } else {
      next = [...selectedDatasetIds, id];
    }
    setSelectedDatasetIds(next);
  };

  const handleSelectAll = () => {
    const allIds = datasets.map((d) => d.id);
    setSelectedDatasetIds(allIds);
  };

  const handleClearSelection = () => {
    setSelectedDatasetIds([]);
    setMultiResult(null);
    setSearchParams({});
  };

  // Quality badge styling
  const getQualityBadge = (status) => {
    const s = (status || '').toLowerCase();
    if (s.includes('excellent')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (s.includes('good')) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (s.includes('moderate')) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-red-50 text-red-700 border-red-200';
  };

  const getSemanticBadge = (type) => {
    switch (type) {
      case 'NUMERIC': return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'CATEGORICAL': return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'DATETIME': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'BOOLEAN': return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'TEXT': return 'bg-amber-50 text-amber-700 border-amber-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  // Active individual profile
  const activeProfile = useMemo(() => {
    if (!multiResult?.individual_profiles) return null;
    const profiles = multiResult.individual_profiles;
    if (selectedIndividualId != null) {
      if (profiles[selectedIndividualId]) return profiles[selectedIndividualId];
      if (profiles[String(selectedIndividualId)]) return profiles[String(selectedIndividualId)];
      if (profiles[Number(selectedIndividualId)]) return profiles[Number(selectedIndividualId)];
    }
    const keys = Object.keys(profiles);
    if (keys.length > 0) {
      return profiles[keys[0]];
    }
    return null;
  }, [multiResult, selectedIndividualId]);

  // Filtered columns for active individual profile
  const filteredColumns = useMemo(() => {
    if (!activeProfile?.columns) return [];
    return activeProfile.columns.filter((col) => {
      const matchesSearch = col.name.toLowerCase().includes(columnSearch.toLowerCase());
      if (!matchesSearch) return false;

      if (typeFilter === 'NUMERIC') return col.semantic_type === 'NUMERIC';
      if (typeFilter === 'CATEGORICAL') return col.semantic_type === 'CATEGORICAL' || col.semantic_type === 'TEXT';
      if (typeFilter === 'MISSING') return col.missing_count > 0;
      return true;
    });
  }, [activeProfile, columnSearch, typeFilter]);

  // Filtered column comparison matrix
  const filteredComparisonMatrix = useMemo(() => {
    if (!multiResult?.comparison?.column_matrix) return [];
    return multiResult.comparison.column_matrix.filter((item) => {
      const matchesSearch =
        item.column_name.toLowerCase().includes(comparisonSearch.toLowerCase()) ||
        item.normalized_name.includes(comparisonSearch.toLowerCase());
      if (!matchesSearch) return false;

      if (comparisonFilter === 'SHARED') return item.is_shared;
      if (comparisonFilter === 'UNIQUE') return !item.is_shared;
      if (comparisonFilter === 'MISMATCH') return !item.type_compatible;
      return true;
    });
  }, [multiResult, comparisonSearch, comparisonFilter]);

  const selectedDatasetsCount = selectedDatasetIds.length;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Multi-File Picker Controls */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] flex items-center gap-2.5">
            <span>Data Profiling & Multi-Dataset Analysis</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#2563EB]/10 text-[#2563EB] border border-[#2563EB]/20">
              Multi-Dataset Ready
            </span>
          </h1>
          <p className="text-xs text-[#64748B] mt-1">
            Analyze multiple datasets together, discover cross-file relationships, compare schemas, and explore individual profiles.
          </p>
        </div>

        {/* Selected count and Quick Actions */}
        {!loadingDatasets && datasets.length > 0 && (
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-slate-100 text-[#0F172A] border border-slate-200">
              {selectedDatasetsCount} of {datasets.length} selected
            </span>

            <button
              onClick={() => runAnalysis(selectedDatasetIds)}
              disabled={selectedDatasetsCount === 0 || isAnalyzing}
              className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
              <span>{isAnalyzing ? 'Analyzing...' : 'Run Analysis'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Dataset Multi-Select Selector Card */}
      {!loadingDatasets && datasets.length > 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#F1F5F9]">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-[#2563EB]" />
              <span className="text-xs font-bold text-[#0F172A]">Select Datasets to Analyze</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSelectAll}
                className="text-[11px] font-semibold text-[#2563EB] hover:underline cursor-pointer"
              >
                Select All
              </button>
              <span className="text-gray-300">|</span>
              <button
                onClick={handleClearSelection}
                className="text-[11px] font-semibold text-[#64748B] hover:text-[#0F172A] cursor-pointer"
              >
                Clear Selection
              </button>
            </div>
          </div>

          {/* Dataset Pill Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
            {datasets.map((d) => {
              const isSelected = selectedDatasetIds.includes(d.id);
              const fname = d.original_filename || d.filename;
              const ftype = (d.file_type || 'CSV').toUpperCase();
              const rowCount = d.row_count ?? d.rows ?? 0;
              const colCount = d.column_count ?? d.columns ?? 0;

              return (
                <div
                  key={d.id}
                  onClick={() => handleToggleDataset(d.id)}
                  className={`flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer select-none ${
                    isSelected
                      ? 'bg-[#EFF6FF] border-[#2563EB] shadow-2xs'
                      : 'bg-white border-[#E2E8F0] hover:border-slate-300 hover:bg-[#F8FAFC]'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={isSelected ? 'text-[#2563EB]' : 'text-slate-400'}>
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-[#2563EB]" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div
                        className={`text-xs font-semibold truncate ${
                          isSelected ? 'text-[#1D4ED8]' : 'text-[#0F172A]'
                        }`}
                        title={fname}
                      >
                        {fname}
                      </div>
                      <div className="text-[10px] text-[#64748B] mt-0.5">
                        {rowCount.toLocaleString()} rows · {colCount} cols
                      </div>
                    </div>
                  </div>

                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase shrink-0 ${
                      ftype === 'CSV'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}
                  >
                    {ftype}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error & Partial Success Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span className="font-medium">{error}</span>
          </div>
          <button
            onClick={() => runAnalysis(selectedDatasetIds)}
            className="text-xs font-semibold text-red-700 underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Partial Failure Notice if any dataset failed in batch */}
      {multiResult?.status === 'partial' && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-2 shadow-xs">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>Partial Analysis Notice ({multiResult.total_successful} of {multiResult.total_selected} datasets succeeded)</span>
          </div>
          <ul className="list-disc pl-5 space-y-1 text-[11px] text-amber-700">
            {multiResult.errors.map((err, idx) => (
              <li key={idx}>
                <strong>{err.dataset_name || `Dataset #${err.dataset_id}`}:</strong> {err.error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Loading State */}
      {isAnalyzing && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-16 text-center shadow-xs">
          <RefreshCw className="w-8 h-8 text-[#2563EB] animate-spin mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-[#0F172A]">Analyzing Selected Datasets...</h3>
          <p className="text-xs text-[#64748B] mt-1">
            Profiling data distributions, comparing schema attributes, and evaluating relationships
          </p>
        </div>
      )}

      {/* Empty State: No Datasets Uploaded */}
      {!loadingDatasets && datasets.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-14 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center mx-auto mb-4">
            <Database className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-[#0F172A]">No Datasets Available</h3>
          <p className="text-xs text-[#64748B] max-w-md mx-auto mt-2 leading-relaxed">
            Upload your CSV or Excel files to run individual and combined multi-dataset profiling.
          </p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Upload Dataset</span>
          </button>
        </div>
      )}

      {/* Empty State: Datasets exist but none selected */}
      {!loadingDatasets && datasets.length > 0 && selectedDatasetsCount === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-14 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center mx-auto mb-4">
            <FileSearch className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-[#0F172A]">No datasets selected</h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto mt-2 leading-relaxed">
            Select one or more datasets from the grid above to profile distributions and discover cross-dataset relationships.
          </p>
          <button
            onClick={handleSelectAll}
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-xs font-semibold rounded-xl shadow-xs cursor-pointer"
          >
            <span>Select All ({datasets.length})</span>
          </button>
        </div>
      )}

      {/* ANALYSIS WORKSPACE (Rendered when results are available) */}
      {!isAnalyzing && multiResult && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Top Mode Navigation Tabs */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-1.5 shadow-xs flex items-center gap-1 overflow-x-auto">
            {/* Combined Overview Tab (Available when 2+ datasets) */}
            {selectedDatasetsCount >= 2 && (
              <button
                onClick={() => setActiveTab('combined')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'combined'
                    ? 'bg-[#2563EB] text-white shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-50'
                }`}
              >
                <Layers className="w-4 h-4" />
                <span>Combined Overview</span>
              </button>
            )}

            {/* Dataset Comparison Tab (Available when 2+ datasets) */}
            {selectedDatasetsCount >= 2 && (
              <button
                onClick={() => setActiveTab('comparison')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'comparison'
                    ? 'bg-[#2563EB] text-white shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-50'
                }`}
              >
                <Table className="w-4 h-4" />
                <span>Schema Comparison</span>
                {multiResult.comparison?.shared_columns?.length > 0 && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                      activeTab === 'comparison' ? 'bg-white/20 text-white' : 'bg-blue-100 text-[#2563EB]'
                    }`}
                  >
                    {multiResult.comparison.shared_columns.length} shared
                  </span>
                )}
              </button>
            )}

            {/* Cross-Dataset Relationships Tab (Available when 2+ datasets) */}
            {selectedDatasetsCount >= 2 && (
              <button
                onClick={() => setActiveTab('relationships')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'relationships'
                    ? 'bg-[#2563EB] text-white shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-50'
                }`}
              >
                <GitMerge className="w-4 h-4" />
                <span>Relationships</span>
                {multiResult.relationships?.length > 0 && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                      activeTab === 'relationships' ? 'bg-white/20 text-white' : 'bg-emerald-100 text-emerald-700'
                    }`}
                  >
                    {multiResult.relationships.length} detected
                  </span>
                )}
              </button>
            )}

            {/* Individual Profiles Tab */}
            <button
              onClick={() => setActiveTab('individual')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'individual'
                  ? 'bg-[#2563EB] text-white shadow-xs'
                  : 'text-[#64748B] hover:text-[#0F172A] hover:bg-slate-50'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Individual Profiles</span>
            </button>
          </div>

          {/* ========================================================= */}
          {/* TAB 1: COMBINED OVERVIEW                                 */}
          {/* ========================================================= */}
          {activeTab === 'combined' && multiResult.combined_overview && (
            <div className="space-y-6">
              {/* Aggregated KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                {/* Total Datasets */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                    <span>Analyzed Datasets</span>
                    <Database className="w-3.5 h-3.5 text-[#2563EB]" />
                  </div>
                  <div className="mt-2 text-xl font-bold text-[#0F172A]">
                    {multiResult.combined_overview.total_datasets}
                  </div>
                  <div className="mt-1 text-[10px] text-[#2563EB] font-medium">All active files</div>
                </div>

                {/* Total Rows */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                    <span>Total Rows</span>
                    <Hash className="w-3.5 h-3.5 text-[#2563EB]" />
                  </div>
                  <div className="mt-2 text-xl font-bold text-[#0F172A]">
                    {multiResult.combined_overview.total_rows.toLocaleString()}
                  </div>
                  <div className="mt-1 text-[10px] text-[#64748B]">Across all datasets</div>
                </div>

                {/* Total Columns */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                    <span>Total Columns</span>
                    <Columns className="w-3.5 h-3.5 text-[#2563EB]" />
                  </div>
                  <div className="mt-2 text-xl font-bold text-[#0F172A]">
                    {multiResult.combined_overview.total_columns}
                  </div>
                  <div className="mt-1 text-[10px] text-[#64748B]">Combined attributes</div>
                </div>

                {/* Combined Missing Values */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                    <span>Missing Values</span>
                    <AlertTriangle
                      className={`w-3.5 h-3.5 ${
                        multiResult.combined_overview.total_missing_cells > 0 ? 'text-amber-500' : 'text-emerald-500'
                      }`}
                    />
                  </div>
                  <div className="mt-2 text-xl font-bold text-[#0F172A]">
                    {multiResult.combined_overview.total_missing_cells.toLocaleString()}
                  </div>
                  <div className="mt-1 text-[10px] font-semibold">
                    <span
                      className={
                        multiResult.combined_overview.total_missing_cells > 0
                          ? 'text-amber-600'
                          : 'text-emerald-600'
                      }
                    >
                      {multiResult.combined_overview.overall_missing_percentage}% of all cells
                    </span>
                  </div>
                </div>

                {/* Combined Duplicates */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                    <span>Duplicate Rows</span>
                    <Layers
                      className={`w-3.5 h-3.5 ${
                        multiResult.combined_overview.total_duplicate_rows > 0 ? 'text-amber-500' : 'text-emerald-500'
                      }`}
                    />
                  </div>
                  <div className="mt-2 text-xl font-bold text-[#0F172A]">
                    {multiResult.combined_overview.total_duplicate_rows.toLocaleString()}
                  </div>
                  <div className="mt-1 text-[10px] font-semibold">
                    <span
                      className={
                        multiResult.combined_overview.total_duplicate_rows > 0
                          ? 'text-amber-600'
                          : 'text-emerald-600'
                      }
                    >
                      {multiResult.combined_overview.overall_duplicate_percentage}% duplicate
                    </span>
                  </div>
                </div>
              </div>

              {/* Cross-Dataset Insights Card */}
              {multiResult.cross_dataset_insights?.length > 0 && (
                <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-2xl p-5 shadow-xs space-y-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#2563EB]" />
                    <h3 className="text-xs font-bold text-[#1D4ED8] uppercase tracking-wider">
                      Cross-Dataset Verified Insights
                    </h3>
                  </div>
                  <div className="space-y-2">
                    {multiResult.cross_dataset_insights.map((insight, idx) => (
                      <div key={idx} className="flex items-start gap-2.5 text-xs text-[#1E3A8A]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#2563EB] shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{insight}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Side-by-Side Dataset Comparison Table */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs">
                <div className="px-6 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[#2563EB]" />
                    <h3 className="text-sm font-bold text-[#0F172A]">Per-Dataset Structural Breakdown</h3>
                  </div>
                  <span className="text-xs text-[#64748B]">
                    Click any dataset to inspect its full profile
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-6 py-3.5">Dataset Name</th>
                        <th className="px-4 py-3.5">Format</th>
                        <th className="px-4 py-3.5 text-right">Rows</th>
                        <th className="px-4 py-3.5 text-right">Cols</th>
                        <th className="px-4 py-3.5 text-right">Size</th>
                        <th className="px-4 py-3.5 text-right">Missing %</th>
                        <th className="px-4 py-3.5 text-right">Duplicates</th>
                        <th className="px-4 py-3.5 text-center">Quality Score</th>
                        <th className="px-6 py-3.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0] text-[#0F172A]">
                      {multiResult.combined_overview.dataset_summaries.map((ds) => (
                        <tr
                          key={ds.dataset_id}
                          className="hover:bg-[#F8FAFC] transition-colors cursor-pointer group"
                          onClick={() => {
                            setSelectedIndividualId(ds.dataset_id);
                            setActiveTab('individual');
                          }}
                        >
                          <td className="px-6 py-3.5 font-semibold text-[#0F172A] group-hover:text-[#2563EB] flex items-center gap-2">
                            <span>{ds.name}</span>
                          </td>
                          <td className="px-4 py-3.5">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border">
                              {ds.file_type}
                            </span>
                          </td>
                          <td className="px-4 py-3.5 text-right font-medium">{ds.rows.toLocaleString()}</td>
                          <td className="px-4 py-3.5 text-right font-medium">{ds.columns}</td>
                          <td className="px-4 py-3.5 text-right text-[#64748B]">{formatFileSize(ds.file_size_bytes)}</td>
                          <td className="px-4 py-3.5 text-right font-semibold">
                            <span className={ds.missing_percentage > 0 ? 'text-amber-600' : 'text-emerald-600'}>
                              {ds.missing_percentage}%
                            </span>
                          </td>
                          <td className="px-4 py-3.5 text-right font-semibold">
                            <span className={ds.duplicate_rows > 0 ? 'text-amber-600' : 'text-emerald-600'}>
                              {ds.duplicate_rows.toLocaleString()}
                            </span>
                          </td>
                          <td className="px-4 py-3.5 text-center">
                            <span
                              className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${getQualityBadge(
                                ds.health_status
                              )}`}
                            >
                              {ds.health_score ?? 'N/A'}/100
                            </span>
                          </td>
                          <td className="px-6 py-3.5 text-right">
                            <span className="text-[#2563EB] font-semibold text-xs flex items-center justify-end gap-1 group-hover:translate-x-0.5 transition-transform">
                              <span>Profile</span>
                              <ArrowRight className="w-3 h-3" />
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 2: SCHEMA COMPARISON MATRIX                          */}
          {/* ========================================================= */}
          {activeTab === 'comparison' && multiResult.comparison && (
            <div className="space-y-6">
              {/* Comparability Summary Banner */}
              <div
                className={`p-4 rounded-2xl border text-xs flex items-start gap-3 shadow-xs ${
                  multiResult.comparison.is_comparable
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-amber-50 border-amber-200 text-amber-800'
                }`}
              >
                {multiResult.comparison.is_comparable ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                )}
                <div className="space-y-1">
                  <div className="font-bold text-sm">
                    {multiResult.comparison.is_comparable
                      ? 'Schema Alignment Detected'
                      : 'Distinct Schemas Detected'}
                  </div>
                  <p className="leading-relaxed">{multiResult.comparison.comparability_notes}</p>
                </div>
              </div>

              {/* Shared vs Unique Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="text-[11px] font-medium text-[#64748B]">Shared Columns</div>
                  <div className="mt-1 text-2xl font-bold text-[#2563EB]">
                    {multiResult.comparison.shared_columns.length}
                  </div>
                  <div className="mt-1 text-[10px] text-[#64748B]">
                    Present across 2+ datasets
                  </div>
                </div>

                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="text-[11px] font-medium text-[#64748B]">Universal Columns</div>
                  <div className="mt-1 text-2xl font-bold text-emerald-600">
                    {multiResult.comparison.shared_across_all_columns.length}
                  </div>
                  <div className="mt-1 text-[10px] text-[#64748B]">
                    Present in all selected datasets
                  </div>
                </div>

                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                  <div className="text-[11px] font-medium text-[#64748B]">Type Conflicts</div>
                  <div
                    className={`mt-1 text-2xl font-bold ${
                      multiResult.comparison.type_mismatches?.length > 0
                        ? 'text-amber-600'
                        : 'text-emerald-600'
                    }`}
                  >
                    {multiResult.comparison.type_mismatches?.length || 0}
                  </div>
                  <div className="mt-1 text-[10px] text-[#64748B]">
                    {multiResult.comparison.type_mismatches?.length > 0
                      ? 'Conflicting data types detected'
                      : 'All shared column types compatible'}
                  </div>
                </div>
              </div>

              {/* Column Comparison Matrix Table */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs space-y-4 p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-[#0F172A]">Cross-Dataset Attribute Matrix</h3>
                    <p className="text-[11px] text-[#64748B] mt-0.5">
                      Compares presence, data types, null counts, and uniqueness across all datasets.
                    </p>
                  </div>

                  {/* Filter and Search Bar */}
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                      <input
                        type="text"
                        value={comparisonSearch}
                        onChange={(e) => setComparisonSearch(e.target.value)}
                        placeholder="Search column..."
                        className="pl-8 pr-3 py-1.5 text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                      />
                    </div>

                    <select
                      value={comparisonFilter}
                      onChange={(e) => setComparisonFilter(e.target.value)}
                      className="px-3 py-1.5 text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl font-semibold text-[#0F172A] focus:outline-none cursor-pointer"
                    >
                      <option value="ALL">All Columns</option>
                      <option value="SHARED">Shared Only</option>
                      <option value="UNIQUE">Unique Only</option>
                      <option value="MISMATCH">Type Mismatches</option>
                    </select>
                  </div>
                </div>

                <div className="overflow-x-auto border border-[#E2E8F0] rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Column Name</th>
                        <th className="px-4 py-3">Shared Status</th>
                        <th className="px-4 py-3">Type Compatibility</th>
                        <th className="px-4 py-3">Dataset Breakdown (Types & Nulls)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0] text-[#0F172A]">
                      {filteredComparisonMatrix.length === 0 ? (
                        <tr>
                          <td colSpan="4" className="px-4 py-8 text-center text-xs text-[#64748B]">
                            No columns matching the selected filter.
                          </td>
                        </tr>
                      ) : (
                        filteredComparisonMatrix.map((col) => (
                          <tr key={col.column_name} className="hover:bg-[#F8FAFC] transition-colors">
                            <td className="px-4 py-3 font-semibold text-[#0F172A]">
                              <span>{col.column_name}</span>
                            </td>
                            <td className="px-4 py-3">
                              {col.is_shared_across_all ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  All Datasets
                                </span>
                              ) : col.is_shared ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                                  Shared ({col.present_in_dataset_ids.length})
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-50 text-slate-600 border border-slate-200">
                                  Unique to 1 dataset
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {col.type_compatible ? (
                                <span className="text-[10px] font-semibold text-emerald-700 flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                  <span>Compatible</span>
                                </span>
                              ) : (
                                <span
                                  className="text-[10px] font-semibold text-amber-700 flex items-center gap-1 cursor-help"
                                  title={col.type_mismatch_warning}
                                >
                                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                                  <span>Type Mismatch</span>
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-2">
                                {Object.entries(col.dataset_details).map(([dsName, detail]) => (
                                  <div
                                    key={dsName}
                                    className="p-1.5 px-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px]"
                                  >
                                    <span className="font-semibold text-slate-800">{dsName}: </span>
                                    <span className="font-mono text-[#2563EB]">{detail.data_type}</span>
                                    <span className="text-slate-400"> · </span>
                                    <span
                                      className={
                                        detail.missing_percentage > 0 ? 'text-amber-600' : 'text-slate-500'
                                      }
                                    >
                                      {detail.missing_percentage}% null
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 3: CROSS-DATASET RELATIONSHIPS                       */}
          {/* ========================================================= */}
          {activeTab === 'relationships' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                    <GitMerge className="w-4 h-4 text-[#2563EB]" />
                    <span>Discovered Relational Keys & Foreign Key Links</span>
                  </h3>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Evaluated from actual value overlap, uniqueness, and normalized column identities.
                  </p>
                </div>
                <button
                  onClick={() => navigate('/data-cleaning')}
                  className="px-3.5 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Join Datasets in Cleaning</span>
                </button>
              </div>

              {(!multiResult.relationships || multiResult.relationships.length === 0) ? (
                <div className="bg-white border border-[#E2E8F0] rounded-2xl p-12 text-center shadow-xs">
                  <GitMerge className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                  <h4 className="text-sm font-bold text-[#0F172A]">No Relational Links Detected</h4>
                  <p className="text-xs text-[#64748B] max-w-md mx-auto mt-1 leading-relaxed">
                    Scan complete: No strong column relationships detected among the selected datasets based on matching values and primary/foreign key attributes.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {multiResult.relationships.map((rel, idx) => {
                    const isM2M = rel.cardinality_symbol === 'M:N';
                    const is11 = rel.cardinality_symbol === '1:1';
                    const is1N = rel.cardinality_symbol === '1:N';

                    return (
                      <div
                        key={idx}
                        className="bg-white border border-[#E2E8F0] hover:border-[#2563EB] rounded-2xl p-5 shadow-xs transition-all space-y-3"
                      >
                        <div className="flex items-center justify-between pb-2 border-b border-[#F1F5F9]">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                is11
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : is1N
                                  ? 'bg-blue-50 text-blue-700 border-blue-200'
                                  : isM2M
                                  ? 'bg-red-50 text-red-700 border-red-200'
                                  : 'bg-purple-50 text-purple-700 border-purple-200'
                              }`}
                            >
                              {rel.cardinality_symbol} · {rel.relationship_type}
                            </span>
                            {rel.is_candidate && (
                              <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                                Candidate Match
                              </span>
                            )}
                          </div>
                          <span className="text-xs font-bold text-[#2563EB]">
                            {(rel.confidence * 100).toFixed(0)}% Confidence
                          </span>
                        </div>

                        {/* Visual Source ↔ Target Diagram */}
                        <div className="grid grid-cols-5 items-center gap-2 py-2">
                          <div className="col-span-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                            <div className="text-[10px] text-[#64748B] truncate font-medium">
                              {rel.source_dataset}
                            </div>
                            <div className="text-xs font-bold text-[#0F172A] truncate mt-0.5">
                              {rel.source_column}
                            </div>
                            <div className="text-[9px] text-[#64748B] mt-0.5">
                              {rel.source_unique ? 'Unique (PK)' : 'Repeated (FK)'}
                            </div>
                          </div>

                          <div className="flex flex-col items-center justify-center text-[#2563EB]">
                            <GitMerge className="w-4 h-4" />
                            <span className="text-[9px] font-mono mt-0.5">{rel.cardinality_symbol}</span>
                          </div>

                          <div className="col-span-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                            <div className="text-[10px] text-[#64748B] truncate font-medium">
                              {rel.target_dataset}
                            </div>
                            <div className="text-xs font-bold text-[#0F172A] truncate mt-0.5">
                              {rel.target_column}
                            </div>
                            <div className="text-[9px] text-[#64748B] mt-0.5">
                              {rel.target_unique ? 'Unique (PK)' : 'Repeated (FK)'}
                            </div>
                          </div>
                        </div>

                        {/* Cardinality explanation */}
                        <p className="text-xs text-[#475569] leading-relaxed bg-[#F8FAFC] p-2.5 rounded-xl border border-slate-100">
                          {rel.cardinality_explanation}
                        </p>

                        {/* Join Safety Status */}
                        <div className="flex items-center justify-between pt-1 text-[11px]">
                          <span className="text-[#64748B]">
                            {rel.matching_values_count.toLocaleString()} matching keys ({rel.overlap_score}% overlap)
                          </span>
                          {rel.safe_for_join ? (
                            <span className="text-emerald-700 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Safe to Join</span>
                            </span>
                          ) : (
                            <span className="text-red-600 font-semibold flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              <span>Row Explosion Risk</span>
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ========================================================= */}
          {/* TAB 4: INDIVIDUAL DATASET PROFILES                       */}
          {/* ========================================================= */}
          {activeTab === 'individual' && (
            <div className="space-y-6">
              {/* Individual Dataset Switcher Sub-Tabs */}
              {Object.keys(multiResult.individual_profiles || {}).length > 1 && (
                <div className="flex items-center gap-2 overflow-x-auto pb-1">
                  <span className="text-xs font-semibold text-[#64748B] mr-1">Switch Dataset:</span>
                  {Object.entries(multiResult.individual_profiles).map(([dsIdStr, prof]) => {
                    const dsId = Number(dsIdStr);
                    const isSelected = selectedIndividualId === dsId;
                    return (
                      <button
                        key={dsId}
                        onClick={() => setSelectedIndividualId(dsId)}
                        className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer flex items-center gap-2 border ${
                          isSelected
                            ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-2xs'
                            : 'bg-white text-[#0F172A] border-[#E2E8F0] hover:bg-[#F8FAFC]'
                        }`}
                      >
                        <Database className="w-3.5 h-3.5" />
                        <span>{prof.dataset_info.name}</span>
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                            isSelected ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {prof.dataset_info.rows.toLocaleString()} rows
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Individual Profile Detailed Content */}
              {activeProfile ? (
                <div className="space-y-6">
                  {/* KPI Cards for the active individual dataset */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                    {/* Rows */}
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                      <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                        <span>Total Rows</span>
                        <Hash className="w-3.5 h-3.5 text-[#2563EB]" />
                      </div>
                      <div className="mt-2 text-xl font-bold text-[#0F172A]">
                        {activeProfile.dataset_info.rows.toLocaleString()}
                      </div>
                      <div className="mt-1 text-[10px] text-[#64748B]">Observed records</div>
                    </div>

                    {/* Columns */}
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                      <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                        <span>Columns</span>
                        <Columns className="w-3.5 h-3.5 text-[#2563EB]" />
                      </div>
                      <div className="mt-2 text-xl font-bold text-[#0F172A]">
                        {activeProfile.dataset_info.columns}
                      </div>
                      <div className="mt-1 text-[10px] text-[#64748B]">Features / attributes</div>
                    </div>

                    {/* Missing Cells */}
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                      <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                        <span>Missing Values</span>
                        <AlertTriangle
                          className={`w-3.5 h-3.5 ${
                            activeProfile.quality_summary.total_missing_cells > 0
                              ? 'text-amber-500'
                              : 'text-emerald-500'
                          }`}
                        />
                      </div>
                      <div className="mt-2 text-xl font-bold text-[#0F172A]">
                        {activeProfile.quality_summary.total_missing_cells.toLocaleString()}
                      </div>
                      <div className="mt-1 text-[10px] font-semibold">
                        <span
                          className={
                            activeProfile.quality_summary.total_missing_cells > 0
                              ? 'text-amber-600'
                              : 'text-emerald-600'
                          }
                        >
                          {activeProfile.quality_summary.missing_percentage}% of cells
                        </span>
                      </div>
                    </div>

                    {/* Duplicate Rows */}
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
                      <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                        <span>Duplicate Rows</span>
                        <Layers
                          className={`w-3.5 h-3.5 ${
                            activeProfile.quality_summary.duplicate_rows > 0
                              ? 'text-amber-500'
                              : 'text-emerald-500'
                          }`}
                        />
                      </div>
                      <div className="mt-2 text-xl font-bold text-[#0F172A]">
                        {activeProfile.quality_summary.duplicate_rows.toLocaleString()}
                      </div>
                      <div className="mt-1 text-[10px] font-semibold">
                        <span
                          className={
                            activeProfile.quality_summary.duplicate_rows > 0
                              ? 'text-amber-600'
                              : 'text-emerald-600'
                          }
                        >
                          {activeProfile.quality_summary.duplicate_percentage}% duplicate
                        </span>
                      </div>
                    </div>

                    {/* Health Score */}
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs col-span-2 sm:col-span-1">
                      <div className="flex items-center justify-between text-[#64748B] text-[11px] font-medium">
                        <span>Quality Status</span>
                        <ShieldCheck className="w-3.5 h-3.5 text-[#16A34A]" />
                      </div>
                      <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-xl font-bold text-[#0F172A]">
                          {activeProfile.quality_summary.health_score}
                        </span>
                        <span className="text-xs text-[#94A3B8]">/ 100</span>
                      </div>
                      <div className="mt-1">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getQualityBadge(
                            activeProfile.quality_summary.health_status
                          )}`}
                        >
                          {activeProfile.quality_summary.health_status}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Metadata bar */}
                  <div className="bg-white border border-[#E2E8F0] rounded-xl px-5 py-3 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs text-[#64748B]">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-[#0F172A]">{activeProfile.dataset_info.name}</span>
                      <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-[10px] font-semibold">
                        {activeProfile.dataset_info.file_type}
                      </span>
                      <span>•</span>
                      <span>{formatFileSize(activeProfile.dataset_info.file_size_bytes)}</span>
                      <span>•</span>
                      <span>{activeProfile.dataset_info.total_cells.toLocaleString()} total cells</span>
                    </div>
                    <div>
                      <span>Uploaded: </span>
                      <span className="font-medium text-[#0F172A]">
                        {formatDate(activeProfile.dataset_info.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Column Profiling Breakdown */}
                  <div className="space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <h2 className="text-sm font-bold text-[#0F172A]">Column Attribute Profiles</h2>
                        <p className="text-xs text-[#64748B] mt-0.5">
                          Statistical distributions, semantic data types, and value frequency rankings.
                        </p>
                      </div>

                      {/* Search & Filter Controls */}
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                          <input
                            type="text"
                            value={columnSearch}
                            onChange={(e) => setColumnSearch(e.target.value)}
                            placeholder="Filter columns..."
                            className="pl-8 pr-3 py-1.5 text-xs bg-white border border-[#CBD5E1] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                          />
                        </div>

                        <select
                          value={typeFilter}
                          onChange={(e) => setTypeFilter(e.target.value)}
                          className="px-3 py-1.5 text-xs bg-white border border-[#CBD5E1] rounded-xl font-semibold text-[#0F172A] focus:outline-none cursor-pointer"
                        >
                          <option value="ALL">All Types</option>
                          <option value="NUMERIC">Numeric</option>
                          <option value="CATEGORICAL">Categorical</option>
                          <option value="MISSING">With Missing</option>
                        </select>
                      </div>
                    </div>

                    {/* Columns List */}
                    <div className="space-y-3">
                      {filteredColumns.map((col) => (
                        <div
                          key={col.name}
                          className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-4"
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#F1F5F9] pb-3">
                            <div className="flex items-center gap-2.5">
                              <span className="font-bold text-sm text-[#0F172A]">{col.name}</span>
                              <span
                                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getSemanticBadge(
                                  col.semantic_type
                                )}`}
                              >
                                {col.semantic_type}
                              </span>
                              <span className="text-[10px] font-mono text-[#64748B]">
                                ({col.data_type})
                              </span>
                            </div>

                            <div className="flex items-center gap-4 text-xs text-[#64748B]">
                              <span>
                                Non-null: <strong className="text-[#0F172A]">{col.non_null_count.toLocaleString()}</strong>
                              </span>
                              <span>
                                Unique: <strong className="text-[#0F172A]">{col.unique_count.toLocaleString()}</strong>
                              </span>
                              <span>
                                Nulls:{' '}
                                <strong
                                  className={col.missing_count > 0 ? 'text-amber-600' : 'text-emerald-600'}
                                >
                                  {col.missing_count} ({col.missing_percentage}%)
                                </strong>
                              </span>
                            </div>
                          </div>

                          {/* Numeric Stats */}
                          {col.numeric_stats && (
                            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 text-xs bg-[#F8FAFC] p-3 rounded-xl border border-slate-100">
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Mean</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.mean.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Median</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.median.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Std Dev</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.std.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Min</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.min.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Max</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.max.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Q1</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.q1.toLocaleString()}</span>
                              </div>
                              <div>
                                <span className="text-[10px] text-[#64748B] block">Q3</span>
                                <span className="font-semibold text-[#0F172A]">{col.numeric_stats.q3.toLocaleString()}</span>
                              </div>
                            </div>
                          )}

                          {/* Categorical Stats & Frequencies */}
                          {col.categorical_stats && col.categorical_stats.top_values?.length > 0 && (
                            <div className="space-y-2">
                              <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider block">
                                Top Value Frequencies
                              </span>
                              <div className="space-y-1.5">
                                {col.categorical_stats.top_values.slice(0, 5).map((val, vIdx) => (
                                  <div key={vIdx} className="space-y-0.5">
                                    <div className="flex items-center justify-between text-xs">
                                      <span className="font-medium text-[#0F172A] truncate max-w-xs">
                                        {val.value || '(empty)'}
                                      </span>
                                      <span className="text-[#64748B] text-[11px]">
                                        {val.count.toLocaleString()} ({val.percentage}%)
                                      </span>
                                    </div>
                                    <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#2563EB] rounded-full"
                                        style={{ width: `${Math.min(val.percentage, 100)}%` }}
                                      />
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Datetime Stats */}
                          {col.datetime_stats && (
                            <div className="flex items-center gap-4 text-xs bg-[#F8FAFC] p-3 rounded-xl border border-slate-100 text-[#475569]">
                              <Calendar className="w-4 h-4 text-[#2563EB]" />
                              <span>
                                Range: <strong>{col.datetime_stats.min_date}</strong> to{' '}
                                <strong>{col.datetime_stats.max_date}</strong>
                              </span>
                              <span>•</span>
                              <span>{col.datetime_stats.unique_dates} unique timestamps</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-[#E2E8F0] rounded-2xl p-12 text-center text-xs text-[#64748B]">
                  No individual profile available.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProfilingPage;
