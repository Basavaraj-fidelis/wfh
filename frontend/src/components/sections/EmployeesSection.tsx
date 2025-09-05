
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

const EmployeesSection: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [filteredEmployees, setFilteredEmployees] = useState<Employee[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');

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
    try {
      const response = await axios.get(`/api/admin/employees/${username}/logs?days=7`);
      const logs = response.data.logs || [];
      
      let logDetails = `📋 Logs for ${username} (Last 7 days)\n`;
      logDetails += `Total logs: ${logs.length}\n\n`;
      
      if (logs.length > 0) {
        logs.forEach((log: any) => {
          const logDate = new Date(log.timestamp).toLocaleString();
          logDetails += `📅 ${logDate}\n`;
          logDetails += `🖥️ Hostname: ${log.hostname}\n`;
          logDetails += `🌐 Local IP: ${log.local_ip}\n`;
          logDetails += `🌍 Public IP: ${log.public_ip}\n`;
          logDetails += `📍 Location: ${log.location}\n`;
          logDetails += `📸 Screenshot: ${log.screenshot_path ? 'Available' : 'None'}\n\n`;
        });
      } else {
        logDetails += 'No logs found for the selected period.';
      }
      
      alert(logDetails);
    } catch (error) {
      alert('Error loading logs. Please try again.');
    }
  };

  const viewWorkingHours = async (username: string) => {
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await axios.get(`/api/admin/employees/${username}/working-hours?date=${today}`);
      const data = response.data;

      let hoursDetails = `⏰ Working Hours for ${username}\n`;
      hoursDetails += `Date: ${data.date}\n`;
      hoursDetails += `Total Hours: ${data.total_hours} hours\n`;

      if (data.first_seen && data.last_seen) {
        const firstSeen = new Date(data.first_seen).toLocaleTimeString();
        const lastSeen = new Date(data.last_seen).toLocaleTimeString();
        hoursDetails += `First Activity: ${firstSeen}\n`;
        hoursDetails += `Last Activity: ${lastSeen}`;
      } else {
        hoursDetails += 'No activity recorded for today';
      }

      alert(hoursDetails);
    } catch (error) {
      alert('Error loading working hours. Please try again.');
    }
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
    </div>
  );
};

export default EmployeesSection;
