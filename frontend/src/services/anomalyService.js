import api from './api';

export const anomalyService = {
  /**
   * Fetch suitable numerical columns for outlier detection on a dataset version.
   * @param {number} datasetId
   * @param {'original'|'cleaned'} version
   */
  async getNumericColumns(datasetId, version = 'original') {
    const response = await api.get(`/anomalies/${datasetId}/columns`, {
      params: { version },
    });
    return response.data;
  },

  /**
   * Run univariate IQR, multivariate Isolation Forest, or combined outlier detection.
   * @param {Object} params
   * @param {number} params.dataset_id
   * @param {'original'|'cleaned'} [params.version='original']
   * @param {'iqr'|'isolation_forest'|'both'} [params.method='both']
   * @param {string[]} [params.columns]
   * @param {number} [params.multiplier=1.5]
   * @param {number} [params.contamination=0.05]
   * @param {number} [params.random_state=42]
   */
  async detectAnomalies(params) {
    const response = await api.post('/anomalies/detect', params);
    return response.data;
  },
};

export default anomalyService;
