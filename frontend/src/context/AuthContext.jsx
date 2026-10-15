import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(true);

  // Initialize and verify authentication state on mount
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          // Verify with backend and initialize fresh profile
          const userProfile = await authService.getMe();
          setUser(userProfile);
          localStorage.setItem('user', JSON.stringify(userProfile));
        } catch {
          // Token expired or invalid
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (identifier, password, rememberMe = false) => {
    // 1. Authenticate with backend
    const loginData = await authService.login(identifier, password, rememberMe);
    const accessToken = loginData.access_token;

    setToken(accessToken);
    localStorage.setItem('token', accessToken);

    // 2. Call GET /api/auth/me to initialize authenticated state
    try {
      const userProfile = await authService.getMe();
      setUser(userProfile);
      localStorage.setItem('user', JSON.stringify(userProfile));
      return { token: accessToken, user: userProfile };
    } catch {
      // Fallback to returned login user if /me fails unexpectedly
      setUser(loginData.user);
      localStorage.setItem('user', JSON.stringify(loginData.user));
      return { token: accessToken, user: loginData.user };
    }
  };

  const register = async (fullName, email, password, confirmPassword) => {
    const data = await authService.register(fullName, email, password, confirmPassword);
    return data;
  };

  const forgotPassword = async (email) => {
    return await authService.forgotPassword(email);
  };

  const verifyResetToken = async (token) => {
    return await authService.verifyResetToken(token);
  };

  const resetPassword = async (token, newPassword, confirmPassword) => {
    return await authService.resetPassword(token, newPassword, confirmPassword);
  };

  const logout = async () => {
    await authService.logout();
    setToken(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isLoading,
    loading: isLoading, // Convenient alias
    login,
    register,
    forgotPassword,
    verifyResetToken,
    resetPassword,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
