import api from './api';

/**
 * Service for Help & Support inquiries and status checking.
 */
export const supportService = {
  /**
   * Submit a support inquiry / contact message to dataanalystagent@gmail.com.
   *
   * @param {Object} payload
   * @param {string} payload.fullName - Full name of the sender
   * @param {string} payload.email - Valid sender email address
   * @param {string} payload.subject - Inquiry subject
   * @param {string} payload.message - Inquiry message content
   * @returns {Promise<{ success: boolean, message: string }>}
   */
  async submitContactMessage({ fullName, email, subject, message }) {
    const response = await api.post('/support/contact', {
      full_name: fullName.trim(),
      email: email.trim().toLowerCase(),
      subject: subject.trim(),
      message: message.trim(),
    });
    return response.data;
  },

  /**
   * Check support delivery readiness (support email, helpline, and SMTP configuration).
   *
   * @returns {Promise<{ support_email: string, helpline: string, smtp_configured: boolean }>}
   */
  async getSupportStatus() {
    const response = await api.get('/support/status');
    return response.data;
  },
};

export default supportService;
