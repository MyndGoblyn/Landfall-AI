import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../lib/api';

const AuthContext = createContext();

const getApiError = (error, fallback) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join(', ');
  }
  if (detail && typeof detail === 'object') {
    return detail.message || JSON.stringify(detail);
  }
  if (error.response?.status) {
    return `${fallback} (${error.response.status})`;
  }
  if (error.request) {
    return `${fallback}: unable to reach the API. Check the frontend API URL and backend CORS settings.`;
  }
  return fallback;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUser();
  }, []);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password, captchaToken) => {
    try {
      const response = await axios.post(`${API}/auth/login`, {
        email,
        password,
        captcha_token: captchaToken
      });
      setUser(response.data.user);
      return { success: true, message: response.data.message };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Login failed') };
    }
  };

  const register = async (email, password, captchaToken) => {
    try {
      const response = await axios.post(`${API}/auth/register`, {
        email,
        password,
        captcha_token: captchaToken
      });
      if (response.data.user) {
        setUser(response.data.user);
      }
      return {
        success: true,
        message: response.data.message,
        user: response.data.user,
        devLink: response.data.dev_link
      };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Registration failed') };
    }
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`);
    } catch (error) {
      console.error('Logout failed:', error);
    }
    setUser(null);
  };

  const resendVerification = async (email, captchaToken) => {
    try {
      const response = await axios.post(`${API}/auth/email/resend`, {
        email,
        captcha_token: captchaToken
      });
      return { success: true, message: response.data.message, devLink: response.data.dev_link };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Could not resend verification email') };
    }
  };

  const verifyEmail = async (verificationToken) => {
    try {
      const response = await axios.post(`${API}/auth/email/verify`, { token: verificationToken });
      setUser(response.data.user);
      return { success: true, message: response.data.message };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Email verification failed') };
    }
  };

  const forgotPassword = async (email, captchaToken) => {
    try {
      const response = await axios.post(`${API}/auth/password/forgot`, {
        email,
        captcha_token: captchaToken
      });
      return { success: true, message: response.data.message, devLink: response.data.dev_link };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Password reset request failed') };
    }
  };

  const resetPassword = async (resetToken, password, captchaToken) => {
    try {
      const response = await axios.post(`${API}/auth/password/reset`, {
        token: resetToken,
        password,
        captcha_token: captchaToken
      });
      setUser(response.data.user);
      return { success: true, message: response.data.message };
    } catch (error) {
      return { success: false, error: getApiError(error, 'Password reset failed') };
    }
  };

  const getAuthHeaders = () => ({});

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      register,
      logout,
      resendVerification,
      verifyEmail,
      forgotPassword,
      resetPassword,
      getAuthHeaders
    }}>
      {children}
    </AuthContext.Provider>
  );
};
