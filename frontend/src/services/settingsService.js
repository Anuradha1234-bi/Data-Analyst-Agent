import api from './api';

export const settingsService = {
  /**
   * Retrieve complete settings overview including user preferences, system configuration,
   * workspace storage usage, available providers, and notification channels.
   */
  async getSettingsOverview() {
    const response = await api.get('/settings/');
    return response.data;
  },

  /**
   * Update the authenticated user's personal preferences.
   * @param {Object} preferences
   */
  async updateUserPreferences(preferences) {
    const response = await api.put('/settings/user-preferences', preferences);
    return response.data;
  },

  /**
   * Update system-wide configuration (requires administrator role).
   * @param {Object} systemSettings
   */
  async updateSystemSettings(systemSettings) {
    const response = await api.put('/settings/system', systemSettings);
    return response.data;
  },

  /**
   * Test connection to Google Gemini API using configured or provided key.
   * @param {string} [testKey]
   */
  async testGeminiKey(testKey) {
    const response = await api.post('/settings/test-gemini', {
      test_key: testKey || null,
    });
    return response.data;
  },

  /**
   * Test notification channel readiness.
   */
  async testNotification() {
    const response = await api.post('/settings/test-notification');
    return response.data;
  },

  /**
   * Retrieve real-time workspace storage metrics for the current user.
   */
  async getWorkspaceStorage() {
    const response = await api.get('/settings/storage');
    return response.data;
  },
};

export default settingsService;
