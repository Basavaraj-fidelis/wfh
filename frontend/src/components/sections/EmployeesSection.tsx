
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

interface LogEntry {
  timestamp: string;
  hostname: string;
  local_ip: string;
  public_ip: string;
  location: string;
  screenshot_path: string | null;
}

interface WorkingHoursData {
  username: string;
  date: string;
  total_hours: number;
  first_seen: string | null;
  last_seen: string | null;
}

interface ModalData {
  type: 'logs' | 'hours' | null;
  employee: string;
  data: LogEntry[] | WorkingHoursData | null;
}

const EmployeesSection: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [filteredEmployees, setFilteredEmployees] = useState<Employee[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [modalData, setModalData] = useState<ModalData>({ type: null, employee: '', data: null });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadEmployees();
  }, []);

  useEffect(() => {
    filterAndSortEmployees();
  }, [employees, searchTerm, statusFilter, sortBy]);

  const loadEmployees = async () => {
    try {
      const response = await axios.get('/api/admin/employees/status');
      setEmployees(response.data.employees || []);
    } catch (error) {
      console.error('Failed to load employees:', error);
    }
  };

  const filterAndSortEmployees = () => {
    let filtered = employees.filter(emp => {
      const matchesSearch = emp.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           emp.hostname.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = !statusFilter || emp.status === statusFilter;
      return matchesSearch && matchesStatus;
    });

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.username.localeCompare(b.username);
        case 'status':
          return a.status.localeCompare(b.status);
        case 'lastSeen':
          return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        case 'location':
          return a.city.localeCompare(b.city);
        default:
          return 0;
      }
    });

    setFilteredEmployees(filtered);
  };

  const viewEmployeeLogs = async (username: string) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/admin/employees/${username}/logs?days=7`);
      const logs = response.data.logs || [];
      setModalData({ type: 'logs', employee: username, data: logs });
    } catch (error) {
      console.error('Error loading logs:', error);
      setModalData({ type: 'logs', employee: username, data: [] });
    }
    setLoading(false);
  };

  const viewWorkingHours = async (username: string) => {
    setLoading(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await axios.get(`/api/admin/employees/${username}/working-hours?date=${today}`);
      const data = response.data;
      setModalData({ type: 'hours', employee: username, data: data });
    } catch (error) {
      console.error('Error loading working hours:', error);
      setModalData({ type: 'hours', employee: username, data: null });
    }
    setLoading(false);
  };

  const closeModal = () => {
    setModalData({ type: null, employee: '', data: null });
  };

  const formatLocation = (locationStr: string) => {
    try {
      const location = JSON.parse(locationStr);
      return `${location.city || 'Unknown'}, ${location.region || 'Unknown'}, ${location.country || 'Unknown'}`;
    } catch {
      return locationStr || 'Unknown';
    }
  };

  const renderModal = () => {
    if (!modalData.type) return null;

    return (
      <div className="modal-overlay" onClick={closeModal}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>
              {modalData.type === 'logs' ? '📋 Employee Logs' : '⏰ Working Hours'}
              {' - '}
              <span className="employee-name">{modalData.employee}</span>
            </h3>
            <button className="modal-close" onClick={closeModal}>×</button>
          </div>
          
          <div className="modal-body">
            {loading ? (
              <div className="loading-spinner">Loading...</div>
            ) : modalData.type === 'logs' ? (
              <div className="logs-content">
                <div className="logs-summary">
                  <strong>Last 7 days • {Array.isArray(modalData.data) ? modalData.data.length : 0} logs found</strong>
                </div>
                {Array.isArray(modalData.data) && modalData.data.length > 0 ? (
                  <div className="logs-list">
                    {modalData.data.map((log: LogEntry, index: number) => (
                      <div key={index} className="log-entry">
                        <div className="log-header">
                          <span className="log-date">
                            📅 {new Date(log.timestamp).toLocaleString()}
                          </span>
                          {log.screenshot_path && (
                            <span className="screenshot-badge">📸 Screenshot</span>
                          )}
                        </div>
                        <div className="log-details">
                          <div className="log-row">
                            <span className="log-label">🖥️ Hostname:</span>
                            <span>{log.hostname}</span>
                          </div>
                          <div className="log-row">
                            <span className="log-label">🌐 Local IP:</span>
                            <span>{log.local_ip}</span>
                          </div>
                          <div className="log-row">
                            <span className="log-label">🌍 Public IP:</span>
                            <span>{log.public_ip}</span>
                          </div>
                          <div className="log-row">
                            <span className="log-label">📍 Location:</span>
                            <span>{formatLocation(log.location)}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="no-data">No logs found for the selected period.</div>
                )}
              </div>
            ) : (
              <div className="hours-content">
                {modalData.data ? (
                  <div className="hours-summary">
                    <div className="hours-card">
                      <div className="hours-main">
                        <div className="hours-number">
                          {(modalData.data as WorkingHoursData).total_hours}
                          <span className="hours-unit">hours</span>
                        </div>
                        <div className="hours-date">
                          {new Date((modalData.data as WorkingHoursData).date).toLocaleDateString()}
                        </div>
                      </div>
                      
                      {(modalData.data as WorkingHoursData).first_seen && (modalData.data as WorkingHoursData).last_seen ? (
                        <div className="hours-timeline">
                          <div className="timeline-item">
                            <span className="timeline-label">🌅 First Activity:</span>
                            <span className="timeline-time">
                              {new Date((modalData.data as WorkingHoursData).first_seen!).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="timeline-item">
                            <span className="timeline-label">🌅 Last Activity:</span>
                            <span className="timeline-time">
                              {new Date((modalData.data as WorkingHoursData).last_seen!).toLocaleTimeString()}
                            </span>
                          </div>
                          
                          <div className="progress-bar">
                            <div className="progress-label">Daily Progress</div>
                            <div className="progress-container">
                              <div 
                                className="progress-fill" 
                                style={{ 
                                  width: `${Math.min(((modalData.data as WorkingHoursData).total_hours / 8) * 100, 100)}%`,
                                  backgroundColor: (modalData.data as WorkingHoursData).total_hours >= 8 ? '#28a745' : 
                                                   (modalData.data as WorkingHoursData).total_hours >= 6 ? '#ffc107' : '#dc3545'
                                }}
                              ></div>
                              <span className="progress-text">
                                {(modalData.data as WorkingHoursData).total_hours}h / 8h
                              </span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="no-activity">No activity recorded for today</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="no-data">Error loading working hours data.</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3>Employee Management</h3>
        <button className="btn btn-success" onClick={loadEmployees}>
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
            <option value="name">Sort by Name</option>
            <option value="status">Sort by Status</option>
            <option value="lastSeen">Sort by Last Seen</option>
            <option value="location">Sort by Location</option>
          </select>
        </div>
      </div>

      {filteredEmployees.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Public IP</th>
              <th>Location</th>
              <th>Last Seen</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredEmployees.map((emp) => (
              <tr key={`${emp.username}-${emp.hostname}`}>
                <td><strong>{emp.username}</strong></td>
                <td>{emp.hostname}</td>
                <td className={emp.status === 'online' ? 'status-online' : 'status-offline'}>
                  {emp.status === 'online' ? '🟢 Online' : '🔴 Offline'}
                </td>
                <td>{emp.public_ip}</td>
                <td>
                  <div style={{ fontSize: '12px' }}>
                    <div>🏙️ {emp.city}, {emp.state}</div>
                    <div>🌍 {emp.country}</div>
                  </div>
                </td>
                <td>{new Date(emp.last_seen).toLocaleString()}</td>
                <td>
                  <button 
                    className="btn btn-primary-sm" 
                    onClick={() => viewEmployeeLogs(emp.username)}
                    style={{ marginRight: '5px' }}
                  >
                    View Logs
                  </button>
                  <button 
                    className="btn btn-success" 
                    onClick={() => viewWorkingHours(emp.username)}
                  >
                    Working Hours
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No employees found</p>
      )}
      
      {renderModal()}
    </div>
  );
};

export default EmployeesSection;
