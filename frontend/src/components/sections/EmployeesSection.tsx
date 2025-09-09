import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Employee {
  id: string;
  username: string;
  hostname?: string;
  status: 'online' | 'offline';
  start_time: string;
  end_time: string;
  working_hours: string;
  productivity: string;
  public_ip: string;
  location: string;
  last_seen: string;
  raw_hours: number;
  raw_productivity: number;
}

interface LogEntry {
  timestamp: string;
  hostname: string;
  local_ip: string;
  public_ip: string;
  location: string;
  screenshot_path: string | null;
}

interface ViewState {
  currentView: 'list' | 'employee-detail';
  selectedEmployee: string | null;
  employeeData: {
    logs: LogEntry[];
    stats: any;
  } | null;
}

interface DashboardStats {
  total_employees: number;
  office_count: number;
  remote_count: number;
  office_productivity: number;
  remote_productivity: number;
}

const EmployeesSection: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [filteredEmployees, setFilteredEmployees] = useState<Employee[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [viewState, setViewState] = useState<ViewState>({
    currentView: 'list',
    selectedEmployee: null,
    employeeData: null
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadEmployees();
  }, []);

  useEffect(() => {
    filterAndSortEmployees();
  }, [employees, searchTerm, statusFilter, sortBy]);

  const loadEmployees = async () => {
    try {
      const response = await axios.get('/api/admin/employees/enhanced');
      setEmployees(response.data.employees || []);
      setDashboardStats(response.data.dashboard_stats || null);
    } catch (error) {
      console.error('Failed to load employees:', error);
    }
  };

  const filterAndSortEmployees = () => {
    let filtered = employees.filter(emp => {
      const matchesSearch = emp.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           emp.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = !statusFilter || emp.status === statusFilter;
      return matchesSearch && matchesStatus;
    });

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.username.localeCompare(b.username);
        case 'id':
          return a.id.localeCompare(b.id);
        case 'hours':
          return b.raw_hours - a.raw_hours;
        case 'productivity':
          return b.raw_productivity - a.raw_productivity;
        default:
          return 0;
      }
    });

    setFilteredEmployees(filtered);
  };

  const viewEmployeeDetail = async (username: string) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/admin/employees/${username}/logs?days=7`);
      const employee = employees.find(emp => emp.username === username);
      
      setViewState({
        currentView: 'employee-detail',
        selectedEmployee: username,
        employeeData: {
          logs: response.data.logs || [],
          stats: employee || {}
        }
      });
    } catch (error) {
      console.error('Error loading employee details:', error);
      setViewState({
        currentView: 'employee-detail',
        selectedEmployee: username,
        employeeData: {
          logs: [],
          stats: employees.find(emp => emp.username === username) || {}
        }
      });
    }
    setLoading(false);
  };

  const backToList = () => {
    setViewState({
      currentView: 'list',
      selectedEmployee: null,
      employeeData: null
    });
  };

  const CircularProgress: React.FC<{ percentage: number; label: string; }> = ({ percentage, label }) => {
    const circumference = 2 * Math.PI * 45; // radius = 45
    const strokeDasharray = circumference;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;
    
    return (
      <div className="circular-progress-container">
        <svg width="120" height="120" className="circular-progress">
          {/* Background circle */}
          <circle
            cx="60"
            cy="60"
            r="45"
            stroke="#f0f0f0"
            strokeWidth="8"
            fill="transparent"
          />
          
          {/* Working time circle (pink) */}
          <circle
            cx="60"
            cy="60"
            r="45"
            stroke="#ff9999"
            strokeWidth="8"
            fill="transparent"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
            className="progress-circle"
          />
          
          {/* Productive time circle (purple) */}
          <circle
            cx="60"
            cy="60"
            r="35"
            stroke="#9966ff"
            strokeWidth="6"
            fill="transparent"
            strokeDasharray={2 * Math.PI * 35}
            strokeDashoffset={2 * Math.PI * 35 - (percentage * 0.8 / 100) * 2 * Math.PI * 35}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
            className="progress-circle"
          />
          
          {/* Computer activity circle (mint) */}
          <circle
            cx="60"
            cy="60"
            r="25"
            stroke="#66ffcc"
            strokeWidth="4"
            fill="transparent"
            strokeDasharray={2 * Math.PI * 25}
            strokeDashoffset={2 * Math.PI * 25 - (percentage * 0.9 / 100) * 2 * Math.PI * 25}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
            className="progress-circle"
          />
          
          {/* Center text */}
          <text
            x="60"
            y="65"
            textAnchor="middle"
            className="progress-percentage"
            fontSize="18"
            fontWeight="bold"
            fill="#333"
          >
            {percentage}%
          </text>
        </svg>
        
        <h3 className="progress-label">{label}</h3>
        
        <div className="progress-legend">
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#ff9999'}}></span>
            <span className="legend-text">Working time</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#9966ff'}}></span>
            <span className="legend-text">Productive Time</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#66ffcc'}}></span>
            <span className="legend-text">Computer Activity</span>
          </div>
        </div>
      </div>
    );
  };

  const renderEmployeeDetail = () => {
    if (viewState.currentView !== 'employee-detail' || !viewState.employeeData) return null;

    const { logs, stats } = viewState.employeeData;

    return (
      <div className="employee-detail-page">
        <div className="employee-detail-header">
          <h1 className="employee-detail-title">
            👤 {viewState.selectedEmployee} - Employee Details
          </h1>
          <button className="back-btn" onClick={backToList}>
            ← Back to List
          </button>
        </div>

        <div className="employee-detail-content">
          {/* Employee Stats Grid */}
          <div className="employee-stats-grid">
            <div className="stat-card">
              <h4>Status</h4>
              <p className="stat-value" style={{ color: stats.status === 'online' ? '#28a745' : '#dc3545' }}>
                {stats.status === 'online' ? '🟢 Online' : '🔴 Offline'}
              </p>
            </div>
            <div className="stat-card">
              <h4>Working Hours</h4>
              <p className="stat-value">{stats.working_hours || '0h 0m'}</p>
            </div>
            <div className="stat-card">
              <h4>Productivity</h4>
              <p className="stat-value">{stats.productivity || '0%'}</p>
            </div>
            <div className="stat-card">
              <h4>Work Location</h4>
              <p className="stat-value" style={{ 
                color: stats.location === 'Office Bangalore' ? '#007bff' : '#28a745'
              }}>
                {stats.location === 'Office Bangalore' ? '🏢 Office Bangalore' : '🏠 Remote'}
              </p>
            </div>
            <div className="stat-card">
              <h4>Public IP</h4>
              <p className="stat-value" style={{ fontSize: '16px' }}>{stats.public_ip || 'Unknown'}</p>
            </div>
            <div className="stat-card">
              <h4>Last Seen</h4>
              <p className="stat-value" style={{ fontSize: '16px' }}>
                {stats.last_seen ? new Date(stats.last_seen).toLocaleString() : 'Unknown'}
              </p>
            </div>
          </div>

          {/* Activity Logs and Screenshots */}
          <div className="logs-section">
            <div className="logs-header">
              <h3>📊 Activity Logs & Screenshots ({logs.length} entries)</h3>
            </div>
            <div className="logs-content">
              {logs.length === 0 ? (
                <p style={{ textAlign: 'center', color: '#666', padding: '40px' }}>
                  No activity logs available for this employee.
                </p>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="log-entry">
                    <div className="log-details">
                      <div className="log-detail-item">
                        <span className="log-detail-label">📅 Timestamp:</span>
                        <span className="log-detail-value">
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div className="log-detail-item">
                        <span className="log-detail-label">💻 Hostname:</span>
                        <span className="log-detail-value">{log.hostname}</span>
                      </div>
                      <div className="log-detail-item">
                        <span className="log-detail-label">🔗 Local IP:</span>
                        <span className="log-detail-value">{log.local_ip}</span>
                      </div>
                      <div className="log-detail-item">
                        <span className="log-detail-label">🌐 Public IP:</span>
                        <span className="log-detail-value">{log.public_ip}</span>
                      </div>
                      <div className="log-detail-item">
                        <span className="log-detail-label">📍 Location:</span>
                        <span className="log-detail-value">
                          {log.public_ip === '14.96.131.106' ? '🏢 Office Bangalore' : '🏠 Remote Work'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="screenshot-container">
                      {log.screenshot_path ? (
                        <>
                          <img 
                            src={`/api/screenshots/${log.screenshot_path.split('/').pop()}`}
                            alt="Employee Screenshot"
                            className="screenshot-preview"
                            onClick={() => window.open(`/api/screenshots/${log.screenshot_path.split('/').pop()}`, '_blank')}
                          />
                          <div className="screenshot-label">
                            Click to view full size
                          </div>
                        </>
                      ) : (
                        <div style={{ 
                          width: '100%', 
                          height: '200px', 
                          background: '#f8f9fa',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '8px',
                          color: '#666'
                        }}>
                          📷 No screenshot available
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderEmployeeList = () => {
    return (
      <div>
        {/* Dashboard Charts */}
        {dashboardStats && (
          <div className="dashboard-charts-new">
            <div className="charts-container">
              <div className="chart-card">
                <div className="chart-wrapper">
                  <CircularProgress 
                    percentage={dashboardStats.remote_productivity} 
                    label="Remote"
                  />
                </div>
                <div className="employee-count">
                  🏠 Remote: {dashboardStats.remote_count} employees
                </div>
              </div>
              
              <div className="chart-card">
                <div className="chart-wrapper">
                  <CircularProgress 
                    percentage={dashboardStats.office_productivity} 
                    label="Office"
                  />
                </div>
                <div className="employee-count">
                  🏢 Office: {dashboardStats.office_count} employees
                </div>
              </div>
            </div>
            
            <div className="legend-panel">
              <div className="legend-item-new">
                <span className="legend-dot" style={{backgroundColor: '#ff9999'}}></span>
                <span>Working time</span>
              </div>
              <div className="legend-item-new">
                <span className="legend-dot" style={{backgroundColor: '#9966ff'}}></span>
                <span>Productive Time</span>
              </div>
              <div className="legend-item-new">
                <span className="legend-dot" style={{backgroundColor: '#66ffcc'}}></span>
                <span>Computer Activity</span>
              </div>
            </div>
          </div>
        )}

        <div className="employee-table-container">
          <div className="employee-header">
            <h3>Employee Management</h3>
            <button className="refresh-btn" onClick={loadEmployees}>
              🔄 Refresh
            </button>
          </div>

          <div className="search-filter-bar">
            <div className="search-box">
              <input
                type="text"
                placeholder="Search employees by name or hostname..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="filter-select">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All Status</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
              </select>
            </div>
            <div className="filter-select">
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                <option value="id">Sort by ID</option>
                <option value="name">Sort by Name</option>
                <option value="hours">Sort by Working Hours</option>
                <option value="productivity">Sort by Productivity</option>
              </select>
            </div>
          </div>

          {filteredEmployees.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>User Name</th>
                  <th>Start time</th>
                  <th>End Time</th>
                  <th>Working Hrs</th>
                  <th>Productivity</th>
                </tr>
              </thead>
              <tbody>
                {filteredEmployees.map((emp) => (
                  <tr key={emp.id} 
                      onClick={() => viewEmployeeDetail(emp.username)}
                      style={{ 
                        cursor: 'pointer',
                        backgroundColor: emp.status === 'online' ? '#f8f9fa' : '#fff'
                      }}
                      className="employee-row"
                  >
                    <td><strong>{emp.id}</strong></td>
                    <td>
                      <strong>{emp.username}</strong>
                      <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
                        {emp.status === 'online' ? '🟢 Online' : '🔴 Offline'} • {emp.public_ip}
                      </div>
                      <div style={{ 
                        fontSize: '10px', 
                        color: emp.location === 'Office Bangalore' ? '#007bff' : '#28a745',
                        fontWeight: '500'
                      }}>
                        {emp.location === 'Office Bangalore' ? '🏢 Office Bangalore' : '🏠 Remote work'}
                      </div>
                    </td>
                    <td>
                      <span className={emp.start_time !== '--:--' ? 'time-active' : 'time-inactive'}>
                        {emp.start_time}
                      </span>
                    </td>
                    <td>
                      <span className={emp.end_time !== '--:--' ? 'time-active' : 'time-inactive'}>
                        {emp.end_time}
                      </span>
                    </td>
                    <td>
                      <span className={emp.raw_hours > 0 ? 'hours-active' : 'hours-inactive'}>
                        {emp.working_hours}
                      </span>
                    </td>
                    <td>
                      <span className={`productivity-${emp.raw_productivity >= 80 ? 'high' : emp.raw_productivity >= 60 ? 'medium' : 'low'}`}>
                        {emp.productivity}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
              No employees found
            </div>
          )}
        </div>
      </div>
    );
  };

  // Main return statement
  if (viewState.currentView === 'employee-detail') {
    return renderEmployeeDetail();
  }

  return renderEmployeeList();
};

export default EmployeesSection;