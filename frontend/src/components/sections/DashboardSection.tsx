import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';

interface Employee {
  username: string;
  hostname: string;
  status: string;
  last_seen: string;
  public_ip: string;
  city: string;
  state: string;
  country: string;
}

const DashboardSection: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { logout, isAuthenticated, isInitialized } = useAuth();

  useEffect(() => {
    if (isInitialized && isAuthenticated) {
      loadDashboardData();
      const interval = setInterval(loadDashboardData, 30000);
      return () => clearInterval(interval);
    }
  }, [isInitialized, isAuthenticated]);

  const loadDashboardData = async () => {
    try {
      setError(null);
      const token = localStorage.getItem('token');
      if (!token) {
        logout();
        return;
      }
      
      const response = await axios.get('/api/admin/employees/status', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setEmployees(response.data.employees || []);
    } catch (error: any) {
      console.error('Failed to load dashboard data:', error);
      if (error.response?.status === 401) {
        logout();
      } else if (error.response?.status === 403) {
        setError('Access denied. Please check your authentication.');
      } else if (error.response?.status === 500) {
        setError('Server error. Database might be initializing. Please wait a moment and try again.');
      } else {
        setError('Failed to load dashboard data. Please check your network connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '24px', marginBottom: '10px' }}>⏳</div>
          <div>Loading dashboard data...</div>
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{
            background: '#f8d7da',
            color: '#721c24',
            padding: '20px',
            borderRadius: '8px',
            marginBottom: '20px'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '10px' }}>⚠️</div>
            <div>{error}</div>
          </div>
          <button
            onClick={loadDashboardData}
            style={{
              background: '#007bff',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '5px',
              cursor: 'pointer'
            }}
          >
            🔄 Retry
          </button>
        </div>
      ) : (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <h3>{employees.length}</h3>
              <p>Total Employees</p>
            </div>
            <div className="stat-card">
              <h3>{employees.filter(emp => emp.status === 'online').length}</h3>
              <p>Online Now</p>
            </div>
            <div className="stat-card">
              <h3>{employees.filter(emp => emp.status === 'offline').length}</h3>
              <p>Offline</p>
            </div>
            <div className="stat-card">
              <h3>
                {employees.length > 0
                  ? Math.round((employees.filter(emp => emp.status === 'online').length / employees.length) * 100)
                  : 0}%
              </h3>
              <p>Online Rate</p>
            </div>
          </div>

          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '20px'
          }}>
            <h3>Recent Employee Activity</h3>
            <button
              onClick={loadDashboardData}
              style={{
                background: '#28a745',
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🔄 Refresh
            </button>
          </div>

          {employees.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '40px',
              background: '#f8f9fa',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>👥</div>
              <h4>No Employee Data</h4>
              <p>No employees are currently being monitored. Install the agent on employee computers to start tracking.</p>
            </div>
          ) : (
            <div className="employee-list">
              {employees.map(emp => (
                <div key={emp.username} className="employee-card">
                  <div className="employee-info">
                    <strong>{emp.username}</strong> ({emp.hostname})
                    <br />
                    <small>🌐 {emp.public_ip}</small>
                    <br />
                    <small>📍 {emp.city}, {emp.state}, {emp.country}</small>
                  </div>
                  <div className={`status ${emp.status === 'online' ? 'status-online' : 'status-offline'}`}>
                    {emp.status === 'online' ? '🟢 Online' : '🔴 Offline'}
                    <br />
                    <small>Last seen: {new Date(emp.last_seen).toLocaleString()}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default DashboardSection;