
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Employee {
  username: string;
  hostname: string;
  status: 'online' | 'offline';
  last_seen: string;
  public_ip: string;
  city: string;
  state: string;
  country: string;
}

const DashboardSection: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    online: 0,
    offline: 0
  });

  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      const response = await axios.get('/api/admin/employees/status');
      const employeeData = response.data.employees || [];
      
      setEmployees(employeeData);
      setStats({
        total: employeeData.length,
        online: employeeData.filter((e: Employee) => e.status === 'online').length,
        offline: employeeData.filter((e: Employee) => e.status === 'offline').length
      });
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    }
  };

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>{stats.total}</h3>
          <p>Total Employees</p>
        </div>
        <div className="stat-card">
          <h3>{stats.online}</h3>
          <p>Online Now</p>
        </div>
        <div className="stat-card">
          <h3>{stats.offline}</h3>
          <p>Offline</p>
        </div>
      </div>

      <h3>Recent Employee Activity</h3>
      <div className="recent-activity">
        {employees.length > 0 ? (
          employees.map((emp) => (
            <div key={`${emp.username}-${emp.hostname}`} className="activity-item">
              <div>
                <strong>{emp.username}</strong> ({emp.hostname})
              </div>
              <div className={emp.status === 'online' ? 'status-online' : 'status-offline'}>
                {emp.status === 'online' ? '🟢 Online' : '🔴 Offline'}{' '}
                <small>{new Date(emp.last_seen).toLocaleString()}</small>
              </div>
            </div>
          ))
        ) : (
          <p>No employee data available</p>
        )}
      </div>
    </div>
  );
};

export default DashboardSection;
