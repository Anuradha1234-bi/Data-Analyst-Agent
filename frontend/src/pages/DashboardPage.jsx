import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Database,
  UploadCloud,
  Sparkles,
  ShieldCheck,
  ArrowRight,
  Layers,
  FileSpreadsheet,
  Plus,
  RefreshCw,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';

export const DashboardPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [datasets, setDatasets] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  useEffect(() => {
    const loadDatasets = async () => {
      try {
        const data = await datasetService.getDatasets();
        setDatasets(data || []);
      } catch {
        setDatasets([]);
      } finally {
        setLoadingDatasets(false);
      }
    };

    loadDatasets();
  }, []);

  const displayName = user?.full_name || user?.name || 'Analyst';
  const totalDatasets = datasets.length;
  const totalRows = datasets.reduce(
    (acc, d) => acc + (d.row_count ?? d.rows ?? 0),
    0
  );

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
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };

  const recentDatasets = datasets.slice(0, 4);

  return (
    <div className="max-w-5xl mx-auto space-y-8 py-4">
      {/* Welcome Banner */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-8 shadow-xs relative overflow-hidden">
        <div className="relative z-10 space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#EFF6FF] border border-[#BFDBFE] text-[#1D4ED8] text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-[#2563EB]" />
            <span>AI Data Analyst Workspace</span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-[#0F172A]">
            Welcome, {displayName}
          </h1>

          <p className="text-sm text-[#64748B] max-w-xl leading-relaxed">
            Your dataset repository is active. Upload tabular files, manage schemas, and prepare your data pipeline.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-all cursor-pointer"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Dataset</span>
            </button>

            <button
              onClick={() => navigate('/datasets')}
              className="flex items-center gap-2 px-5 py-2.5 bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] text-xs font-semibold rounded-xl shadow-xs transition-all cursor-pointer"
            >
              <Database className="w-4 h-4 text-[#2563EB]" />
              <span>View Datasets ({totalDatasets})</span>
            </button>
          </div>
        </div>

        {/* Decorative background element */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-[#EFF6FF]/60 to-transparent pointer-events-none hidden md:block" />
      </div>

      {/* Real Statistics Overview Cards (Section 17 Requirements) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {/* Total Datasets */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#64748B]">Total Datasets</span>
            <div className="p-2 rounded-lg bg-[#EFF6FF] text-[#2563EB]">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-[#0F172A]">
            {loadingDatasets ? (
              <RefreshCw className="w-5 h-5 text-[#94A3B8] animate-spin" />
            ) : (
              totalDatasets
            )}
          </div>
          <div className="mt-1 text-[11px] text-[#2563EB] font-medium">
            {totalDatasets === 1 ? '1 active file' : `${totalDatasets} active files`}
          </div>
        </div>

        {/* Total Records / Rows */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#64748B]">Total Rows Ingested</span>
            <div className="p-2 rounded-lg bg-emerald-50 text-[#16A34A]">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-[#0F172A]">
            {loadingDatasets ? (
              <RefreshCw className="w-5 h-5 text-[#94A3B8] animate-spin" />
            ) : (
              totalRows.toLocaleString()
            )}
          </div>
          <div className="mt-1 text-[11px] text-[#16A34A] font-medium">
            Available across all datasets
          </div>
        </div>

        {/* Active Account Status */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#64748B]">Active Account</span>
            <div className="p-2 rounded-lg bg-emerald-50 text-[#16A34A]">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 text-base font-bold text-[#0F172A] truncate">
            {user?.email || 'Authenticated'}
          </div>
          <div className="mt-1 text-[11px] text-[#16A34A] font-medium">
            JWT Session Active
          </div>
        </div>
      </div>

      {/* Recent Datasets Section (Section 17 Requirements) */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-[#E2E8F0]">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-[#2563EB]" />
            <h2 className="text-sm font-bold text-[#0F172A]">Recent Datasets</h2>
          </div>
          {datasets.length > 0 && (
            <button
              onClick={() => navigate('/datasets')}
              className="text-xs font-semibold text-[#2563EB] hover:underline flex items-center gap-1 cursor-pointer"
            >
              <span>View all ({totalDatasets})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {loadingDatasets ? (
          <div className="py-8 text-center text-xs text-[#64748B] flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-[#2563EB]" />
            <span>Loading datasets...</span>
          </div>
        ) : datasets.length === 0 ? (
          <div className="py-8 text-center space-y-3">
            <p className="text-xs text-[#64748B]">
              No datasets uploaded yet. Upload your first CSV or Excel file to get started.
            </p>
            <button
              onClick={() => navigate('/upload')}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Upload Dataset</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-[#E2E8F0]">
            {recentDatasets.map((dataset) => {
              const fname = dataset.original_filename || dataset.filename;
              const ftype = (dataset.file_type || '').toUpperCase();
              const rowCount = dataset.row_count ?? dataset.rows ?? 0;
              const colCount = dataset.column_count ?? dataset.columns ?? 0;
              const fsize = dataset.file_size ?? dataset.file_size_bytes ?? 0;

              return (
                <div
                  key={dataset.id}
                  className="py-3 flex items-center justify-between gap-4 hover:bg-[#F8FAFC] px-2 rounded-xl transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-lg bg-[#EFF6FF] text-[#2563EB] shrink-0">
                      <FileSpreadsheet className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div
                        onClick={() => navigate('/datasets')}
                        className="text-xs font-semibold text-[#0F172A] hover:text-[#2563EB] cursor-pointer truncate max-w-sm"
                        title={fname}
                      >
                        {fname}
                      </div>
                      <div className="text-[11px] text-[#64748B] mt-0.5">
                        {rowCount.toLocaleString()} rows · {colCount} cols ·{' '}
                        {formatFileSize(fsize)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        ftype === 'CSV'
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : ftype === 'XLSX'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                      }`}
                    >
                      {ftype}
                    </span>
                    <span className="text-[11px] text-[#94A3B8] hidden sm:inline">
                      {formatDate(dataset.created_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
