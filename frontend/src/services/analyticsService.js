import api from './api';

export const analyticsService = {
  /**
   * Retrieve dynamic dataset overview, schema profiling, and calculated KPIs.
   */
  async getOverview(datasetId, version = 'original') {
    const response = await api.get(`/analytics/overview/${datasetId}`, {
      params: { version },
    });
    return response.data;
  },

  /**
   * Generate interactive chart visualization and matching tabular data with custom filters.
   */
  async generateChart(chartRequest) {
    const response = await api.post('/analytics/chart', chartRequest);
    return response.data;
  },

  /**
   * Analyze chronological time-series trends with interval aggregation and period comparison.
   */
  async analyzeTrend(trendRequest) {
    const response = await api.post('/analytics/trend', trendRequest);
    return response.data;
  },

  /**
   * Multidimensional group-by aggregation and comparative evaluation table.
   */
  async groupCompare(compareRequest) {
    const response = await api.post('/analytics/group-compare', compareRequest);
    return response.data;
  },

  /**
   * Retrieve deep descriptive statistics, Pearson correlation matrix, and IQR outliers.
   */
  async getStats(statsRequest) {
    const response = await api.post('/analytics/stats', statsRequest);
    return response.data;
  },

  /**
   * Extract automated evidence-grounded insights and concentration patterns.
   */
  async getInsights(datasetId, version = 'original') {
    const response = await api.get(`/analytics/insights/${datasetId}`, {
      params: { version },
    });
    return response.data;
  },

  /**
   * Download table data as a structured CSV file with UTF-8 BOM.
   */
  async downloadCSV(filename, columns, rows) {
    const response = await api.post(
      '/analytics/export/csv',
      {
        filename: filename || 'analytics_export.csv',
        columns,
        rows,
      },
      {
        responseType: 'blob',
      }
    );

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename.endsWith('.csv') ? filename : `${filename}.csv`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Generate and retrieve structured executive analytics summary report.
   */
  async generateReport(reportRequest) {
    const response = await api.post('/analytics/export/report', reportRequest);
    return response.data;
  },
};

export default analyticsService;
