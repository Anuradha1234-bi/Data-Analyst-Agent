import api from './api';

export const predictionService = {
  /**
   * Check prediction service readiness.
   */
  async getStatus() {
    const response = await api.get('/prediction/status');
    return response.data;
  },

  /**
   * Retrieve catalog of supported predictive models.
   */
  async getCandidateModels() {
    const response = await api.get('/prediction/models');
    return response.data;
  },

  /**
   * Run pre-flight diagnostic analysis on a dataset.
   */
  async analyzeDataset({ dataset_id, target_column, date_column, mode = 'auto' }) {
    const response = await api.post('/prediction/analyze', {
      dataset_id,
      target_column,
      date_column,
      mode,
    });
    return response.data;
  },

  /**
   * Train models and persist run.
   */
  async trainModel(payload) {
    const response = await api.post('/prediction/train', payload);
    return response.data;
  },

  /**
   * Retrieve prediction history runs.
   */
  async getRuns(datasetId = null) {
    const params = datasetId ? { dataset_id: datasetId } : {};
    const response = await api.get('/prediction/runs', { params });
    return response.data;
  },

  /**
   * Retrieve full details of a specific prediction run.
   */
  async getRunDetail(runId) {
    const response = await api.get(`/prediction/runs/${runId}`);
    return response.data;
  },

  /**
   * Delete a saved prediction run.
   */
  async deleteRun(runId) {
    const response = await api.delete(`/prediction/runs/${runId}`);
    return response.data;
  },

  /**
   * Download predictions as a CSV file.
   */
  async downloadPredictionsCsv(runId, filename) {
    const response = await api.get(`/prediction/runs/${runId}/export/csv`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename || `predictions_run_${runId}.csv`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Download full model evaluation report in Markdown format.
   */
  async downloadEvaluationReport(runId, filename) {
    const response = await api.get(`/prediction/runs/${runId}/export/report`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename || `model_report_run_${runId}.md`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Predict on newly uploaded tabular file using a trained model pipeline.
   */
  async predictNewData(runId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/prediction/runs/${runId}/predict`, formData, {
      headers: {
        'Content-Type': undefined,
      },
    });
    return response.data;
  },
};

export default predictionService;
