import api from './api';

export const profilingService = {
  /**
   * Retrieve statistical distribution profiling and data hygiene report for a dataset.
   * Supports both /datasets/{id}/profile and /profiling/{id}.
   */
  async getProfile(datasetId) {
    const response = await api.get(`/datasets/${datasetId}/profile`);
    return response.data;
  },

  /**
   * Batch profile multiple datasets simultaneously.
   */
  async batchProfile(datasetIds, mode = 'all') {
    const response = await api.post('/profiling/batch', {
      dataset_ids: datasetIds,
      mode,
    });
    return response.data;
  },
};

export default profilingService;
