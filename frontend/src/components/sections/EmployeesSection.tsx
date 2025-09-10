
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
  activity_data: string;
}

interface DayActivity {
  date: string;
  location: 'Office Bangalore' | 'Remote Work';
  heartbeat_count: number;
  active_time: number;
  idle_time: number;
  screen_lock_events: any[];
  app_usage: Record<string, number>;
  websites_visited: any[];
  screenshots: LogEntry[];
  working_hours: number;
  productivity: string;
}

interface ViewState {
  currentView: 'list' | 'employee-detail' | 'day-detail';
  selectedEmployee: string | null;
  selectedDate: string | null;
  employeeData: {
    logs: LogEntry[];
    stats: any;
    dailyActivities: DayActivity[];
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
    selectedDate: null,
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
      // Get logs for the last 30 days to build calendar
      const response = await axios.get(`/api/admin/employees/${username}/logs?days=30`);
      const employee = employees.find(emp => emp.username === username);

      // Process logs to create daily activities
      const dailyActivities = await processDailyActivities(username, response.data.logs || []);

      setViewState({
        currentView: 'employee-detail',
        selectedEmployee: username,
        selectedDate: null,
        employeeData: {
          logs: response.data.logs || [],
          stats: employee || {},
          dailyActivities
        }
      });
    } catch (error) {
      console.error('Error loading employee details:', error);
      setViewState({
        currentView: 'employee-detail',
        selectedEmployee: username,
        selectedDate: null,
        employeeData: {
          logs: [],
          stats: employees.find(emp => emp.username === username) || {},
          dailyActivities: []
        }
      });
    }
    setLoading(false);
  };

  const processDailyActivities = async (username: string, logs: LogEntry[]): Promise<DayActivity[]> => {
    const dailyMap = new Map<string, DayActivity>();

    // Process logs by date
    logs.forEach(log => {
      const date = new Date(log.timestamp).toISOString().split('T')[0];
      
      if (!dailyMap.has(date)) {
        dailyMap.set(date, {
          date,
          location: 'Remote Work',
          heartbeat_count: 0,
          active_time: 0,
          idle_time: 0,
          screen_lock_events: [],
          app_usage: {},
          websites_visited: [],
          screenshots: [],
          working_hours: 0,
          productivity: '0%'
        });
      }

      const dayActivity = dailyMap.get(date)!;
      
      // Determine location
      try {
        const locationData = JSON.parse(log.location);
        if (locationData.ip === "14.96.131.106") {
          dayActivity.location = 'Office Bangalore';
        }
      } catch (e) {}

      // Parse activity data
      try {
        const activityData = JSON.parse(log.activity_data || '{}');
        
        if (activityData.heartbeat_count) {
          dayActivity.heartbeat_count += activityData.heartbeat_count;
        }
        
        if (activityData.total_active_time) {
          dayActivity.active_time += activityData.total_active_time;
        }
        
        if (activityData.total_idle_time) {
          dayActivity.idle_time += activityData.total_idle_time;
        }
        
        if (activityData.app_usage) {
          Object.entries(activityData.app_usage).forEach(([app, usage]) => {
            dayActivity.app_usage[app] = (dayActivity.app_usage[app] || 0) + (usage as number);
          });
        }
        
        if (activityData.websites_visited) {
          dayActivity.websites_visited.push(...activityData.websites_visited);
        }
        
        if (activityData.screen_lock_events) {
          dayActivity.screen_lock_events.push(...activityData.screen_lock_events);
        }
      } catch (e) {}

      // Add screenshot
      if (log.screenshot_path) {
        dayActivity.screenshots.push(log);
      }
    });

    // Get working hours for each day
    for (const [date, activity] of dailyMap.entries()) {
      try {
        const workingHoursResponse = await axios.get(`/api/admin/employees/${username}/working-hours?date=${date}`);
        activity.working_hours = workingHoursResponse.data.total_hours || 0;
        const productivityPercentage = Math.min((activity.working_hours / 8.0 * 100), 100);
        activity.productivity = `${Math.round(productivityPercentage)}%`;
      } catch (e) {
        console.error('Error getting working hours for date:', date, e);
      }
    }

    return Array.from(dailyMap.values()).sort((a, b) => b.date.localeCompare(a.date));
  };

  const viewDayDetail = (date: string) => {
    setViewState(prev => ({
      ...prev,
      currentView: 'day-detail',
      selectedDate: date
    }));
  };

  const backToEmployeeDetail = () => {
    setViewState(prev => ({
      ...prev,
      currentView: 'employee-detail',
      selectedDate: null
    }));
  };

  const backToList = () => {
    setViewState({
      currentView: 'list',
      selectedEmployee: null,
      selectedDate: null,
      employeeData: null
    });
  };

  const CircularProgress: React.FC<{ percentage: number; label: string; }> = ({ percentage, label }) => {
    const circumference = 2 * Math.PI * 45;
    const strokeDasharray = circumference;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    return (
      <div className="circular-progress-container">
        <svg width="120" height="120" className="circular-progress">
          <circle cx="60" cy="60" r="45" stroke="#f0f0f0" strokeWidth="8" fill="transparent" />
          <circle
            cx="60" cy="60" r="45" stroke="#ff9999" strokeWidth="8" fill="transparent"
            strokeDasharray={strokeDasharray} strokeDashoffset={strokeDashoffset}
            strokeLinecap="round" transform="rotate(-90 60 60)" className="progress-circle"
          />
          <circle
            cx="60" cy="60" r="35" stroke="#9966ff" strokeWidth="6" fill="transparent"
            strokeDasharray={2 * Math.PI * 35}
            strokeDashoffset={2 * Math.PI * 35 - (percentage * 0.8 / 100) * 2 * Math.PI * 35}
            strokeLinecap="round" transform="rotate(-90 60 60)" className="progress-circle"
          />
          <circle
            cx="60" cy="60" r="25" stroke="#66ffcc" strokeWidth="4" fill="transparent"
            strokeDasharray={2 * Math.PI * 25}
            strokeDashoffset={2 * Math.PI * 25 - (percentage * 0.9 / 100) * 2 * Math.PI * 25}
            strokeLinecap="round" transform="rotate(-90 60 60)" className="progress-circle"
          />
          <text x="60" y="65" textAnchor="middle" className="progress-percentage" fontSize="18" fontWeight="bold" fill="#333">
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

  const renderDayDetailView = () => {
    if (!viewState.employeeData || !viewState.selectedDate) return null;

    const dayActivity = viewState.employeeData.dailyActivities.find(
      day => day.date === viewState.selectedDate
    );

    if (!dayActivity) return <div>No data for selected date</div>;

    return (
      <div className="day-detail-page">
        <div className="day-detail-header">
          <h1 className="day-detail-title">
            📅 {viewState.selectedEmployee} - {new Date(viewState.selectedDate!).toLocaleDateString()}
          </h1>
          <button className="back-btn" onClick={backToEmployeeDetail}>
            ← Back to Calendar
          </button>
        </div>

        <div className="day-detail-content">
          {/* Day Summary Stats */}
          <div className="day-stats-grid">
            <div className="stat-card">
              <h4>Work Location</h4>
              <p className="stat-value" style={{ color: dayActivity.location === 'Office Bangalore' ? '#007bff' : '#28a745' }}>
                {dayActivity.location === 'Office Bangalore' ? '🏢 Office Bangalore' : '🏠 Remote Work'}
              </p>
            </div>
            <div className="stat-card">
              <h4>Heartbeat Count</h4>
              <p className="stat-value">{dayActivity.heartbeat_count}</p>
            </div>
            <div className="stat-card">
              <h4>Active Time</h4>
              <p className="stat-value">{Math.round(dayActivity.active_time)} minutes</p>
            </div>
            <div className="stat-card">
              <h4>Idle Time</h4>
              <p className="stat-value">{Math.round(dayActivity.idle_time)} minutes</p>
            </div>
            <div className="stat-card">
              <h4>Working Hours</h4>
              <p className="stat-value">{dayActivity.working_hours.toFixed(1)}h</p>
            </div>
            <div className="stat-card">
              <h4>Productivity</h4>
              <p className="stat-value">{dayActivity.productivity}</p>
            </div>
          </div>

          {/* Application Usage Chart */}
          <div className="chart-section">
            <h3>📱 Application Usage</h3>
            <div className="app-usage-chart">
              {Object.entries(dayActivity.app_usage).length > 0 ? (
                Object.entries(dayActivity.app_usage)
                  .sort(([,a], [,b]) => b - a)
                  .slice(0, 10)
                  .map(([app, usage], index) => (
                    <div key={app} className="app-usage-bar">
                      <div className="app-name">{app}</div>
                      <div className="usage-bar">
                        <div 
                          className="usage-fill"
                          style={{ 
                            width: `${(usage / Math.max(...Object.values(dayActivity.app_usage))) * 100}%`,
                            backgroundColor: `hsl(${index * 30}, 70%, 60%)`
                          }}
                        ></div>
                      </div>
                      <div className="usage-time">{usage} min</div>
                    </div>
                  ))
              ) : (
                <p style={{ textAlign: 'center', color: '#666' }}>No application usage data available</p>
              )}
            </div>
          </div>

          {/* Websites Visited Chart */}
          <div className="chart-section">
            <h3>🌐 Websites Visited</h3>
            <div className="websites-chart">
              {dayActivity.websites_visited.length > 0 ? (
                dayActivity.websites_visited.map((website, index) => (
                  <div key={index} className="website-entry">
                    <div className="website-info">
                      <span className="website-browser">{website.browser}</span>
                      <span className="website-url">{website.url}</span>
                      <span className="website-time">{new Date(website.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ textAlign: 'center', color: '#666' }}>No website data available</p>
              )}
            </div>
          </div>

          {/* Screen Lock Events */}
          <div className="chart-section">
            <h3>🔒 Screen Lock Events</h3>
            <div className="lock-events">
              {dayActivity.screen_lock_events.length > 0 ? (
                dayActivity.screen_lock_events.map((event, index) => (
                  <div key={index} className="lock-event">
                    <span className={`lock-status ${event.is_locked ? 'locked' : 'unlocked'}`}>
                      {event.is_locked ? '🔒 Locked' : '🔓 Unlocked'}
                    </span>
                    {event.screensaver_active && <span className="screensaver">💻 Screensaver</span>}
                  </div>
                ))
              ) : (
                <p style={{ textAlign: 'center', color: '#666' }}>No screen lock events recorded</p>
              )}
            </div>
          </div>

          {/* Screenshots */}
          <div className="screenshots-section">
            <h3>📷 Screenshots ({dayActivity.screenshots.length})</h3>
            <div className="screenshots-grid">
              {dayActivity.screenshots.map((screenshot, index) => (
                <div key={index} className="screenshot-item">
                  <div className="screenshot-time">
                    {new Date(screenshot.timestamp).toLocaleTimeString()}
                  </div>
                  {screenshot.screenshot_path ? (
                    <img 
                      src={`/api/screenshots/${screenshot.screenshot_path.split('/').pop()}`}
                      alt="Screenshot"
                      className="screenshot-thumbnail"
                      onClick={() => window.open(`/api/screenshots/${screenshot.screenshot_path.split('/').pop()}`, '_blank')}
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const container = target.parentElement;
                        if (container) {
                          container.innerHTML = '<div class="screenshot-error">📷 Screenshot not available</div>';
                        }
                      }}
                    />
                  ) : (
                    <div className="screenshot-error">📷 No screenshot</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderCalendarView = () => {
    if (!viewState.employeeData) return null;

    const { dailyActivities } = viewState.employeeData;
    
    // Generate calendar for last 30 days
    const today = new Date();
    const calendarDays = [];
    
    for (let i = 29; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      
      const activity = dailyActivities.find(day => day.date === dateStr);
      
      calendarDays.push({
        date: dateStr,
        displayDate: date,
        activity: activity || null
      });
    }

    return (
      <div className="calendar-section">
        <h3>📅 Activity Calendar (Last 30 Days)</h3>
        <div className="calendar-grid">
          {calendarDays.map(({ date, displayDate, activity }) => (
            <div 
              key={date}
              className={`calendar-day ${activity ? 'has-activity' : 'no-activity'}`}
              onClick={() => activity && viewDayDetail(date)}
              style={{ cursor: activity ? 'pointer' : 'default' }}
            >
              <div className="calendar-date">{displayDate.getDate()}</div>
              <div className="calendar-month">{displayDate.toLocaleDateString('en', { month: 'short' })}</div>
              {activity && (
                <div className="calendar-info">
                  <div className={`location-indicator ${activity.location === 'Office Bangalore' ? 'office' : 'remote'}`}>
                    {activity.location === 'Office Bangalore' ? '🏢' : '🏠'}
                  </div>
                  <div className="working-hours">{activity.working_hours.toFixed(1)}h</div>
                  <div className="productivity">{activity.productivity}</div>
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="calendar-legend">
          <div className="legend-item">
            <span className="legend-dot office"></span>
            <span>🏢 Office</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot remote"></span>
            <span>🏠 Remote</span>
          </div>
        </div>
      </div>
    );
  };

  const renderEmployeeDetailView = () => {
    const employee = employees.find(emp => emp.username === viewState.selectedEmployee);
    if (!employee || !viewState.employeeData) return null;

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
              <p className="stat-value" style={{ color: employee.status === 'online' ? '#28a745' : '#dc3545' }}>
                {employee.status === 'online' ? '🟢 Online' : '🔴 Offline'}
              </p>
            </div>
            <div className="stat-card">
              <h4>Working Hours Today</h4>
              <p className="stat-value">{employee.working_hours || '0h 0m'}</p>
            </div>
            <div className="stat-card">
              <h4>Productivity Today</h4>
              <p className="stat-value">{employee.productivity || '0%'}</p>
            </div>
            <div className="stat-card">
              <h4>Current Location</h4>
              <p className="stat-value" style={{ 
                color: employee.location === 'Office Bangalore' ? '#007bff' : '#28a745'
              }}>
                {employee.location === 'Office Bangalore' ? '🏢 Office Bangalore' : '🏠 Remote'}
              </p>
            </div>
            <div className="stat-card">
              <h4>Public IP</h4>
              <p className="stat-value" style={{ fontSize: '16px' }}>{employee.public_ip || 'Unknown'}</p>
            </div>
            <div className="stat-card">
              <h4>Last Seen</h4>
              <p className="stat-value" style={{ fontSize: '16px' }}>
                {employee.last_seen ? new Date(employee.last_seen).toLocaleString() : 'Unknown'}
              </p>
            </div>
          </div>

          {/* Calendar View */}
          {renderCalendarView()}
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
  if (viewState.currentView === 'day-detail') {
    return renderDayDetailView();
  }

  if (viewState.currentView === 'employee-detail') {
    return renderEmployeeDetailView();
  }

  return renderEmployeeList();
};

export default EmployeesSection;
