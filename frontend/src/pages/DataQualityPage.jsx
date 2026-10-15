import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Database,
  RefreshCw,
  FileSearch,
  Search,
  ChevronDown,
  Plus,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { extractErrorMessage } from '../services/api';

export const DataQualityPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [qualityData, setQualityData] = useState(null);

  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [loadingQuality, setLoadingQuality] = useState(false);
  const [error, setError] = useState('');
  const [columnSearch, setColumnSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [activeTab, setActiveTab] = useState('columns');

  // Load datasets list on mount
  useEffect(() => {
    const fetchDatasets = async () => {
      setLoadingDatasets(true);
      setError('');
      try {
        const data = await datasetService.getDatasets();
        const list = data || [];
        setDatasets(list);

        const queryId = searchParams.get('dataset_id') || searchParams.get('id');
        const savedId = localStorage.getItem('selected_dataset_id');

        if (queryId && list.some((d) => String(d.id) === String(queryId))) {
          setSelectedDatasetId(Number(queryId));
        } else if (savedId && list.some((d) => String(d.id) === String(savedId))) {
          setSelectedDatasetId(Number(savedId));
        } else {
          // Empty state: please select a dataset first
          setSelectedDatasetId(null);
        }
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingDatasets(false);
      }
    };

    fetchDatasets();
  }, []);

  // Fetch quality analysis whenever selectedDatasetId changes
  useEffect(() => {
    if (!selectedDatasetId) {
      setQualityData(null);
      return;
    }

    setQualityData(null);
    setError('');
    setLoadingQuality(true);

    setSearchParams({ dataset_id: selectedDatasetId }, { replace: true });
    localStorage.setItem('selected_dataset_id', String(selectedDatasetId));

    const loadQuality = async () => {
      try {
        const data = await datasetService.getDatasetQuality(selectedDatasetId);
        setQualityData(data);
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingQuality(false);
      }
    };

    loadQuality();
  }, [selectedDatasetId]);

  const currentDataset = useMemo(() => {
    return datasets.find((d) => d.id === selectedDatasetId) || null;
  }, [datasets, selectedDatasetId]);

  // Filter columns based on search and status filter
  const filteredColumns = useMemo(() => {
    if (!qualityData?.columns) return [];
    return qualityData.columns.filter((col) => {
      const matchesSearch = col.column_name.toLowerCase().includes(columnSearch.toLowerCase());
      if (!matchesSearch) return false;

      if (statusFilter === 'ISSUES_ONLY') return col.quality_status !== 'Good';
      if (statusFilter === 'GOOD_ONLY') return col.quality_status === 'Good';
      if (statusFilter === 'MISSING_ONLY') return col.missing_count > 0;
      return true;
    });
  }, [qualityData, columnSearch, statusFilter]);

  // Helper for status badge colors
  const getStatusBadge = (status) => {
    if (status === 'Good') {
      return {
        bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        dot: 'bg-emerald-500',
        icon: CheckCircle2,
      };
    }
    if (status === 'Needs Attention' || status === 'Warning') {
      return {
        bg: 'bg-amber-50 text-amber-700 border-amber-200',
        dot: 'bg-amber-500',
        icon: AlertTriangle,
      };
    }
    return {
      bg: 'bg-rose-50 text-rose-700 border-rose-200',
      dot: 'bg-rose-500',
      icon: AlertCircle,
    };
  };

  const getTypeBadgeColor = (type) => {
    switch (type) {
      case 'Integer':
      case 'Float':
      case 'Numeric':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Categorical':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Datetime':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Boolean':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header & Dataset Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">Data Quality</h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              Analysis Only
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1">
            Comprehensive data hygiene assessment, missing value diagnostics, schema conformance, and structural integrity checks.
          </p>
        </div>

        {/* Dataset Selector Dropdown */}
        <div className="flex items-center gap-2.5">
          <div className="relative min-w-[220px]">
            <Database className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <select
              value={selectedDatasetId || ''}
              onChange={(e) => setSelectedDatasetId(e.target.value ? Number(e.target.value) : null)}
              disabled={loadingDatasets}
              className="w-full pl-8 pr-8 py-1.5 bg-white border border-[#CBD5E1] rounded-lg text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all appearance-none cursor-pointer disabled:opacity-50"
            >
              <option value="">-- Select a Dataset --</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.rows} rows, {d.columns} cols)
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {selectedDatasetId && (
            <>
              <button
                onClick={() => {
                  setQualityData(null);
                  setError('');
                  setLoadingQuality(true);
                  datasetService.getDatasetQuality(selectedDatasetId)
                    .then(setQualityData)
                    .catch((err) => setError(extractErrorMessage(err)))
                    .finally(() => setLoadingQuality(false));
                }}
                disabled={loadingQuality}
                title="Refresh Quality Analysis"
                className="p-2 rounded-lg bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#64748B] hover:text-[#0F172A] transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingQuality ? 'animate-spin' : ''}`} />
              </button>

              <button
                onClick={() => navigate(`/profile-data?dataset_id=${selectedDatasetId}`)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#EFF6FF] text-[#1D4ED8] hover:bg-[#DBEAFE] border border-[#BFDBFE] transition-colors cursor-pointer"
                title="View statistical profile for this dataset"
              >
                <FileSearch className="w-3.5 h-3.5" />
                <span>View Profile</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-600" />
          <div className="text-xs">
            <span className="font-semibold">Quality Analysis Error: </span>
            {error}
          </div>
        </div>
      )}

      {/* Empty State: No Dataset Selected */}
      {!selectedDatasetId && !loadingDatasets && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-12 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] border border-[#BFDBFE] text-[#2563EB] flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-[#0F172A]">Please select a dataset first.</h3>
          <p className="text-xs text-[#64748B] max-w-md mx-auto mt-1.5 mb-6">
            Choose an uploaded dataset from the selector above or browse your datasets to inspect missing values, duplicate records, data types, and potential quality issues.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => navigate('/datasets')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-[#CBD5E1] text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] transition-colors cursor-pointer"
            >
              <Database className="w-3.5 h-3.5 text-[#64748B]" />
              <span>Browse Datasets</span>
            </button>
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2563EB] text-white text-xs font-medium hover:bg-[#1D4ED8] transition-colors cursor-pointer shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Upload New Dataset</span>
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loadingQuality && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-12 text-center shadow-xs">
          <div className="w-12 h-12 rounded-full border-3 border-[#2563EB]/20 border-t-[#2563EB] animate-spin mx-auto mb-4"></div>
          <h3 className="text-sm font-bold text-[#0F172A]">Analyzing Dataset Quality...</h3>
          <p className="text-xs text-[#64748B] mt-1">
            Inspecting {currentDataset?.filename || 'dataset'} for missing values, duplicates, and column conformance.
          </p>
        </div>
      )}

      {/* Quality Results */}
      {qualityData && !loadingQuality && (
        <div className="space-y-6">
          {/* Overall Quality Banner */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border ${
                    getStatusBadge(qualityData.summary.overall_status).bg
                  }`}
                >
                  {React.createElement(getStatusBadge(qualityData.summary.overall_status).icon, {
                    className: 'w-6 h-6',
                  })}
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-bold text-[#64748B] uppercase tracking-wider">
                      Overall Quality Status
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-bold border flex items-center gap-1.5 ${
                        getStatusBadge(qualityData.summary.overall_status).bg
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          getStatusBadge(qualityData.summary.overall_status).dot
                        }`}
                      ></span>
                      {qualityData.summary.overall_status}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-[#0F172A] mt-1">
                    {qualityData.summary.status_message}
                  </p>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Target Dataset: <span className="font-medium text-[#0F172A]">{qualityData.filename}</span>
                  </p>
                </div>
              </div>

              {/* Quality Score Gauge */}
              <div className="flex items-center gap-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3 px-5 shrink-0">
                <div className="text-right">
                  <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                    Calculated Score
                  </div>
                  <div className="text-2xl font-black text-[#0F172A] tracking-tight">
                    {qualityData.summary.quality_score}
                    <span className="text-xs font-normal text-[#94A3B8]"> / 100</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-full border-4 border-[#2563EB]/20 border-t-[#2563EB] flex items-center justify-center font-bold text-xs text-[#2563EB]">
                  {Math.round(qualityData.summary.quality_score)}%
                </div>
              </div>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Total Rows</div>
              <div className="text-lg font-bold text-[#0F172A] mt-1">
                {qualityData.summary.total_rows.toLocaleString()}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">Records evaluated</div>
            </div>

            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Total Columns</div>
              <div className="text-lg font-bold text-[#0F172A] mt-1">
                {qualityData.summary.total_columns}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">
                {qualityData.summary.total_cells.toLocaleString()} total cells
              </div>
            </div>

            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Missing Cells</div>
              <div className={`text-lg font-bold mt-1 ${qualityData.summary.missing_cells > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {qualityData.summary.missing_cells.toLocaleString()}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">
                {qualityData.summary.missing_percentage}% of total cells
              </div>
            </div>

            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Duplicate Rows</div>
              <div className={`text-lg font-bold mt-1 ${qualityData.summary.duplicate_rows > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {qualityData.summary.duplicate_rows}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">
                {qualityData.summary.duplicate_percentage}% duplicates
              </div>
            </div>

            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Problematic Cols</div>
              <div className={`text-lg font-bold mt-1 ${qualityData.summary.problematic_columns_count > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {qualityData.summary.problematic_columns_count}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">
                of {qualityData.summary.total_columns} columns
              </div>
            </div>

            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Quality Issues</div>
              <div className={`text-lg font-bold mt-1 ${qualityData.summary.quality_issues_count > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {qualityData.summary.quality_issues_count}
              </div>
              <div className="text-[10px] text-[#64748B] mt-0.5">Total detected anomalies</div>
            </div>
          </div>

          {/* Diagnostic Sections Tabs */}
          <div className="flex border-b border-[#E2E8F0] gap-2">
            <button
              onClick={() => setActiveTab('columns')}
              className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
                activeTab === 'columns'
                  ? 'border-[#2563EB] text-[#2563EB]'
                  : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              Column Quality Assessment ({qualityData.columns.length})
            </button>
            <button
              onClick={() => setActiveTab('missing')}
              className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
                activeTab === 'missing'
                  ? 'border-[#2563EB] text-[#2563EB]'
                  : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              Missing Values Breakdown ({qualityData.missing_report.affected_columns_count})
            </button>
            <button
              onClick={() => setActiveTab('consistency')}
              className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
                activeTab === 'consistency'
                  ? 'border-[#2563EB] text-[#2563EB]'
                  : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              Data Types & Consistency
            </button>
          </div>

          {/* TAB 1: Column Quality Table */}
          {activeTab === 'columns' && (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl shadow-xs overflow-hidden">
              <div className="p-4 border-b border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      placeholder="Search columns..."
                      value={columnSearch}
                      onChange={(e) => setColumnSearch(e.target.value)}
                      className="pl-8 pr-3 py-1.5 bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all w-52"
                    />
                  </div>
                </div>

                {/* Filter Chips */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    onClick={() => setStatusFilter('ALL')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                      statusFilter === 'ALL'
                        ? 'bg-[#2563EB] text-white'
                        : 'bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]'
                    }`}
                  >
                    All ({qualityData.columns.length})
                  </button>
                  <button
                    onClick={() => setStatusFilter('ISSUES_ONLY')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                      statusFilter === 'ISSUES_ONLY'
                        ? 'bg-amber-600 text-white'
                        : 'bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]'
                    }`}
                  >
                    Needs Attention ({qualityData.summary.problematic_columns_count})
                  </button>
                  <button
                    onClick={() => setStatusFilter('GOOD_ONLY')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                      statusFilter === 'GOOD_ONLY'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]'
                    }`}
                  >
                    Good ({qualityData.columns.length - qualityData.summary.problematic_columns_count})
                  </button>
                  <button
                    onClick={() => setStatusFilter('MISSING_ONLY')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                      statusFilter === 'MISSING_ONLY'
                        ? 'bg-blue-600 text-white'
                        : 'bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]'
                    }`}
                  >
                    Has Missing ({qualityData.missing_report.affected_columns_count})
                  </button>
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#475569] font-bold uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="py-3 px-4">Column</th>
                      <th className="py-3 px-4">Data Type</th>
                      <th className="py-3 px-4">Missing</th>
                      <th className="py-3 px-4">Missing %</th>
                      <th className="py-3 px-4">Unique</th>
                      <th className="py-3 px-4">Duplicate / Constant Issue</th>
                      <th className="py-3 px-4 text-right">Quality Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {filteredColumns.map((col) => {
                      const statusBadge = getStatusBadge(col.quality_status);
                      const StatusIcon = statusBadge.icon;
                      return (
                        <tr key={col.column_name} className="hover:bg-[#F8FAFC] transition-colors">
                          <td className="py-3 px-4 font-semibold text-[#0F172A]">
                            <div className="flex items-center gap-1.5">
                              <span>{col.column_name}</span>
                            </div>
                            {col.issues.length > 0 && (
                              <div className="text-[10px] text-[#64748B] font-normal mt-0.5">
                                {col.issues.join(' • ')}
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold border ${getTypeBadgeColor(col.inferred_type)}`}>
                              {col.inferred_type}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono font-medium text-[#0F172A]">
                            {col.missing_count}
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2 min-w-[100px]">
                              <div className="flex-1 h-1.5 bg-[#E2E8F0] rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    col.missing_percentage > 20
                                      ? 'bg-rose-500'
                                      : col.missing_percentage > 0
                                      ? 'bg-amber-500'
                                      : 'bg-emerald-500'
                                  }`}
                                  style={{ width: `${Math.min(100, col.missing_percentage)}%` }}
                                ></div>
                              </div>
                              <span className="text-[11px] font-medium text-[#64748B] w-10 text-right">
                                {col.missing_percentage}%
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-mono text-[#0F172A]">{col.unique_count}</span>
                            <span className="text-[10px] text-[#64748B] ml-1">({col.unique_percentage}%)</span>
                          </td>
                          <td className="py-3 px-4">
                            {col.duplicate_constant_issue !== 'None' ? (
                              <span
                                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${
                                  col.is_constant
                                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                                    : col.is_near_constant
                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                    : 'bg-blue-50 text-blue-700 border-blue-200'
                                }`}
                              >
                                {col.duplicate_constant_issue}
                              </span>
                            ) : (
                              <span className="text-[#94A3B8] text-xs">None</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span
                              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${statusBadge.bg}`}
                            >
                              <StatusIcon className="w-3 h-3" />
                              {col.quality_status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 2: Missing Values Diagnostic */}
          {activeTab === 'missing' && (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Missing Values Report</h3>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Columns containing null, empty, or undefined cells in {qualityData.filename}.
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold text-[#64748B]">Total Missing Cells: </span>
                  <span className="text-sm font-bold text-amber-600 font-mono">
                    {qualityData.missing_report.total_missing_cells} ({qualityData.missing_report.missing_percentage}%)
                  </span>
                </div>
              </div>

              {qualityData.missing_report.columns_with_missing.length === 0 ? (
                <div className="p-8 text-center bg-emerald-50/50 rounded-xl border border-emerald-100">
                  <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                  <div className="text-xs font-bold text-emerald-800">Zero Missing Values Detected</div>
                  <div className="text-[11px] text-emerald-600 mt-0.5">
                    All cells in all {qualityData.summary.total_columns} columns are 100% populated.
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {qualityData.missing_report.columns_with_missing.map((col) => (
                    <div
                      key={col.column_name}
                      className="p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex items-center justify-between gap-4"
                    >
                      <div className="min-w-[180px]">
                        <div className="text-xs font-bold text-[#0F172A]">{col.column_name}</div>
                        <div className="text-[10px] text-[#64748B] mt-0.5">
                          {col.missing_count} missing out of {qualityData.summary.total_rows} rows
                        </div>
                      </div>

                      <div className="flex-1 max-w-md">
                        <div className="h-2 bg-[#E2E8F0] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              col.missing_percentage > 20 ? 'bg-rose-500' : 'bg-amber-500'
                            }`}
                            style={{ width: `${Math.min(100, col.missing_percentage)}%` }}
                          ></div>
                        </div>
                      </div>

                      <div className="text-right min-w-[70px]">
                        <span className="text-xs font-bold text-[#0F172A]">{col.missing_percentage}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Data Types & Consistency */}
          {activeTab === 'consistency' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Data Types Summary */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-4">
                <h3 className="text-sm font-bold text-[#0F172A]">Data Types Distribution</h3>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <span className="font-medium text-[#475569]">Numeric Columns</span>
                    <span className="font-bold text-blue-600 font-mono">
                      {qualityData.types_report.numeric_columns.length} ({qualityData.types_report.numeric_columns.join(', ') || 'None'})
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <span className="font-medium text-[#475569]">Categorical / Text Columns</span>
                    <span className="font-bold text-purple-600 font-mono">
                      {qualityData.types_report.categorical_columns.length} ({qualityData.types_report.categorical_columns.join(', ') || 'None'})
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <span className="font-medium text-[#475569]">Datetime Columns</span>
                    <span className="font-bold text-amber-600 font-mono">
                      {qualityData.types_report.datetime_columns.length} ({qualityData.types_report.datetime_columns.join(', ') || 'None'})
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <span className="font-medium text-[#475569]">Boolean Columns</span>
                    <span className="font-bold text-teal-600 font-mono">
                      {qualityData.types_report.boolean_columns.length} ({qualityData.types_report.boolean_columns.join(', ') || 'None'})
                    </span>
                  </div>
                </div>
              </div>

              {/* Consistency & Anomaly Details */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-4">
                <h3 className="text-sm font-bold text-[#0F172A]">Consistency & Formatting Checks</h3>
                <div className="space-y-2.5">
                  <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#475569]">Constant Columns</span>
                      <span className={`font-bold ${qualityData.constant_report.constant_columns.length > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        {qualityData.constant_report.constant_columns.length > 0
                          ? qualityData.constant_report.constant_columns.map(c => `${c.column_name} ('${c.constant_value}')`).join(', ')
                          : 'None detected'}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#475569]">Near-Constant Columns</span>
                      <span className={`font-bold ${qualityData.constant_report.near_constant_columns.length > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {qualityData.constant_report.near_constant_columns.length > 0
                          ? qualityData.constant_report.near_constant_columns.map(c => `${c.column_name} (${c.percentage}% '${c.constant_value}')`).join(', ')
                          : 'None detected'}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#475569]">Empty Rows / Empty Columns</span>
                      <span className={`font-bold ${qualityData.empty_report.empty_rows_count > 0 || qualityData.empty_report.empty_columns_count > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        {qualityData.empty_report.empty_rows_count} empty rows, {qualityData.empty_report.empty_columns_count} empty columns
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#475569]">Null-like String Tokens</span>
                      <span className={`font-bold ${qualityData.consistency_report.null_like_values_detected.length > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {qualityData.consistency_report.null_like_values_detected.length > 0
                          ? `${qualityData.consistency_report.null_like_values_detected.length} token(s) detected`
                          : 'None detected'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DataQualityPage;
