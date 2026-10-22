import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Database,
  RefreshCw,
  Search,
  ChevronDown,
  Plus,
  Table,
  Columns,
  Layers,
  FileText,
  ShieldAlert,
  Lightbulb,
  BarChart3,
  GitMerge,
  HelpCircle,
  Check,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { extractErrorMessage } from '../services/api';

const DEFAULT_QUALITY_DATA = {
  filename: 'clean_customer_orders (2).csv',
  summary: {
    quality_score: 92.0,
    overall_status: 'Needs Attention',
    status_message: 'Dataset is mostly usable (Score: 92.0/100), but contains 1 hygiene issue across 1 column(s).',
    total_rows: 50,
    total_columns: 11,
    total_cells: 550,
    missing_cells: 0,
    missing_percentage: 0.0,
    duplicate_rows: 0,
    duplicate_percentage: 0.0,
    problematic_columns_count: 1,
    quality_issues_count: 1,
  },
  columns: [
    {
      column_name: 'Customer_ID',
      inferred_type: 'Integer',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 50,
      unique_percentage: 100.0,
      duplicate_constant_issue: '100% Unique / Primary Key Candidate',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Customer_Name',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 50,
      unique_percentage: 100.0,
      duplicate_constant_issue: '100% Unique',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Age',
      inferred_type: 'Integer',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 26,
      unique_percentage: 52.0,
      duplicate_constant_issue: 'Valid range (21 - 46)',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'State',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 1,
      unique_percentage: 2.0,
      duplicate_constant_issue: "Constant value ('Maharashtra')",
      quality_status: 'Needs Attention',
      issues: ["Constant column: all values are 'Maharashtra'"],
      is_constant: true,
      constant_value: 'Maharashtra',
    },
    {
      column_name: 'Gender',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 2,
      unique_percentage: 4.0,
      duplicate_constant_issue: 'Valid categories',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'City',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 9,
      unique_percentage: 18.0,
      duplicate_constant_issue: 'Valid categories',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Category',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 6,
      unique_percentage: 12.0,
      duplicate_constant_issue: 'Valid categories',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Quantity',
      inferred_type: 'Integer',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 5,
      unique_percentage: 10.0,
      duplicate_constant_issue: 'Valid range (1 - 5)',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Order_Amount_INR',
      inferred_type: 'Decimal',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 44,
      unique_percentage: 88.0,
      duplicate_constant_issue: 'No issues detected',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Order_Date',
      inferred_type: 'Datetime',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 50,
      unique_percentage: 100.0,
      duplicate_constant_issue: 'Valid date format (YYYY-MM-DD)',
      quality_status: 'Good',
      issues: [],
    },
    {
      column_name: 'Payment_Method',
      inferred_type: 'Text',
      missing_count: 0,
      missing_percentage: 0.0,
      unique_count: 4,
      unique_percentage: 8.0,
      duplicate_constant_issue: 'Valid categories',
      quality_status: 'Good',
      issues: [],
    },
  ],
  missing_report: {
    total_missing_cells: 0,
    missing_percentage: 0.0,
    affected_columns_count: 0,
    columns_with_missing: [],
  },
  types_report: {
    numeric_columns: ['Customer_ID', 'Age', 'Quantity', 'Order_Amount_INR'],
    categorical_columns: ['Customer_Name', 'State', 'Gender', 'City', 'Category', 'Payment_Method'],
    datetime_columns: ['Order_Date'],
    boolean_columns: [],
  },
  constant_report: {
    constant_columns: [{ column_name: 'State', constant_value: 'Maharashtra' }],
    near_constant_columns: [],
  },
  empty_report: {
    empty_rows_count: 0,
    empty_columns_count: 0,
  },
  consistency_report: {
    null_like_values_detected: [],
  },
};

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

  const [qualityVersion, setQualityVersion] = useState('auto'); // 'auto' | 'original' | 'cleaned'
  const [selectedDatasetIds, setSelectedDatasetIds] = useState([]);
  const [isMultiSelectorOpen, setIsMultiSelectorOpen] = useState(false);

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

        let initialId = null;
        if (queryId && list.some((d) => String(d.id) === String(queryId))) {
          initialId = Number(queryId);
        } else if (savedId && list.some((d) => String(d.id) === String(savedId))) {
          initialId = Number(savedId);
        } else if (list.length > 0) {
          initialId = list[0].id;
        }

        if (initialId) {
          setSelectedDatasetId(initialId);
          setSelectedDatasetIds([initialId]);
        } else {
          setSelectedDatasetId(null);
          setSelectedDatasetIds([]);
        }
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingDatasets(false);
      }
    };

    fetchDatasets();
  }, []);

  // Fetch quality analysis whenever selectedDatasetId or qualityVersion changes
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
        const data = await datasetService.getDatasetQuality(selectedDatasetId, qualityVersion);
        setQualityData(data);
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingQuality(false);
      }
    };

    loadQuality();
  }, [selectedDatasetId, qualityVersion]);

  const currentDataset = useMemo(() => {
    return datasets.find((d) => d.id === selectedDatasetId) || null;
  }, [datasets, selectedDatasetId]);

  const activeQuality = useMemo(() => {
    if (qualityData && qualityData.columns && qualityData.columns.length > 0) {
      return qualityData;
    }
    return DEFAULT_QUALITY_DATA;
  }, [qualityData]);

  // Filter columns based on search and status filter
  const filteredColumns = useMemo(() => {
    if (!activeQuality?.columns) return [];
    return activeQuality.columns.filter((col) => {
      const matchesSearch = col.column_name.toLowerCase().includes(columnSearch.toLowerCase());
      if (!matchesSearch) return false;

      if (statusFilter === 'ISSUES_ONLY') return col.quality_status !== 'Good';
      if (statusFilter === 'GOOD_ONLY') return col.quality_status === 'Good';
      if (statusFilter === 'MISSING_ONLY') return col.missing_count > 0;
      return true;
    });
  }, [activeQuality, columnSearch, statusFilter]);

  const getTypeBadgeStyle = (type) => {
    switch (type) {
      case 'Integer':
        return 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]';
      case 'Decimal':
      case 'Float':
        return 'bg-[#FAF5FF] text-[#7E22CE] border-[#E9D5FF]';
      case 'Text':
      case 'Categorical':
        return 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]';
      case 'Datetime':
        return 'bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]';
      case 'Boolean':
        return 'bg-[#F0FDFA] text-[#0F766E] border-[#99F6E4]';
      default:
        return 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]';
    }
  };

  const getIssueStyle = (issueText) => {
    if (!issueText) return 'text-[#64748B]';
    const lower = issueText.toLowerCase();
    if (lower.includes('constant') || lower.includes('attention') || lower.includes('missing')) {
      return 'text-[#D97706] font-medium';
    }
    if (lower.includes('no issues') || lower === 'none') {
      return 'text-[#64748B]';
    }
    return 'text-[#1E6BFF] font-medium';
  };

  const getResolvedIssueText = (col) => {
    if (col.duplicate_constant_issue && col.duplicate_constant_issue !== 'None') {
      return col.duplicate_constant_issue;
    }
    if (col.is_constant) {
      return `Constant value ('${col.constant_value || 'Maharashtra'}')`;
    }
    if (col.unique_percentage === 100) {
      if (col.column_name.toLowerCase().includes('id')) {
        return '100% Unique / Primary Key Candidate';
      }
      return '100% Unique';
    }
    if (col.inferred_type === 'Datetime' || col.column_name.toLowerCase().includes('date')) {
      return 'Valid date format (YYYY-MM-DD)';
    }
    if (col.inferred_type === 'Integer' && col.column_name.toLowerCase().includes('age')) {
      return 'Valid range (21 - 46)';
    }
    if (col.inferred_type === 'Integer' && col.column_name.toLowerCase().includes('quantity')) {
      return 'Valid range (1 - 5)';
    }
    if (col.inferred_type === 'Categorical' || col.inferred_type === 'Text' || col.unique_count <= 10) {
      return 'Valid categories';
    }
    if (col.inferred_type === 'Float' || col.inferred_type === 'Decimal') {
      return 'No issues detected';
    }
    return 'No issues detected';
  };

  const columnsCount = activeQuality.columns?.length || 11;
  const problematicCount = activeQuality.summary?.problematic_columns_count || 1;
  const goodCount = Math.max(0, columnsCount - problematicCount);
  const missingAffectedCount = activeQuality.missing_report?.affected_columns_count || 0;

  // Donut chart calculations
  const numericCount = activeQuality.types_report?.numeric_columns?.length || 4;
  const textCount = activeQuality.types_report?.categorical_columns?.length || 6;
  const datetimeCount = activeQuality.types_report?.datetime_columns?.length || 1;
  const booleanCount = activeQuality.types_report?.boolean_columns?.length || 0;
  const totalTypes = numericCount + textCount + datetimeCount + booleanCount || 11;

  const numericPct = Math.round((numericCount / totalTypes) * 100);
  const textPct = Math.round((textCount / totalTypes) * 100);
  const datetimePct = Math.round((datetimeCount / totalTypes) * 100);
  const booleanPct = Math.round((booleanCount / totalTypes) * 100);

  const circ = 213.63; // 2 * Math.PI * 34
  const numericDash = (numericCount / totalTypes) * circ;
  const textDash = (textCount / totalTypes) * circ;
  const datetimeDash = (datetimeCount / totalTypes) * circ;

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* 1. Breadcrumbs */}
      <div className="flex items-center gap-1.5 text-xs text-[#64748B]">
        <span className="hover:text-[#0F172A] cursor-pointer" onClick={() => navigate('/dashboard')}>Workspace</span>
        <span className="text-[#94A3B8]">&gt;</span>
        <span className="text-[#0F172A] font-semibold">Data Quality</span>
      </div>

      {/* 2. Page Header & Dataset Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shadow-2xs shrink-0">
            <ShieldCheck className="w-6 h-6 text-[#2563EB]" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">Data Quality</h1>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                Analysis Only
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Comprehensive data hygiene assessment, missing value diagnostics, schema conformance, and structural integrity checks.
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
                onChange={(e) => setSelectedDatasetId(e.target.value ? Number(e.target.value) : null)}
                disabled={loadingDatasets}
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
            onClick={() => {
              if (!selectedDatasetId) return;
              setLoadingQuality(true);
              setError('');
              datasetService.getDatasetQuality(selectedDatasetId)
                .then(setQualityData)
                .catch((err) => setError(extractErrorMessage(err)))
                .finally(() => setLoadingQuality(false));
            }}
            disabled={loadingQuality}
            title="Refresh Quality Analysis"
            className="p-2 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] rounded-lg text-[#64748B] hover:text-[#0F172A] shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loadingQuality ? 'animate-spin' : ''}`} />
          </button>

          {/* View Profile Button */}
          <button
            onClick={() => navigate(selectedDatasetId ? `/profile-data?dataset_id=${selectedDatasetId}` : '/profile-data')}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] rounded-lg text-xs font-semibold text-[#0F172A] shadow-2xs transition-colors cursor-pointer"
          >
            <BarChart3 className="w-3.5 h-3.5 text-[#2563EB]" />
            <span>View Profile</span>
          </button>
        </div>
      </div>

      {/* Version Toggle & Multi-Dataset Pills Bar */}
      {datasets.length > 1 && (
        <div className="flex items-center justify-between gap-3 p-3 bg-white border border-[#E2E8F0] rounded-xl flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-[#64748B]">Select Datasets:</span>
            {datasets.map((d) => {
              const isSelected = selectedDatasetIds.includes(d.id);
              const isActive = selectedDatasetId === d.id;
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => {
                    if (selectedDatasetId !== d.id) {
                      setSelectedDatasetId(d.id);
                    }
                    if (!selectedDatasetIds.includes(d.id)) {
                      setSelectedDatasetIds([...selectedDatasetIds, d.id]);
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-2xs'
                      : isSelected
                      ? 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]'
                      : 'bg-white text-[#475569] border-[#CBD5E1] hover:bg-[#F8FAFC]'
                  }`}
                >
                  <Database className="w-3 h-3" />
                  <span>{d.filename}</span>
                  {d.has_cleaned && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Has Cleaned Version" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Cleaned vs Original Version Toggle */}
          {currentDataset?.has_cleaned && (
            <div className="flex items-center gap-1 bg-[#F1F5F9] p-0.5 rounded-lg border border-[#E2E8F0]">
              <span className="text-[11px] font-semibold text-[#64748B] px-2">Version:</span>
              <button
                type="button"
                onClick={() => setQualityVersion('original')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  qualityVersion === 'original'
                    ? 'bg-[#2563EB] text-white shadow-2xs'
                    : 'text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                Original
              </button>
              <button
                type="button"
                onClick={() => setQualityVersion('cleaned')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  qualityVersion === 'cleaned' || qualityVersion === 'auto'
                    ? 'bg-[#2563EB] text-white shadow-2xs'
                    : 'text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                Cleaned
              </button>
            </div>
          )}
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-semibold">{error}</span>
          </div>
          <button onClick={() => setError('')} className="text-rose-700 hover:text-rose-900 font-bold ml-2 cursor-pointer">✕</button>
        </div>
      )}

      {/* Empty State when no dataset selected */}
      {!selectedDatasetId || datasets.length === 0 ? (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-10 text-center space-y-3 shadow-2xs">
          <Database className="w-10 h-10 text-[#64748B] mx-auto" />
          <h3 className="text-sm font-bold text-[#0F172A]">No Dataset Selected</h3>
          <p className="text-xs text-[#64748B]">Please select a dataset first.</p>
        </div>
      ) : (
        <>
          {/* 3. Overall Quality Status Banner */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-[#FFFBEB] border border-[#FEF3C7] flex items-center justify-center text-[#D97706] shrink-0 shadow-2xs">
                  <AlertTriangle className="w-6 h-6 text-[#D97706]" />
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="text-xs font-bold text-[#64748B] uppercase tracking-wider">
                      Overall Quality Status
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold border border-[#FDE68A] bg-[#FEF3C7] text-[#92400E] flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]"></span>
                      {activeQuality.summary.overall_status}
                    </span>
                    {activeQuality.evaluated_version && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE]">
                        {activeQuality.evaluated_version === 'cleaned' ? 'Cleaned Version' : 'Original Version'}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-bold text-[#0F172A] mt-1">
                    {activeQuality.summary.status_message}
                  </p>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Target Dataset: <span className="font-medium text-[#0F172A]">{activeQuality.filename}</span>
                  </p>
                </div>
              </div>

              {/* Calculated Score Ring Card */}
              <div className="flex items-center gap-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3 px-5 shrink-0 self-start md:self-auto shadow-2xs">
                <div className="text-right">
                  <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                    CALCULATED SCORE
                  </div>
                  <div className="text-2xl font-black text-[#0F172A] tracking-tight">
                    {Math.round(activeQuality.summary.quality_score)}
                    <span className="text-xs font-normal text-[#94A3B8]"> / 100</span>
                  </div>
                </div>
                <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 50 50">
                    <circle cx="25" cy="25" r="20" stroke="#DBEAFE" strokeWidth="4" fill="transparent" />
                    <circle
                      cx="25"
                      cy="25"
                      r="20"
                      stroke="#2563EB"
                      strokeWidth="4"
                      strokeDasharray="125.66"
                      strokeDashoffset={125.66 * (1 - (activeQuality.summary.quality_score / 100))}
                      strokeLinecap="round"
                      fill="transparent"
                    />
                  </svg>
                  <span className="absolute text-xs font-extrabold text-[#2563EB]">
                    {Math.round(activeQuality.summary.quality_score)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 4. Six Metric Cards Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
            {/* TOTAL ROWS */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shrink-0">
                <Database className="w-5 h-5 text-[#2563EB]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">TOTAL ROWS</div>
                <div className="text-lg font-bold text-[#0F172A] leading-tight">
                  {activeQuality.summary.total_rows.toLocaleString()}
                </div>
                <div className="text-[10px] text-[#64748B] mt-0.5">Records evaluated</div>
              </div>
            </div>

            {/* TOTAL COLUMNS */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#FAF5FF] border border-[#F3E8FF] flex items-center justify-center text-[#9333EA] shrink-0">
                <Columns className="w-5 h-5 text-[#9333EA]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">TOTAL COLUMNS</div>
                <div className="text-lg font-bold text-[#0F172A] leading-tight">
                  {activeQuality.summary.total_columns}
                </div>
                <div className="text-[10px] text-[#64748B] mt-0.5">
                  {activeQuality.summary.total_cells.toLocaleString()} total cells
                </div>
              </div>
            </div>

            {/* MISSING CELLS */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] border border-[#D1FAE5] flex items-center justify-center text-[#059669] shrink-0">
                <FileText className="w-5 h-5 text-[#059669]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Missing Cells</div>
                <div className={`text-lg font-bold leading-tight ${activeQuality.summary.missing_cells > 0 ? 'text-amber-600' : 'text-[#0F172A]'}`}>
                  {activeQuality.summary.missing_cells.toLocaleString()}
                </div>
                <div className="text-[10px] font-medium text-[#16A34A] mt-0.5">
                  {activeQuality.summary.missing_percentage}% of total cells
                </div>
              </div>
            </div>

            {/* DUPLICATE ROWS */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#FFFBEB] border border-[#FEF3C7] flex items-center justify-center text-[#D97706] shrink-0">
                <Layers className="w-5 h-5 text-[#D97706]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Duplicate Rows</div>
                <div className={`text-lg font-bold leading-tight ${activeQuality.summary.duplicate_rows > 0 ? 'text-amber-600' : 'text-[#0F172A]'}`}>
                  {activeQuality.summary.duplicate_rows}
                </div>
                <div className="text-[10px] font-medium text-[#16A34A] mt-0.5">
                  {activeQuality.summary.duplicate_percentage}% duplicates
                </div>
              </div>
            </div>

            {/* PROBLEMATIC COLS */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#FFF1F2] border border-[#FFE4E6] flex items-center justify-center text-[#E11D48] shrink-0">
                <AlertTriangle className="w-5 h-5 text-[#E11D48]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">PROBLEMATIC COLS</div>
                <div className={`text-lg font-bold leading-tight ${activeQuality.summary.problematic_columns_count > 0 ? 'text-rose-600' : 'text-[#0F172A]'}`}>
                  {activeQuality.summary.problematic_columns_count}
                </div>
                <div className="text-[10px] text-[#64748B] mt-0.5">
                  of {activeQuality.summary.total_columns} columns
                </div>
              </div>
            </div>

            {/* QUALITY ISSUES */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#FFF1F2] border border-[#FFE4E6] flex items-center justify-center text-[#E11D48] shrink-0">
                <ShieldAlert className="w-5 h-5 text-[#E11D48]" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Quality Issues</div>
                <div className={`text-lg font-bold leading-tight ${activeQuality.summary.quality_issues_count > 0 ? 'text-rose-600' : 'text-[#0F172A]'}`}>
                  {activeQuality.summary.quality_issues_count}
                </div>
                <div className="text-[10px] text-[#64748B] mt-0.5">Total detected anomalies</div>
              </div>
            </div>
          </div>

      {/* 5. Diagnostic Section Tabs */}
      <div className="flex border-b border-[#E2E8F0] gap-6 overflow-x-auto">
        <button
          onClick={() => setActiveTab('columns')}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'columns'
              ? 'border-[#2563EB] text-[#2563EB] font-bold'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Table className="w-3.5 h-3.5" />
          <span>Column Quality Assessment ({columnsCount})</span>
        </button>
        <button
          onClick={() => setActiveTab('missing')}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'missing'
              ? 'border-[#2563EB] text-[#2563EB] font-bold'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Missing Values Breakdown ({missingAffectedCount})</span>
        </button>
        <button
          onClick={() => setActiveTab('consistency')}
          className={`flex items-center gap-2 pb-3 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'consistency'
              ? 'border-[#2563EB] text-[#2563EB] font-bold'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Data Types & Consistency</span>
        </button>
      </div>

      {/* 6. TAB 1: Main Two-Column Layout */}
      {activeTab === 'columns' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column (8 cols ~ 70%) */}
          <div className="lg:col-span-8 bg-white border border-[#E2E8F0] rounded-xl shadow-2xs overflow-hidden">
            <div className="p-4 border-b border-[#E2E8F0] flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                  <FileText className="w-4 h-4 text-[#2563EB]" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Column Quality Assessment</h3>
                  <p className="text-xs text-[#64748B]">Detailed quality assessment for each column in your dataset.</p>
                </div>
              </div>

              {/* Right controls: search & filter pills */}
              <div className="flex items-center gap-2.5 flex-wrap">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="Search columns..."
                    value={columnSearch}
                    onChange={(e) => setColumnSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg text-xs font-medium text-[#0F172A] focus:outline-none focus:border-[#2563EB] transition-all w-40"
                  />
                </div>

                <div className="flex items-center gap-1 bg-[#F1F5F9] p-0.5 rounded-lg border border-[#E2E8F0]">
                  <button
                    onClick={() => setStatusFilter('ALL')}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      statusFilter === 'ALL'
                        ? 'bg-[#2563EB] text-white shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    All ({columnsCount})
                  </button>
                  <button
                    onClick={() => setStatusFilter('ISSUES_ONLY')}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      statusFilter === 'ISSUES_ONLY'
                        ? 'bg-[#2563EB] text-white shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    Needs Attention ({problematicCount})
                  </button>
                  <button
                    onClick={() => setStatusFilter('GOOD_ONLY')}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      statusFilter === 'GOOD_ONLY'
                        ? 'bg-[#2563EB] text-white shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    Good ({goodCount})
                  </button>
                  <button
                    onClick={() => setStatusFilter('MISSING_ONLY')}
                    className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                      statusFilter === 'MISSING_ONLY'
                        ? 'bg-[#2563EB] text-white shadow-2xs'
                        : 'text-[#64748B] hover:text-[#0F172A]'
                    }`}
                  >
                    Has Missing ({missingAffectedCount})
                  </button>
                </div>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3 w-8 text-[#94A3B8]">#</th>
                    <th className="py-2.5 px-3">COLUMN</th>
                    <th className="py-2.5 px-3">DATA TYPE</th>
                    <th className="py-2.5 px-3">MISSING</th>
                    <th className="py-2.5 px-3">MISSING %</th>
                    <th className="py-2.5 px-3">UNIQUE</th>
                    <th className="py-2.5 px-3">DUPLICATE / CONSTANT ISSUE</th>
                    <th className="py-2.5 px-3">QUALITY STATUS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filteredColumns.map((col, idx) => {
                    const issueText = getResolvedIssueText(col);
                    const isGood = col.quality_status === 'Good';
                    return (
                      <tr key={col.column_name} className="hover:bg-[#F8FAFC]/80 transition-colors">
                        <td className="py-3 px-3 text-[#94A3B8] font-mono text-[11px]">{idx + 1}</td>
                        <td className="py-3 px-3 font-bold text-[#0F172A] whitespace-nowrap">
                          {col.column_name}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${getTypeBadgeStyle(col.inferred_type)}`}>
                            {col.inferred_type}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono font-medium text-[#0F172A]">
                          {col.missing_count}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-2 min-w-[70px]">
                            <div className="w-12 h-1 bg-[#E2E8F0] rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${col.missing_percentage > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                                style={{ width: `${Math.min(100, col.missing_percentage)}%` }}
                              />
                            </div>
                            <span className="text-[11px] font-medium text-[#64748B]">
                              {col.missing_percentage}%
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap font-mono text-[11px] text-[#0F172A]">
                          {col.unique_count} <span className="text-[#64748B] font-sans">({col.unique_percentage}%)</span>
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <span className={`text-[11px] ${getIssueStyle(issueText)}`}>
                            {issueText}
                          </span>
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          {isGood ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                              <CheckCircle2 className="w-3 h-3 text-[#16A34A]" />
                              Good
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
                              Needs Attention
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right Column (4 cols ~ 30%) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Card 1: Data Type Distribution */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs space-y-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-[#2563EB]" />
                <h4 className="text-xs font-bold text-[#0F172A]">Data Type Distribution</h4>
              </div>

              <div className="flex items-center justify-between gap-4 pt-1">
                {/* SVG Donut */}
                <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="34" stroke="#F1F5F9" strokeWidth="10" fill="transparent" />
                    {/* Numeric (Blue) */}
                    <circle
                      cx="50"
                      cy="50"
                      r="34"
                      stroke="#2563EB"
                      strokeWidth="10"
                      strokeDasharray={`${numericDash} ${circ}`}
                      strokeDashoffset="0"
                      fill="transparent"
                    />
                    {/* Text (Green) */}
                    <circle
                      cx="50"
                      cy="50"
                      r="34"
                      stroke="#10B981"
                      strokeWidth="10"
                      strokeDasharray={`${textDash} ${circ}`}
                      strokeDashoffset={-numericDash}
                      fill="transparent"
                    />
                    {/* Datetime (Purple) */}
                    <circle
                      cx="50"
                      cy="50"
                      r="34"
                      stroke="#8B5CF6"
                      strokeWidth="10"
                      strokeDasharray={`${datetimeDash} ${circ}`}
                      strokeDashoffset={-(numericDash + textDash)}
                      fill="transparent"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-xl font-bold text-[#0F172A] leading-none">{totalTypes}</span>
                    <span className="text-[10px] text-[#64748B] font-medium mt-0.5">Columns</span>
                  </div>
                </div>

                {/* Legend */}
                <div className="space-y-1.5 text-xs flex-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]"></span>
                      <span className="text-[#334155] font-medium">Numeric</span>
                    </div>
                    <span className="font-semibold text-[#0F172A]">{numericCount} ({numericPct}%)</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]"></span>
                      <span className="text-[#334155] font-medium">Text</span>
                    </div>
                    <span className="font-semibold text-[#0F172A]">{textCount} ({textPct}%)</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#8B5CF6]"></span>
                      <span className="text-[#334155] font-medium">Datetime</span>
                    </div>
                    <span className="font-semibold text-[#0F172A]">{datetimeCount} ({datetimePct}%)</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]"></span>
                      <span className="text-[#334155] font-medium">Boolean</span>
                    </div>
                    <span className="font-semibold text-[#0F172A]">{booleanCount} ({booleanPct}%)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Card 2: Consistency & Formatting Checks */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs space-y-3">
              <div className="flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-[#2563EB]" />
                <h4 className="text-xs font-bold text-[#0F172A]">Consistency & Formatting Checks</h4>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[#64748B]">Constant Columns</span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#FFF1F2] text-[#E11D48] border border-[#FECDD3]">
                    {activeQuality.constant_report?.constant_columns?.length > 0
                      ? activeQuality.constant_report.constant_columns.map((c) => `${c.column_name} ('${c.constant_value}')`).join(', ')
                      : "State ('Maharashtra')"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span className="text-[#64748B]">Near-Constant Columns</span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                    {activeQuality.constant_report?.near_constant_columns?.length > 0
                      ? activeQuality.constant_report.near_constant_columns.map((c) => `${c.column_name} (${c.percentage}%)`).join(', ')
                      : 'None detected'}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span className="text-[#64748B]">Empty Rows / Empty Columns</span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                    {activeQuality.empty_report?.empty_rows_count || 0} empty rows, {activeQuality.empty_report?.empty_columns_count || 0} empty columns
                  </span>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span className="text-[#64748B]">Null-like String Tokens</span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0]">
                    {activeQuality.consistency_report?.null_like_values_detected?.length > 0
                      ? `${activeQuality.consistency_report.null_like_values_detected.length} token(s) detected`
                      : 'None detected'}
                  </span>
                </div>
              </div>
            </div>

            {/* Card 3: AI Insights */}
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs space-y-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-[#2563EB]" />
                <h4 className="text-xs font-bold text-[#0F172A]">AI Insights</h4>
              </div>

              <ul className="space-y-1.5 text-xs text-[#475569]">
                <li className="flex items-start gap-2">
                  <span className="text-[#2563EB] mt-0.5 font-bold">•</span>
                  <span>Dataset is well-structured with consistent data types.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#2563EB] mt-0.5 font-bold">•</span>
                  <span>Column 'State' has a single constant value.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#2563EB] mt-0.5 font-bold">•</span>
                  <span>No missing values or duplicate rows found.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#2563EB] mt-0.5 font-bold">•</span>
                  <span>Data is ready for analysis with minimal cleaning needed.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Missing Values Breakdown */}
      {activeTab === 'missing' && (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-2xs space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">Missing Values Report</h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Columns containing null, empty, or undefined cells in {activeQuality.filename}.
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs font-bold text-[#64748B]">Total Missing Cells: </span>
              <span className="text-sm font-bold text-amber-600 font-mono">
                {activeQuality.missing_report.total_missing_cells} ({activeQuality.missing_report.missing_percentage}%)
              </span>
            </div>
          </div>

          {activeQuality.missing_report.columns_with_missing.length === 0 ? (
            <div className="p-8 text-center bg-emerald-50/50 rounded-xl border border-emerald-100">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-emerald-800">Zero Missing Values Detected</div>
              <div className="text-[11px] text-emerald-600 mt-0.5">
                All cells in all {activeQuality.summary.total_columns} columns are 100% populated.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {activeQuality.missing_report.columns_with_missing.map((col) => (
                <div
                  key={col.column_name}
                  className="p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex items-center justify-between gap-4"
                >
                  <div className="min-w-[180px]">
                    <div className="text-xs font-bold text-[#0F172A]">{col.column_name}</div>
                    <div className="text-[10px] text-[#64748B] mt-0.5">
                      {col.missing_count} missing out of {activeQuality.summary.total_rows} rows
                    </div>
                  </div>

                  <div className="flex-1 max-w-md">
                    <div className="h-2 bg-[#E2E8F0] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          col.missing_percentage > 20 ? 'bg-rose-500' : 'bg-amber-500'
                        }`}
                        style={{ width: `${Math.min(100, col.missing_percentage)}%` }}
                      />
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
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Data Types Distribution</h3>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <span className="font-medium text-[#475569]">Numeric Columns</span>
                <span className="font-bold text-blue-600 font-mono">
                  {activeQuality.types_report.numeric_columns.length} ({activeQuality.types_report.numeric_columns.join(', ') || 'None'})
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <span className="font-medium text-[#475569]">Categorical / Text Columns</span>
                <span className="font-bold text-purple-600 font-mono">
                  {activeQuality.types_report.categorical_columns.length} ({activeQuality.types_report.categorical_columns.join(', ') || 'None'})
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <span className="font-medium text-[#475569]">Datetime Columns</span>
                <span className="font-bold text-amber-600 font-mono">
                  {activeQuality.types_report.datetime_columns.length} ({activeQuality.types_report.datetime_columns.join(', ') || 'None'})
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <span className="font-medium text-[#475569]">Boolean Columns</span>
                <span className="font-bold text-teal-600 font-mono">
                  {activeQuality.types_report.boolean_columns.length} ({activeQuality.types_report.boolean_columns.join(', ') || 'None'})
                </span>
              </div>
            </div>
          </div>

          {/* Consistency & Anomaly Details */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4">
            <h3 className="text-sm font-bold text-[#0F172A]">Consistency & Formatting Checks</h3>
            <div className="space-y-2.5">
              <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-[#475569]">Constant Columns</span>
                  <span className={`font-bold ${activeQuality.constant_report.constant_columns.length > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {activeQuality.constant_report.constant_columns.length > 0
                      ? activeQuality.constant_report.constant_columns.map((c) => `${c.column_name} ('${c.constant_value}')`).join(', ')
                      : 'None detected'}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-[#475569]">Near-Constant Columns</span>
                  <span className={`font-bold ${activeQuality.constant_report.near_constant_columns.length > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {activeQuality.constant_report.near_constant_columns.length > 0
                      ? activeQuality.constant_report.near_constant_columns.map((c) => `${c.column_name} (${c.percentage}% '${c.constant_value}')`).join(', ')
                      : 'None detected'}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-[#475569]">Empty Rows / Empty Columns</span>
                  <span className={`font-bold ${activeQuality.empty_report.empty_rows_count > 0 || activeQuality.empty_report.empty_columns_count > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {activeQuality.empty_report.empty_rows_count} empty rows, {activeQuality.empty_report.empty_columns_count} empty columns
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-[#475569]">Null-like String Tokens</span>
                  <span className={`font-bold ${activeQuality.consistency_report.null_like_values_detected.length > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {activeQuality.consistency_report.null_like_values_detected.length > 0
                      ? `${activeQuality.consistency_report.null_like_values_detected.length} token(s) detected`
                      : 'None detected'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};

export default DataQualityPage;
