
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

  const loadWeeklyReport = async () => {
    setLoading(true);
    try {
      const startDate = (document.getElementById('weeklyDate') as HTMLInputElement)?.value || 
                        getWeekStart().toISOString().split('T')[0];
      const response = await axios.get(`/api/admin/reports/weekly?start_date=${startDate}`);
      setReportData(response.data);
    } catch (error) {
      console.error('Error loading weekly report:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCustomReport = async () => {
    setLoading(true);
    try {
      const startDate = (document.getElementById('customFromDate') as HTMLInputElement)?.value;
      const endDate = (document.getElementById('customToDate') as HTMLInputElement)?.value;
      
      if (!startDate || !endDate) {
        alert('Please select both start and end dates');
        setLoading(false);
        return;
      }
      
      const response = await axios.get(`/api/admin/reports/range?start_date=${startDate}&end_date=${endDate}`);
      setReportData(response.data);
    } catch (error) {
      console.error('Error loading custom report:', error);
    } finally {
      setLoading(false);
    }
  };

  const getWeekStart = () => {
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    return new Date(today.setDate(diff));
  };

  const exportToCsv = (data: any, filename: string) => {
    if (!data || !data.employees) {
      alert('No data to export');
      return;
    }

    let csvContent = '';
    
    if (currentTab === 'daily') {
      csvContent = 'Employee,Hours Worked,First Activity,Last Activity,Heartbeats,Logs\n';
      data.employees.forEach((emp: any) => {
        csvContent += `${emp.username},${emp.hours_worked},${new Date(emp.first_activity).toLocaleString()},${new Date(emp.last_activity).toLocaleString()},${emp.heartbeats_count},${emp.logs_count}\n`;
      });
    } else if (currentTab === 'weekly') {
      csvContent = 'Employee,Total Hours,Avg Daily Hours,Mon,Tue,Wed,Thu,Fri,Sat,Sun\n';
      data.employees.forEach((emp: any) => {
        const dailyHours = emp.daily_breakdown.map((day: any) => day.hours_worked).join(',');
        csvContent += `${emp.username},${emp.total_hours},${emp.average_daily_hours},${dailyHours}\n`;
      });
    } else if (currentTab === 'custom') {
      csvContent = 'Employee,Estimated Active Hours,Heartbeats,Detailed Logs,First Activity,Last Activity\n';
      data.employees.forEach((emp: any) => {
        csvContent += `${emp.username},${emp.estimated_active_hours},${emp.heartbeats_count},${emp.logs_count},${new Date(emp.first_activity).toLocaleString()},${new Date(emp.last_activity).toLocaleString()}\n`;
      });
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  };

  const renderWeeklyReport = () => (
    <div>
      <div className="date-picker">
        <label>Select Week Starting:</label>
        <input 
          type="date" 
          id="weeklyDate" 
          defaultValue={getWeekStart().toISOString().split('T')[0]} 
        />
        <button className="btn btn-primary-sm" onClick={loadWeeklyReport}>
          Generate Report
        </button>
      </div>
      
      {loading && <p>Loading report...</p>}
      
      {reportData && (
        <div className="chart-container">
          <div className="export-buttons">
            <button className="btn btn-success" onClick={() => exportToCsv(reportData, `weekly_report_${reportData.week_start}_${reportData.week_end}.csv`)}>
              📊 Export CSV
            </button>
          </div>
          
          <div className="summary-grid">
            <div className="summary-card">
              <h4>Week Range</h4>
              <div className="value" style={{fontSize: '14px'}}>{reportData.week_start} to {reportData.week_end}</div>
            </div>
            <div className="summary-card">
              <h4>Total Employees</h4>
              <div className="value">{reportData.total_employees}</div>
            </div>
          </div>

          <h4>Weekly Employee Activity</h4>
          {reportData.employees && reportData.employees.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Total Hours</th>
                  <th>Avg Daily Hours</th>
                  <th>Mon</th>
                  <th>Tue</th>
                  <th>Wed</th>
                  <th>Thu</th>
                  <th>Fri</th>
                  <th>Sat</th>
                  <th>Sun</th>
                </tr>
              </thead>
              <tbody>
                {reportData.employees.map((emp: any) => (
                  <tr key={emp.username}>
                    <td><strong>{emp.username}</strong></td>
                    <td>{emp.total_hours}h</td>
                    <td>{emp.average_daily_hours}h</td>
                    {emp.daily_breakdown.map((day: any, index: number) => (
                      <td key={index}>{day.hours_worked}h</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No employee data for this week</p>
          )}
        </div>
      )}
    </div>
  );

  const renderCustomReport = () => (
    <div>
      <div className="date-picker">
        <label>From:</label>
        <input type="date" id="customFromDate" />
        <label>To:</label>
        <input type="date" id="customToDate" />
        <button className="btn btn-primary-sm" onClick={loadCustomReport}>
          Generate Report
        </button>
      </div>
      
      {loading && <p>Loading report...</p>}
      
      {reportData && (
        <div className="chart-container">
          <div className="export-buttons">
            <button className="btn btn-success" onClick={() => exportToCsv(reportData, `custom_report_${reportData.start_date}_${reportData.end_date}.csv`)}>
              📊 Export CSV
            </button>
          </div>
          
          <div className="summary-grid">
            <div className="summary-card">
              <h4>Date Range</h4>
              <div className="value" style={{fontSize: '14px'}}>{reportData.start_date} to {reportData.end_date}</div>
            </div>
            <div className="summary-card">
              <h4>Duration</h4>
              <div className="value">{reportData.duration_days} days</div>
            </div>
            <div className="summary-card">
              <h4>Total Heartbeats</h4>
              <div className="value">{reportData.summary.total_heartbeats}</div>
            </div>
            <div className="summary-card">
              <h4>Total Logs</h4>
              <div className="value">{reportData.summary.total_logs}</div>
            </div>
            <div className="summary-card">
              <h4>Active Employees</h4>
              <div className="value">{reportData.summary.unique_employees}</div>
            </div>
          </div>

          <h4>Employee Activity Summary</h4>
          {reportData.employees && reportData.employees.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Estimated Active Hours</th>
                  <th>Heartbeats</th>
                  <th>Detailed Logs</th>
                  <th>First Activity</th>
                  <th>Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {reportData.employees.map((emp: any) => (
                  <tr key={emp.username}>
                    <td><strong>{emp.username}</strong></td>
                    <td>{emp.estimated_active_hours}h</td>
                    <td>{emp.heartbeats_count}</td>
                    <td>{emp.logs_count}</td>
                    <td>{new Date(emp.first_activity).toLocaleString()}</td>
                    <td>{new Date(emp.last_activity).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No employee data for this date range</p>
          )}
        </div>
      )}
    </div>
  );

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

          <div className="export-buttons">
            <button className="btn btn-success" onClick={() => exportToCsv(reportData, `daily_report_${reportData.date}.csv`)}>
              📊 Export CSV
            </button>
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

  const handleTabChange = (tab: string) => {
    setCurrentTab(tab);
    setReportData(null);
    setLoading(false);
  };

  return (
    <div>
      <h3>Reports & Analytics</h3>

      <div className="report-tabs">
        <button 
          className={`report-tab ${currentTab === 'daily' ? 'active' : ''}`}
          onClick={() => handleTabChange('daily')}
        >
          Daily Reports
        </button>
        <button 
          className={`report-tab ${currentTab === 'weekly' ? 'active' : ''}`}
          onClick={() => handleTabChange('weekly')}
        >
          Weekly Reports
        </button>
        <button 
          className={`report-tab ${currentTab === 'custom' ? 'active' : ''}`}
          onClick={() => handleTabChange('custom')}
        >
          Custom Range
        </button>
      </div>

      {currentTab === 'daily' && renderDailyReport()}
      {currentTab === 'weekly' && renderWeeklyReport()}
      {currentTab === 'custom' && renderCustomReport()}
    </div>
  );
};

export default ReportsSection;
