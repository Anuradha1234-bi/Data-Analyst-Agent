import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Send,
  Sparkles,
  Database,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  Table as TableIcon,
  BarChart3,
  HelpCircle,
  Clock,
  Trash2,
  Layers,
  FileSpreadsheet,
  X,
  ArrowRight,
  ShieldCheck,
  Check,
  RotateCcw,
  SlidersHorizontal,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { analysisService } from '../services/analysisService';
import { extractErrorMessage } from '../services/api';
import { AnalyticalChart } from '../components/AnalyticalChart';

const renderFormattedText = (text) => {
  if (!text) return '';
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx} className="font-bold text-[#0F172A]">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={idx} className="px-1 py-0.2 bg-blue-100/80 border border-blue-200 text-[#1D4ED8] rounded font-mono text-[11px]">{part.slice(1, -1)}</code>;
    }
    return part;
  });
};

export const AnalysisPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Dataset states
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedVersion, setSelectedVersion] = useState('original');
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  // Question & Query states
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [currentResult, setCurrentResult] = useState(null);

  // Contextual suggested questions
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // Query History states
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // View presentation mode: 'both' | 'table' | 'chart'
  const [viewMode, setViewMode] = useState('both');

  // 1. Initial Load: Load Datasets
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
        }
      } catch (err) {
        setError(extractErrorMessage(err));
      } finally {
        setLoadingDatasets(false);
      }
    };

    fetchDatasets();
  }, []);

  // 2. When active dataset changes, update URL, fetch suggestions & history
  useEffect(() => {
    if (!selectedDatasetId) {
      setSuggestedQuestions([]);
      setCurrentResult(null);
      return;
    }

    setSearchParams({ dataset_id: selectedDatasetId }, { replace: true });
    localStorage.setItem('selected_dataset_id', String(selectedDatasetId));
    setError('');
    setCurrentResult(null);
    setQuestion('');

    // Fetch suggested questions
    const loadSuggestions = async () => {
      setLoadingSuggestions(true);
      try {
        const res = await analysisService.getSuggestedQuestions(selectedDatasetId);
        setSuggestedQuestions(res?.questions || []);
      } catch {
        setSuggestedQuestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    };

    // Fetch history
    const loadHistory = async () => {
      setLoadingHistory(true);
      try {
        const res = await analysisService.getHistory(selectedDatasetId, 30);
        setHistory(res?.history || []);
      } catch {
        setHistory([]);
      } finally {
        setLoadingHistory(false);
      }
    };

    loadSuggestions();
    loadHistory();
  }, [selectedDatasetId]);

  const currentDataset = useMemo(() => {
    return datasets.find((d) => d.id === selectedDatasetId) || null;
  }, [datasets, selectedDatasetId]);

  // 3. Submit question to backend
  const handleAskQuestion = async (queryText) => {
    const q = (queryText || question).trim();
    if (!q) return;

    if (!selectedDatasetId) {
      setError('Please select an active dataset before submitting a question.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const resp = await analysisService.askQuestion(
        selectedDatasetId,
        q,
        selectedVersion,
        currentResult ? { previous_query: currentResult.question } : null
      );
      setCurrentResult(resp);
      setQuestion('');

      // Refresh history
      const histRes = await analysisService.getHistory(selectedDatasetId, 30);
      setHistory(histRes?.history || []);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClearHistory = async () => {
    try {
      await analysisService.clearHistory(selectedDatasetId);
      setHistory([]);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const handleDeleteHistoryItem = async (histId, e) => {
    e.stopPropagation();
    try {
      await analysisService.deleteHistoryItem(histId);
      setHistory((prev) => prev.filter((item) => item.id !== histId));
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A] flex items-center gap-2.5">
            <span>Data Analyst Assistant</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#2563EB]/10 text-[#2563EB] border border-[#2563EB]/20">
              Natural Language Querying
            </span>
          </h1>
          <p className="text-xs text-[#64748B] mt-1">
            Ask analytical questions in natural language. Powered by deterministic aggregation, grouping, trend analysis, and evidence-grounded charting.
          </p>
        </div>

        {/* Action Buttons: New Thread & History */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={async () => {
              if (selectedDatasetId) {
                try {
                  await analysisService.clearContext(selectedDatasetId);
                } catch (e) {}
              }
              setCurrentResult(null);
              setQuestion('');
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl border border-[#CBD5E1] bg-white text-[#0F172A] hover:bg-[#F8FAFC] transition-all cursor-pointer shadow-2xs"
            title="Start fresh conversation thread"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            <span>New Thread</span>
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl border transition-all cursor-pointer ${
              showHistory
                ? 'bg-[#2563EB] text-white border-[#2563EB] shadow-xs'
                : 'bg-white text-[#0F172A] border-[#CBD5E1] hover:bg-[#F8FAFC]'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>History</span>
            {history.length > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  showHistory ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700'
                }`}
              >
                {history.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Dataset & Version Selector Toolbar */}
      {!loadingDatasets && datasets.length > 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-[#64748B]">
              <Database className="w-4 h-4 text-[#2563EB]" />
              <span className="font-semibold text-[#0F172A]">Dataset:</span>
            </div>

            {/* Dataset Dropdown */}
            <div className="relative">
              <select
                value={selectedDatasetId || ''}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedDatasetId(val ? Number(val) : null);
                  setCurrentResult(null);
                }}
                className="appearance-none bg-[#F8FAFC] border border-[#CBD5E1] hover:border-[#2563EB] rounded-xl px-3.5 py-1.5 pr-8 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer transition-all"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.original_filename || d.filename} ({(d.row_count ?? d.rows ?? 0).toLocaleString()} rows)
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Version Toggle (Original vs Cleaned) */}
            <div className="flex items-center gap-1 bg-[#F1F5F9] p-1 rounded-xl border border-slate-200 text-xs">
              <button
                type="button"
                onClick={() => setSelectedVersion('original')}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                  selectedVersion === 'original'
                    ? 'bg-white text-[#2563EB] shadow-2xs'
                    : 'text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                Original
              </button>
              <button
                type="button"
                onClick={() => {
                  if (currentDataset?.has_cleaned) {
                    setSelectedVersion('cleaned');
                  }
                }}
                disabled={!currentDataset?.has_cleaned}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 ${
                  selectedVersion === 'cleaned'
                    ? 'bg-white text-[#2563EB] shadow-2xs'
                    : currentDataset?.has_cleaned
                    ? 'text-[#64748B] hover:text-[#0F172A] cursor-pointer'
                    : 'text-[#94A3B8] opacity-60 cursor-not-allowed'
                }`}
                title={currentDataset?.has_cleaned ? 'Analyze cleaned version' : 'No cleaned version available'}
              >
                <span>Cleaned</span>
                {currentDataset?.has_cleaned && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                )}
              </button>
            </div>
          </div>

          {/* Dataset Dimension Badges */}
          {currentDataset && (
            <div className="flex items-center gap-3 text-xs text-[#64748B]">
              <span className="font-medium text-[#0F172A]">
                {(currentDataset.row_count ?? currentDataset.rows ?? 0).toLocaleString()} rows
              </span>
              <span>•</span>
              <span className="font-medium text-[#0F172A]">
                {currentDataset.column_count ?? currentDataset.columns ?? 0} columns
              </span>
              <span>•</span>
              <span>{formatFileSize(currentDataset.file_size ?? currentDataset.file_size_bytes ?? 0)}</span>
            </div>
          )}
        </div>
      )}

      {/* Main Analysis Input Box */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAskQuestion();
          }}
          className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3"
        >
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#2563EB]">
              <Sparkles className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isSubmitting || !selectedDatasetId}
              placeholder={
                selectedDatasetId
                  ? 'Ask a question about your dataset (e.g. What is the average sales amount? Or which category has the highest total?)...'
                  : 'Please select a dataset above first...'
              }
              className="w-full pl-10 pr-10 py-3 text-sm bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:opacity-50"
            />
            {question && (
              <button
                type="button"
                onClick={() => setQuestion('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-[#94A3B8] hover:text-[#0F172A]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <button
            type="submit"
            disabled={!question.trim() || isSubmitting || !selectedDatasetId}
            className="px-6 py-3 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Analyzing...</span>
              </>
            ) : (
              <>
                <span>Ask Analyst</span>
                <Send className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Contextual Suggested Questions Chips */}
        {suggestedQuestions.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-[#F1F5F9]">
            <div className="flex items-center justify-between text-[11px] text-[#64748B]">
              <span className="font-semibold uppercase tracking-wider text-[#0F172A] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
                <span>Suggested Questions for {currentDataset?.original_filename || 'this dataset'}:</span>
              </span>
              <span>Click to analyze</span>
            </div>

            <div className="flex flex-wrap gap-2">
              {suggestedQuestions.map((sq, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setQuestion(sq.question);
                    handleAskQuestion(sq.question);
                  }}
                  disabled={isSubmitting}
                  className="px-3 py-1.5 rounded-xl bg-[#F8FAFC] hover:bg-[#EFF6FF] text-[#0F172A] hover:text-[#2563EB] border border-[#E2E8F0] hover:border-[#BFDBFE] text-xs font-medium transition-all text-left cursor-pointer flex items-center gap-2 group"
                >
                  <span>{sq.question}</span>
                  <ArrowRight className="w-3 h-3 text-[#94A3B8] group-hover:text-[#2563EB] group-hover:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span className="font-medium">{error}</span>
          </div>
          <button
            onClick={() => setError('')}
            className="text-xs font-semibold text-red-700 hover:underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Empty State: No Dataset Selected */}
      {!loadingDatasets && datasets.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-14 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center mx-auto mb-4">
            <Database className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-[#0F172A]">No Datasets Available</h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto mt-2 leading-relaxed">
            Upload your CSV or Excel dataset to ask analytical questions, calculate metrics, and generate charts.
          </p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <span>Upload Dataset</span>
          </button>
        </div>
      )}

      {/* AMBIGUITY / CLARIFICATION CARD */}
      {currentResult?.status === 'needs_clarification' && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 shadow-xs space-y-4 animate-in fade-in">
          <div className="flex items-start gap-3">
            <HelpCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-amber-900">Clarification Needed</h3>
              <p className="text-xs text-amber-800 leading-relaxed">
                {currentResult.clarification_question || currentResult.answer}
              </p>
            </div>
          </div>

          {/* Clarification candidate options */}
          {((currentResult.clarification_candidates && currentResult.clarification_candidates.length > 0) ||
            (currentResult.clarification_options && currentResult.clarification_options.length > 0)) && (
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-semibold text-amber-900 block">
                Select which column you intended to continue:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {(currentResult.clarification_candidates && currentResult.clarification_candidates.length > 0
                  ? currentResult.clarification_candidates
                  : currentResult.clarification_options.map((opt) => ({
                      column: opt,
                      label: opt,
                      is_join_generated: false,
                    }))
                ).map((cand, idx) => {
                  const colName = typeof cand === 'string' ? cand : cand.column;
                  const isJoin = typeof cand === 'object' && cand.is_join_generated;
                  const srcDataset = typeof cand === 'object' ? cand.source_dataset : null;
                  const dataType = typeof cand === 'object' ? cand.data_type : null;
                  const desc = typeof cand === 'object' ? cand.description : null;
                  const hasSource = Boolean(srcDataset && srcDataset !== 'Source information unavailable');

                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        const clarifiedQuery = `${currentResult.question} using ${colName}`;
                        setQuestion(clarifiedQuery);
                        handleAskQuestion(clarifiedQuery);
                      }}
                      className="text-left p-3.5 bg-white border border-amber-200 hover:border-amber-400 text-amber-950 font-medium rounded-xl text-xs shadow-2xs hover:bg-amber-100/60 transition-all cursor-pointer flex items-center justify-between gap-3 group"
                    >
                      <div className="flex flex-col gap-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-amber-950 truncate font-mono text-[13px]">
                            {colName}
                          </span>
                          {dataType && dataType !== 'unknown' && (
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-200">
                              {dataType}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-col text-[11px] text-amber-800 gap-0.5">
                          <span className="font-semibold text-amber-900">
                            {hasSource
                              ? `Origin: ${srcDataset} (${isJoin ? 'Joined' : 'Original'})`
                              : isJoin
                              ? 'Joined origin: Source information unavailable'
                              : 'Base dataset: Source information unavailable'}
                          </span>
                          <span className="text-amber-700 text-[10px]">
                            {desc || (isJoin ? 'Join-generated duplicate column' : 'Original base dataset column')}
                          </span>
                        </div>
                      </div>
                      <span className="shrink-0 p-1.5 rounded-lg bg-amber-100 group-hover:bg-amber-200 text-amber-800 transition-colors">
                        <ArrowRight className="w-3.5 h-3.5" />
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ANALYSIS RESULT WORKSPACE */}
      {currentResult && currentResult.status !== 'needs_clarification' && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Main Answer Headline Card */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F1F5F9] pb-4">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                  Analyzed Question
                </span>
                <h3 className="text-base font-bold text-[#0F172A] leading-snug">
                  "{currentResult.question}"
                </h3>
                {currentResult.interpreted_question && currentResult.interpreted_question !== currentResult.question && (
                  <p className="text-xs text-[#64748B] font-medium">
                    Interpreted: <span className="text-[#2563EB]">{currentResult.interpreted_question}</span>
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2 self-start sm:self-auto">
                <span
                  className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${
                    currentResult.status === 'error'
                      ? 'bg-red-50 text-red-700 border-red-200'
                      : currentResult.confidence === 'High'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : currentResult.confidence === 'Medium'
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200'
                  }`}
                >
                  {currentResult.status === 'error' ? 'Query Error' : `${currentResult.confidence} Confidence`}
                </span>

                {currentResult.execution_engine && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                    ⚡ {currentResult.execution_engine}
                  </span>
                )}

                {currentResult.llm_provider && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                    🧠 {currentResult.llm_provider}
                  </span>
                )}

                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border">
                  Version: {currentResult.dataset_version}
                </span>

                {currentResult.execution_time_ms && (
                  <span className="text-[10px] text-[#64748B]">
                    {currentResult.execution_time_ms}ms
                  </span>
                )}
              </div>
            </div>

            {/* Text Answer */}
            <div
              className={`border rounded-xl p-4 text-xs leading-relaxed font-medium ${
                currentResult.status === 'error'
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : 'bg-[#EFF6FF] border-[#BFDBFE] text-[#1E3A8A]'
              }`}
            >
              <div className="flex items-start gap-2.5">
                {currentResult.status === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                ) : (
                  <Sparkles className="w-4 h-4 text-[#2563EB] shrink-0 mt-0.5" />
                )}
                <span>{renderFormattedText(currentResult.answer)}</span>
              </div>
            </div>

            {/* Column Lineage Explanation if lineage resolved ambiguity */}
            {(currentResult.selection_explanation || currentResult.evidence?.selection_explanation) && (
              <div className="bg-indigo-50/70 border border-indigo-200 rounded-xl px-4 py-2.5 text-xs text-indigo-900 flex items-center gap-2">
                <span className="font-semibold text-indigo-700">Column Lineage:</span>
                <span>{currentResult.selection_explanation || currentResult.evidence?.selection_explanation}</span>
              </div>
            )}

            {/* Grounded Analytical Evidence Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Operation</span>
                <span className="font-semibold text-slate-800 truncate block mt-0.5">
                  {currentResult.operation_performed || 'Analysis'}
                </span>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Dataset</span>
                <span className="font-semibold text-slate-800 truncate block mt-0.5" title={currentResult.dataset_name}>
                  {currentResult.dataset_name} ({currentResult.dataset_version})
                </span>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Columns Used</span>
                <span className="font-semibold text-slate-800 truncate block mt-0.5" title={currentResult.columns_used?.join(', ') || 'N/A'}>
                  {currentResult.columns_used?.length > 0 ? currentResult.columns_used.join(', ') : 'All Columns'}
                </span>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Filters Applied</span>
                <span className="font-semibold text-slate-800 truncate block mt-0.5">
                  {currentResult.filters_applied?.length > 0
                    ? currentResult.filters_applied.map(f => `${f.column} ${f.operator} ${f.value}`).join('; ')
                    : 'None'}
                </span>
              </div>
            </div>

            {/* Key Findings Bullet List */}
            {currentResult.key_points?.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <h4 className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">
                  Key Findings
                </h4>
                <ul className="space-y-1 text-xs text-[#0F172A]">
                  {currentResult.key_points.map((pt, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{renderFormattedText(pt)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Automated Data-Driven Insights Grid */}
            {currentResult.automated_insights?.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-[#F1F5F9]">
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-[#0F172A] uppercase tracking-wider">
                  <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
                  <span>Automated Data-Driven Insights</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {currentResult.automated_insights.map((ins, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="font-semibold text-slate-700">{ins.type}</span>
                        <span className={`px-1.5 py-0.5 rounded font-bold uppercase ${
                          ins.severity === 'High' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
                        }`}>
                          {ins.metric}
                        </span>
                      </div>
                      <p className="text-xs text-slate-800 leading-snug">{ins.statement}</p>
                      {ins.limitations && (
                        <p className="text-[10px] text-slate-500 italic">Limitation: {ins.limitations}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Statistical Diagnostics & Formula Breakdown */}
            {currentResult.statistical_metrics && (
              <details className="pt-2 border-t border-[#F1F5F9] text-xs group">
                <summary className="font-semibold text-[#0F172A] cursor-pointer hover:text-blue-600 flex items-center justify-between py-1">
                  <span>Statistical Diagnostics & Formula Breakdown</span>
                  <ChevronDown className="w-3.5 h-3.5 group-open:rotate-180 transition-transform text-slate-400" />
                </summary>
                <div className="mt-2 p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2">
                  {currentResult.statistical_metrics.regression && (
                    <div className="space-y-1">
                      <div className="font-semibold text-slate-900">Linear Regression Equation:</div>
                      <code className="px-2 py-1 bg-white border border-slate-300 rounded font-mono text-[11px] block">
                        {currentResult.statistical_metrics.regression.equation}
                      </code>
                      <div className="text-[11px] text-slate-600">
                        R² = {currentResult.statistical_metrics.regression.r_squared} | P-value = {currentResult.statistical_metrics.regression.p_value} | Std Error = {currentResult.statistical_metrics.regression.standard_error}
                      </div>
                    </div>
                  )}
                  {currentResult.statistical_metrics.hypothesis_test && (
                    <div className="space-y-1">
                      <div className="font-semibold text-slate-900">Hypothesis Test Comparison:</div>
                      <div className="text-[11px] text-slate-700">
                        {currentResult.statistical_metrics.hypothesis_test.interpretation}
                      </div>
                      <div className="text-[11px] text-slate-600">
                        T = {currentResult.statistical_metrics.hypothesis_test.t_statistic} | P = {currentResult.statistical_metrics.hypothesis_test.p_value} | Cohen's d = {currentResult.statistical_metrics.hypothesis_test.cohens_d}
                      </div>
                    </div>
                  )}
                  {currentResult.statistical_metrics.chi_square && (
                    <div className="space-y-1">
                      <div className="font-semibold text-slate-900">Chi-Square Test of Independence:</div>
                      <div className="text-[11px] text-slate-700">
                        {currentResult.statistical_metrics.chi_square.interpretation}
                      </div>
                      <div className="text-[11px] text-slate-600">
                        χ² = {currentResult.statistical_metrics.chi_square.chi2_statistic} | dof = {currentResult.statistical_metrics.chi_square.degrees_of_freedom} | Cramér's V = {currentResult.statistical_metrics.chi_square.cramers_v}
                      </div>
                    </div>
                  )}
                </div>
              </details>
            )}

            {/* Contextual Follow-Up Suggestions Chips */}
            {currentResult.follow_up_suggestions?.length > 0 && (
              <div className="pt-3 border-t border-[#F1F5F9] space-y-1.5">
                <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                  Suggested Follow-Up Inquiries (Contextual Memory Active)
                </div>
                <div className="flex flex-wrap gap-2">
                  {currentResult.follow_up_suggestions.map((fu, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setQuestion(fu);
                        handleAskQuestion(fu);
                      }}
                      disabled={isSubmitting}
                      className="px-3 py-1 bg-white border border-blue-200 hover:border-blue-400 hover:bg-blue-50 text-blue-700 text-xs font-medium rounded-lg shadow-2xs transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <span>{fu}</span>
                      <ArrowRight className="w-3 h-3 text-blue-500" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Evidence & Methodology Tags */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#F1F5F9] text-[11px] text-[#64748B]">
              <span className="font-semibold text-[#0F172A]">Calculation Trace:</span>
              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                Source: {currentResult.dataset_name} ({currentResult.dataset_version})
              </span>
              {currentResult.result && (
                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                  {currentResult.result.total_rows.toLocaleString()} records evaluated
                </span>
              )}
              {currentResult.limitations?.map((lim, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200"
                >
                  Notice: {lim}
                </span>
              ))}
            </div>
          </div>

          {/* Presentation Switcher Bar (when both chart and table are available) */}
          {currentResult.visualization?.recommended && currentResult.result?.rows?.length > 0 && (
            <div className="flex items-center justify-end gap-2 text-xs">
              <span className="text-[#64748B] font-medium text-[11px]">View Display:</span>
              <div className="flex items-center bg-white border border-[#E2E8F0] p-1 rounded-xl shadow-2xs">
                <button
                  type="button"
                  onClick={() => setViewMode('both')}
                  className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                    viewMode === 'both' ? 'bg-[#2563EB] text-white shadow-2xs' : 'text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  Both
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('chart')}
                  className={`px-3 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 cursor-pointer ${
                    viewMode === 'chart' ? 'bg-[#2563EB] text-white shadow-2xs' : 'text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  <BarChart3 className="w-3.5 h-3.5" />
                  <span>Chart</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('table')}
                  className={`px-3 py-1 rounded-lg font-semibold transition-all flex items-center gap-1 cursor-pointer ${
                    viewMode === 'table' ? 'bg-[#2563EB] text-white shadow-2xs' : 'text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  <span>Table</span>
                </button>
              </div>
            </div>
          )}

          {/* Visual Chart View */}
          {(viewMode === 'both' || viewMode === 'chart') && currentResult.visualization?.recommended && (
            <AnalyticalChart chartData={currentResult.visualization} />
          )}

          {/* Structured Result Table View */}
          {(viewMode === 'both' || viewMode === 'table' || !currentResult.visualization?.recommended) &&
            currentResult.result &&
            currentResult.result.rows &&
            currentResult.result.rows.length > 0 && (
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs space-y-3 p-5">
                <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
                  <div className="flex items-center gap-2">
                    <TableIcon className="w-4 h-4 text-[#2563EB]" />
                    <h4 className="text-xs font-bold text-[#0F172A]">Detailed Result Data</h4>
                  </div>
                  <span className="text-[11px] text-[#64748B] font-medium">
                    Showing {Math.min(currentResult.result.rows.length, 100)} of {currentResult.result.total_rows.toLocaleString()} rows
                  </span>
                </div>

                <div className="overflow-x-auto border border-[#E2E8F0] rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold uppercase text-[10px] tracking-wider">
                      <tr>
                        {currentResult.result.columns.map((col, idx) => (
                          <th key={idx} className="px-4 py-3 whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0] text-[#0F172A]">
                      {currentResult.result.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-[#F8FAFC] transition-colors">
                          {currentResult.result.columns.map((col, cIdx) => (
                            <td key={cIdx} className="px-4 py-3 whitespace-nowrap font-medium">
                              {row[col] !== null && row[col] !== undefined
                                ? String(row[col])
                                : <span className="text-slate-400 italic">null</span>}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
        </div>
      )}

      {/* QUERY HISTORY DRAWER / SIDEBAR */}
      {showHistory && (
        <div className="fixed inset-y-0 right-0 w-80 md:w-96 bg-white border-l border-[#E2E8F0] shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-200">
          <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#2563EB]" />
              <h3 className="text-xs font-bold text-[#0F172A]">Analytical Query History</h3>
            </div>
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 text-[#94A3B8] hover:text-[#0F172A] rounded-lg"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {history.length === 0 ? (
              <div className="py-12 text-center text-xs text-[#64748B] space-y-2">
                <Clock className="w-8 h-8 text-slate-300 mx-auto" />
                <p>No queries asked for this dataset yet.</p>
              </div>
            ) : (
              history.map((item) => (
                <div
                  key={item.id}
                  onClick={() => {
                    setQuestion(item.query);
                    handleAskQuestion(item.query);
                    setShowHistory(false);
                  }}
                  className="p-3 rounded-xl border border-[#E2E8F0] hover:border-[#2563EB] hover:bg-[#F8FAFC] transition-all cursor-pointer space-y-1.5 group text-xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-[#0F172A] group-hover:text-[#2563EB] leading-snug">
                      "{item.query}"
                    </span>
                    <button
                      onClick={(e) => handleDeleteHistoryItem(item.id, e)}
                      className="text-slate-300 hover:text-red-500 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Delete history item"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {item.answer_preview && (
                    <p className="text-[11px] text-[#64748B] line-clamp-2 leading-relaxed">
                      {item.answer_preview}
                    </p>
                  )}

                  <div className="flex items-center justify-between text-[10px] text-[#94A3B8] pt-1 border-t border-slate-100">
                    <span className="uppercase font-semibold">{item.analysis_type}</span>
                    <span>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          {history.length > 0 && (
            <div className="p-3 border-t border-[#E2E8F0]">
              <button
                type="button"
                onClick={handleClearHistory}
                className="w-full py-2 text-xs font-semibold text-red-600 hover:bg-red-50 rounded-xl transition-colors cursor-pointer"
              >
                Clear History
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AnalysisPage;
