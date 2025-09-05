
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

interface AuthContextType {
  token: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('adminToken'));

  // Check if token is expired
  const isTokenValid = (token: string): boolean => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp > currentTime;
    } catch {
      return false;
    }
  };

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await axios.post('/api/admin/login', {
        username,
        password
      });

      if (response.data.access_token) {
        const newToken = response.data.access_token;
        setToken(newToken);
        localStorage.setItem('adminToken', newToken);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Login failed:', error);
      return false;
    }
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem('adminToken');
  };

  const isAuthenticated = !!token && isTokenValid(token);

  // Auto-logout if token is expired
  React.useEffect(() => {
    if (token && !isTokenValid(token)) {
      logout();
    }
  }, [token]);

  // Set up axios interceptor for authentication
  useEffect(() => {
    const interceptor = axios.interceptors.request.use(
      (config) => {
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    const responseInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          logout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.request.eject(interceptor);
      axios.interceptors.response.eject(responseInterceptor);
    };
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
};
