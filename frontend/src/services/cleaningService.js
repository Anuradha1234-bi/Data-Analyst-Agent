import api from './api';

export const cleaningService = {
  /**
   * Retrieve cleaning diagnostics, column options, and duplicate/empty previews.
   */
  async getCleaningOverview(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}`);
    return response.data;
  },

  /**
   * Alias for getCleaningOverview.
   */
  async getOverview(datasetId) {
    return this.getCleaningOverview(datasetId);
  },

  /**
   * Compute a dry-run preview of cleaning transformations without mutating disk.
   */
  async previewCleaning(datasetId, operations) {
    const response = await api.post(`/cleaning/${datasetId}/preview`, operations);
    return response.data;
  },

  /**
   * Apply cleaning pipeline, persist versioned cleaned file, and record audit log.
   */
  async applyCleaning(datasetId, operations) {
    const response = await api.post(`/cleaning/${datasetId}/apply`, operations);
    return response.data;
  },

  /**
   * Fetch historical cleaning runs for this dataset.
   */
  async getCleaningHistory(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/history`);
    return response.data;
  },

  /**
   * Alias for getCleaningHistory.
   */
  async getHistory(datasetId) {
    return this.getCleaningHistory(datasetId);
  },

  /**
   * Download the versioned cleaned dataset file in CSV or Excel format.
   */
  async downloadCleanedDataset(datasetId, filename, format = 'csv') {
    const response = await api.get(`/cleaning/${datasetId}/download`, {
      params: { format },
      responseType: 'blob',
    });

    const isExcel = format === 'excel' || format === 'xlsx';
    const mime = isExcel
      ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      : 'text/csv';
    const ext = isExcel ? 'xlsx' : 'csv';

    const blob = new Blob([response.data], { type: mime });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename || `cleaned_dataset_${datasetId}.${ext}`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Helper to download cleaned dataset in Excel format.
   */
  async downloadCleanedExcel(datasetId, filename) {
    return this.downloadCleanedDataset(datasetId, filename, 'excel');
  },

  /**
   * Reset cleaned dataset state back to original.
   */
  async resetCleanedDataset(datasetId) {
    const response = await api.post(`/cleaning/${datasetId}/reset`);
    return response.data;
  },

  /**
   * Phase 2: Retrieve unique values, frequencies, and percentages for a column.
   */
  async getColumnValueSummary(datasetId, column) {
    const response = await api.get(`/cleaning/${datasetId}/column-summary`, {
      params: { column },
    });
    return response.data;
  },

  /**
   * Phase 2: Detect potentially equivalent/inconsistent category clusters for a column.
   */
  async getCategoryInconsistencies(datasetId, column) {
    const response = await api.get(`/cleaning/${datasetId}/category-inconsistencies`, {
      params: { column },
    });
    return response.data;
  },

  /**
   * Phase 2: Inspect date parsing diagnostics and format detection for a column.
   */
  async inspectDateColumn(datasetId, column) {
    const response = await api.get(`/cleaning/${datasetId}/date-inspection`, {
      params: { column },
    });
    return response.data;
  },

  // =========================================================================
  // Phase 4: Professional Cleaning Workflow, Validation, Score, & Report
  // =========================================================================

  /**
   * Phase 4: Retrieve compact summary with cleaning score, issue counts, and status.
   */
  async getDashboardSummary(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/dashboard-summary`);
    return response.data;
  },

  /**
   * Phase 4: Run Before vs After hygiene checks and return validation report.
   */
  async getValidationReport(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/validation`);
    return response.data;
  },

  /**
   * Phase 4: Dry-run preview of chained bulk cleaning operations with impact summary.
   */
  async bulkPreview(datasetId, operations) {
    const response = await api.post(`/cleaning/${datasetId}/bulk-preview`, operations);
    return response.data;
  },

  /**
   * Alias for bulkPreview.
   */
  async previewBulkOperations(datasetId, operations) {
    return this.bulkPreview(datasetId, operations);
  },

  /**
   * Phase 4: Atomically apply all queued cleaning operations and create version snapshot.
   */
  async bulkApply(datasetId, operations) {
    const response = await api.post(`/cleaning/${datasetId}/bulk-apply`, operations);
    return response.data;
  },

  /**
   * Phase 4: Fetch timeline of dataset versions from Original to latest Cleaned.
   */
  async getVersionTimeline(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/versions`);
    return response.data;
  },

  /**
   * Phase 4: Restore dataset to any historical version or back to Original.
   */
  async restoreVersion(datasetId, versionTag) {
    const response = await api.post(`/cleaning/${datasetId}/versions/${versionTag}/restore`);
    return response.data;
  },

  /**
   * Phase 4: Generate structured cleaning report with operations log, validation, and score.
   */
  async getCleaningReport(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/report`);
    return response.data;
  },

  /**
   * Phase 4: Download comprehensive cleaning report (markdown, csv, or json).
   */
  async downloadCleaningReport(datasetId, format = 'markdown', filename) {
    const response = await api.get(`/cleaning/${datasetId}/report/download`, {
      params: { format },
      responseType: 'blob',
    });

    const mimeMap = {
      markdown: 'text/markdown',
      csv: 'text/csv',
      json: 'application/json',
    };
    const extMap = {
      markdown: 'md',
      csv: 'csv',
      json: 'json',
    };

    const mime = mimeMap[format] || 'text/plain';
    const ext = extMap[format] || 'txt';

    const blob = new Blob([response.data], { type: mime });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename || `cleaning_report_${datasetId}.${ext}`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Phase 4: Retrieve sample preview of original uncleaned dataset (Previous CSV).
   */
  async getOriginalPreview(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/original-preview`);
    return response.data;
  },

  // =========================================================================
  // Phase 5: Smart Cleaning Suggestions, Consistency Checks, & Version Compare
  // =========================================================================

  /**
   * Phase 5: Generate intelligent, data-driven cleaning suggestions grouped by priority.
   */
  async getSmartSuggestions(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/suggestions`);
    return response.data;
  },

  /**
   * Phase 5: Run cross-column relationship and consistency checks.
   */
  async getConsistencyChecks(datasetId) {
    const response = await api.get(`/cleaning/${datasetId}/consistency`);
    return response.data;
  },

  /**
   * Phase 5: Evaluate a user-defined cross-column consistency rule.
   */
  async evaluateCustomRule(datasetId, ruleConfig) {
    const response = await api.post(`/cleaning/${datasetId}/consistency/custom-rule`, ruleConfig);
    return response.data;
  },

  /**
   * Phase 4/5: Compare two historical dataset versions.
   */
  async compareVersions(datasetId, v1, v2) {
    const response = await api.get(`/cleaning/${datasetId}/versions/compare`, {
      params: { v1, v2 },
    });
    return response.data;
  },
};

export default cleaningService;

