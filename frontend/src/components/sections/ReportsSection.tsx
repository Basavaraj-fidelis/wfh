
import React, { useState } from 'react';
import axios from 'axios';

const ReportsSection: React.FC = () => {
  const [currentTab, setCurrentTab] = useState('daily');
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadDailyReport = async () => {
    setLoading(true);
    try {
      const date = (document.getElementById('dailyDate') as HTMLInputElement)?.value || 
                   new Date().toISOString().split('T')[0];
      const response = await axios.get(`/api/admin/reports/daily?date=${date}`);
      setReportData(response.data);
    } catch (error) {
      console.error('Error loading daily report:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderDailyReport = () => (
    <div>
      <div className="date-picker">
        <label>Select Date:</label>
        <input 
          type="date" 
          id="dailyDate" 
          defaultValue={new Date().toISOString().split('T')[0]} 
        />
        <button className="btn btn-primary-sm" onClick={loadDailyReport}>
          Generate Report
        </button>
      </div>
      
      {loading && <p>Loading report...</p>}
      
      {reportData && (
        <div className="chart-container">
          <div className="summary-grid">
            <div className="summary-card">
              <h4>Active Employees</h4>
              <div className="value">{reportData.total_employees_active}</div>
            </div>
            <div className="summary-card">
              <h4>Total Hours</h4>
              <div className="value">{reportData.total_hours_worked}h</div>
            </div>
            <div className="summary-card">
              <h4>Avg Hours/Employee</h4>
              <div className="value">{reportData.average_hours_per_employee}h</div>
            </div>
          </div>

          <h4>Employee Activity - {reportData.date}</h4>
          {reportData.employees && reportData.employees.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Hours Worked</th>
                  <th>First Activity</th>
                  <th>Last Activity</th>
                  <th>Heartbeats</th>
                  <th>Logs</th>
                </tr>
              </thead>
              <tbody>
                {reportData.employees.map((emp: any) => (
                  <tr key={emp.username}>
                    <td><strong>{emp.username}</strong></td>
                    <td>{emp.hours_worked}h</td>
                    <td>{new Date(emp.first_activity).toLocaleTimeString()}</td>
                    <td>{new Date(emp.last_activity).toLocaleTimeString()}</td>
                    <td>{emp.heartbeats_count}</td>
                    <td>{emp.logs_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No employee data for this date</p>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div>
      <h3>Reports & Analytics</h3>

      <div className="report-tabs">
        <button 
          className={`report-tab ${currentTab === 'daily' ? 'active' : ''}`}
          onClick={() => setCurrentTab('daily')}
        >
          Daily Reports
        </button>
        <button 
          className={`report-tab ${currentTab === 'weekly' ? 'active' : ''}`}
          onClick={() => setCurrentTab('weekly')}
        >
          Weekly Reports
        </button>
        <button 
          className={`report-tab ${currentTab === 'custom' ? 'active' : ''}`}
          onClick={() => setCurrentTab('custom')}
        >
          Custom Range
        </button>
      </div>

      {currentTab === 'daily' && renderDailyReport()}
      {currentTab === 'weekly' && <p>Weekly reports feature coming soon...</p>}
      {currentTab === 'custom' && <p>Custom range reports feature coming soon...</p>}
    </div>
  );
};

export default ReportsSection;
