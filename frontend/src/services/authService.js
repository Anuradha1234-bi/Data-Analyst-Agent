import api from './api';

export const authService = {
  async register(full_name, email, password, confirm_password) {
    const response = await api.post('/auth/register', {
      full_name,
      email,
      password,
      confirm_password,
    });
    return response.data;
  },

  async login(identifier, password, remember_me = false) {
    const trimmed = (identifier || '').trim();
    const response = await api.post('/auth/login', {
      email_or_username: trimmed,
      email: trimmed,
      password,
      remember_me,
    });
    return response.data;
  },

  async getMe() {
    const response = await api.get('/auth/me');
    return response.data;
  },

  async forgotPassword(email) {
    const response = await api.post('/auth/forgot-password', {
      email: email.trim().toLowerCase(),
    });
    return response.data;
  },

  async verifyResetToken(token) {
    const response = await api.get('/auth/verify-reset-token', {
      params: { token: token.trim() },
    });
    return response.data;
  },

  async resetPassword(token, new_password, confirm_password) {
    const response = await api.post('/auth/reset-password', {
      token: token.trim(),
      new_password,
      confirm_password,
    });
    return response.data;
  },

  async logout() {
    try {
      await api.post('/auth/logout');
    } catch {
      // Continue client cleanup even if network fails
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  },
};
