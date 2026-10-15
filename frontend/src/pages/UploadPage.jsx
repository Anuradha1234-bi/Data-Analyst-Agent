import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  UploadCloud,
  FileSpreadsheet,
  Trash2,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  X,
  RefreshCw,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { extractErrorMessage } from '../services/api';

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];

export const UploadPage = () => {
  const [fileList, setFileList] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [generalError, setGeneralError] = useState('');
  const [uploadSummary, setUploadSummary] = useState(null);

  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const validateFile = (file) => {
    const ext = `.${file.name.split('.').pop().toLowerCase()}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return 'This file type is not supported. Supported formats: CSV, XLSX, XLS.';
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return 'The file is too large. Maximum allowed size is 50 MB.';
    }
    if (file.size === 0) {
      return 'The file is empty (0 bytes). Please provide a file with data.';
    }
    return null;
  };

  const handleAddFiles = (newRawFiles) => {
    setGeneralError('');
    setUploadSummary(null);

    const newEntries = Array.from(newRawFiles).map((file) => {
      const validationError = validateFile(file);
      return {
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        file,
        name: file.name,
        size: file.size,
        status: validationError ? 'error' : 'pending',
        error: validationError,
      };
    });

    setFileList((prev) => [...prev, ...newEntries]);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleAddFiles(e.target.files);
      e.target.value = '';
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(e.dataTransfer.files);
    }
  };

  const removeFile = (id) => {
    setFileList((prev) => prev.filter((item) => item.id !== id));
  };

  const clearAll = () => {
    setFileList([]);
    setGeneralError('');
    setUploadSummary(null);
  };

  const handleUploadAll = async () => {
    setGeneralError('');
    setUploadSummary(null);

    // Filter valid files that are not yet uploaded
    const filesToUpload = fileList.filter(
      (item) => item.status === 'pending' || (item.status === 'error' && !validateFile(item.file))
    );

    if (filesToUpload.length === 0) {
      setGeneralError('No valid files ready for upload. Please add CSV, XLSX, or XLS files.');
      return;
    }

    // Set status to uploading for selected files
    setFileList((prev) =>
      prev.map((item) =>
        filesToUpload.some((target) => target.id === item.id)
          ? { ...item, status: 'uploading', error: null }
          : item
      )
    );

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const rawFiles = filesToUpload.map((item) => item.file);
      const res = await datasetService.uploadDatasets(rawFiles, (percent) => {
        setUploadProgress(percent);
      });

      const uploadedNames = new Set(
        (res.uploaded || []).map((d) => d.original_filename || d.filename)
      );
      const failedMap = new Map();
      (res.failed || []).forEach((f) => {
        failedMap.set(f.filename, f.error);
      });

      // Update item statuses based on server response
      setFileList((prev) =>
        prev.map((item) => {
          if (uploadedNames.has(item.name)) {
            return { ...item, status: 'uploaded', error: null };
          }
          if (failedMap.has(item.name)) {
            return {
              ...item,
              status: 'error',
              error: failedMap.get(item.name) || 'Unable to upload the file.',
            };
          }
          return item;
        })
      );

      setUploadSummary({
        totalUploaded: res.total_uploaded || (res.uploaded ? res.uploaded.length : 0),
        totalFailed: res.total_failed || (res.failed ? res.failed.length : 0),
      });
    } catch (err) {
      const friendlyMsg = extractErrorMessage(err);
      setGeneralError(friendlyMsg);
      // Revert uploading status to error on failure
      setFileList((prev) =>
        prev.map((item) =>
          item.status === 'uploading'
            ? { ...item, status: 'error', error: friendlyMsg }
            : item
        )
      );
    } finally {
      setIsUploading(false);
    }
  };

  const hasPending = fileList.some((item) => item.status === 'pending');
  const hasUploaded = fileList.some((item) => item.status === 'uploaded');

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#0F172A]">Upload Dataset</h1>
          <p className="text-xs text-[#64748B] mt-1">
            Ingest tabular datasets securely into your private analytics environment.
          </p>
        </div>
        <Link
          to="/datasets"
          className="text-xs font-semibold text-[#2563EB] hover:underline flex items-center gap-1.5"
        >
          <span>View My Datasets</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* General Error Banner */}
      {generalError && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{generalError}</span>
        </div>
      )}

      {/* Upload Success Summary Banner */}
      {uploadSummary && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between ${
            uploadSummary.totalFailed === 0
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-amber-50 border-amber-200 text-amber-900'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle2
              className={`w-4 h-4 shrink-0 ${
                uploadSummary.totalFailed === 0 ? 'text-emerald-600' : 'text-amber-600'
              }`}
            />
            <span>
              {uploadSummary.totalUploaded}{' '}
              {uploadSummary.totalUploaded === 1 ? 'dataset' : 'datasets'} uploaded successfully.
              {uploadSummary.totalFailed > 0 &&
                ` (${uploadSummary.totalFailed} file failed to process)`}
            </span>
          </div>
          <button
            onClick={() => navigate('/datasets')}
            className="px-3 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
          >
            Go to My Datasets
          </button>
        </div>
      )}

      {/* Drag & Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-2xl p-10 text-center transition-all ${
          isDragging
            ? 'border-[#2563EB] bg-[#EFF6FF]'
            : 'border-[#CBD5E1] bg-white hover:border-[#2563EB]'
        }`}
      >
        <div className="inline-flex p-3 rounded-2xl bg-[#EFF6FF] text-[#2563EB] mb-3">
          <UploadCloud className="w-8 h-8" />
        </div>
        <h3 className="text-sm font-bold text-[#0F172A]">
          Drag & drop your CSV or Excel files here
        </h3>
        <p className="text-xs text-[#64748B] mt-1">or</p>

        <div className="mt-3">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls"
            onChange={handleFileInputChange}
            className="hidden"
            id="dataset-file-input"
            disabled={isUploading}
          />
          <button
            type="button"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
            className="px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Browse Files
          </button>
        </div>

        <div className="mt-4 flex items-center justify-center gap-6 text-[11px] text-[#64748B]">
          <span>
            Supported: <strong className="text-[#0F172A]">CSV, XLSX, XLS</strong>
          </span>
          <span>•</span>
          <span>
            Maximum size: <strong className="text-[#0F172A]">50 MB</strong> per file
          </span>
        </div>
      </div>

      {/* Selected Files Section */}
      {fileList.length > 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#E2E8F0]">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-[#0F172A]">Selected Files</h2>
              <span className="px-2 py-0.5 rounded-full bg-[#EFF6FF] text-[#2563EB] text-[11px] font-semibold">
                {fileList.length}
              </span>
            </div>
            <button
              onClick={clearAll}
              disabled={isUploading}
              className="text-xs text-[#64748B] hover:text-red-600 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Clear All
            </button>
          </div>

          {/* Progress bar when uploading */}
          {isUploading && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-[#64748B]">
                <span>Uploading datasets to secure storage...</span>
                <span className="font-semibold text-[#2563EB]">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                <div
                  className="bg-[#2563EB] h-2 transition-all duration-300 rounded-full"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* File Rows */}
          <div className="divide-y divide-[#E2E8F0]">
            {fileList.map((item) => (
              <div
                key={item.id}
                className="py-3 flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`p-2 rounded-lg shrink-0 ${
                      item.status === 'uploaded'
                        ? 'bg-emerald-50 text-emerald-600'
                        : item.status === 'error'
                        ? 'bg-red-50 text-red-600'
                        : 'bg-[#EFF6FF] text-[#2563EB]'
                    }`}
                  >
                    <FileSpreadsheet className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[#0F172A] truncate">
                      {item.name}
                    </div>
                    <div className="text-[11px] text-[#64748B]">
                      {formatFileSize(item.size)}
                    </div>
                    {item.error && (
                      <div className="text-[11px] text-red-600 mt-0.5 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        <span>{item.error}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {/* Status Badges */}
                  {item.status === 'uploading' && (
                    <div className="flex items-center gap-1.5 text-xs text-[#2563EB]">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Uploading...</span>
                    </div>
                  )}

                  {item.status === 'uploaded' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Uploaded</span>
                    </span>
                  )}

                  {item.status === 'error' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-50 text-red-700 text-xs font-medium border border-red-200">
                      <X className="w-3.5 h-3.5 text-red-600" />
                      <span>Failed</span>
                    </span>
                  )}

                  {/* Remove Button */}
                  {!isUploading && (
                    <button
                      onClick={() => removeFile(item.id)}
                      className="p-1.5 text-[#94A3B8] hover:text-red-600 transition-colors cursor-pointer"
                      title="Remove file"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="px-4 py-2.5 border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold rounded-xl transition-colors cursor-pointer disabled:opacity-60"
            >
              Add more files
            </button>

            <button
              type="button"
              onClick={handleUploadAll}
              disabled={isUploading || (!hasPending && !fileList.some((f) => f.status === 'error'))}
              className="px-6 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <span>Upload All Files</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
