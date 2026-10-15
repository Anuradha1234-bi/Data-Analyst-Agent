import React, { useState } from 'react';
import { UserPlus, User, Mail, Lock, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function Signup({ onNavigate }) {
  const { signup } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    const trimmedUsername = username.trim();
    const trimmedEmail = email.trim();

    // Client-side validations
    if (!trimmedUsername || !trimmedEmail || !password || !confirmPassword) {
      setErrorMessage('Please fill in all required fields.');
      return;
    }

    if (trimmedUsername.length < 3) {
      setErrorMessage('Username must be at least 3 characters long.');
      return;
    }

    // Basic email format check
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setErrorMessage('Please enter a valid email address.');
      return;
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    try {
      setIsSubmitting(true);
      const res = await signup({
        username: trimmedUsername,
        email: trimmedEmail,
        password,
      });

      setSuccessMessage(res.message || 'Account created successfully! Redirecting to login...');
      setTimeout(() => {
        if (onNavigate) {
          onNavigate('login');
        }
      }, 1200);
    } catch (err) {
      setErrorMessage(err.message || 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon-wrap">
            <UserPlus size={26} className="auth-header-icon" />
          </div>
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Register to begin analyzing datasets</p>
        </div>

        {errorMessage && (
          <div className="auth-error-banner" role="alert">
            <AlertCircle size={16} className="auth-error-icon" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="auth-success-banner" role="status">
            <CheckCircle2 size={16} className="auth-success-icon" />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="signup-username" className="form-label">
              Username
            </label>
            <div className="input-wrap">
              <User size={16} className="input-icon" />
              <input
                id="signup-username"
                type="text"
                autoComplete="username"
                className="form-input"
                placeholder="anu"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="signup-email" className="form-label">
              Email Address
            </label>
            <div className="input-wrap">
              <Mail size={16} className="input-icon" />
              <input
                id="signup-email"
                type="email"
                autoComplete="email"
                className="form-input"
                placeholder="anu@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="signup-password" className="form-label">
              Password (min 8 characters)
            </label>
            <div className="input-wrap">
              <Lock size={16} className="input-icon" />
              <input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="signup-confirm-password" className="form-label">
              Confirm Password
            </label>
            <div className="input-wrap">
              <Lock size={16} className="input-icon" />
              <input
                id="signup-confirm-password"
                type="password"
                autoComplete="new-password"
                className="form-input"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-auth-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="spin" />
                <span>Creating Account...</span>
              </>
            ) : (
              <>
                <UserPlus size={16} />
                <span>Sign Up</span>
              </>
            )}
          </button>
        </form>

        <div className="auth-footer">
          <span>Already have an account?</span>{' '}
          <button
            type="button"
            className="auth-link-btn"
            onClick={() => onNavigate && onNavigate('login')}
          >
            Sign In
          </button>
        </div>
      </div>
    </div>
  );
}
