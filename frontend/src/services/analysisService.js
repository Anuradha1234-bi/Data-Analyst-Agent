import api from './api';

export const analysisService = {
  /**
   * Submit a natural language analytical question against a dataset and version.
   */
  async askQuestion(datasetId, question, version = 'original', context = null) {
    const response = await api.post('/analysis/ask', {
      dataset_id: datasetId,
      question,
      version,
      context,
    });
    return response.data;
  },

  /**
   * Fetch contextually relevant suggested questions based on the dataset's actual schema.
   */
  async getSuggestedQuestions(datasetId) {
    const response = await api.get(`/analysis/suggested-questions/${datasetId}`);
    return response.data;
  },

  /**
   * Fetch analytical query history, optionally filtered by dataset ID.
   */
  async getHistory(datasetId = null, limit = 50) {
    const params = { limit };
    if (datasetId) params.dataset_id = datasetId;
    const response = await api.get('/analysis/history', { params });
    return response.data;
  },

  /**
   * Delete a single history entry.
   */
  async deleteHistoryItem(historyId) {
    const response = await api.delete(`/analysis/history/${historyId}`);
    return response.data;
  },

  /**
   * Clear all query history for user, optionally filtered by dataset.
   */
  async clearHistory(datasetId = null) {
    const params = {};
    if (datasetId) params.dataset_id = datasetId;
    const response = await api.post('/analysis/history/clear', null, { params });
    return response.data;
  },

  /**
   * Reset bounded multi-turn conversational memory for a dataset.
   */
  async clearContext(datasetId) {
    const response = await api.post('/analysis/context/clear', null, {
      params: { dataset_id: datasetId },
    });
    return response.data;
  },
};

export default analysisService;
