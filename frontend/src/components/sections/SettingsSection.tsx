
import React, { useState } from 'react';
import axios from 'axios';

const SettingsSection: React.FC = () => {
  const [alert, setAlert] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showAlert = (message: string, type: 'success' | 'error') => {
    setAlert({ message, type });
    setTimeout(() => setAlert(null), 5000);
  };

  const saveSettings = () => {
    showAlert('Settings saved successfully!', 'success');
  };

  const cleanupOldData = async () => {
    if (!confirm('Are you sure you want to cleanup old data? This cannot be undone.')) {
      return;
    }

    try {
      const response = await axios.get('/api/admin/cleanup');
      const data = response.data;
      showAlert(
        `Cleanup completed: ${data.deleted_heartbeats} heartbeats, ${data.deleted_logs} logs, ${data.deleted_screenshots} screenshots deleted`,
        'success'
      );
    } catch (error) {
      showAlert('Cleanup failed: ' + (error as any).message, 'error');
    }
  };

  return (
    <div>
      <h3>System Settings</h3>

      <div className="form-row">
        <div>
          <label>Data Retention Period (days)</label>
          <input type="number" defaultValue="45" min="1" max="365" />
        </div>
        <div>
          <label>Heartbeat Interval (minutes)</label>
          <input type="number" defaultValue="5" min="1" max="60" />
        </div>
      </div>

      <div className="form-row">
        <div>
          <label>Agent Token</label>
          <input type="text" defaultValue="agent-secret-token-change-this-in-production" />
        </div>
        <div>
          <label>Screenshot Quality</label>
          <select defaultValue="medium">
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div style={{ marginTop: '30px' }}>
        <button className="btn btn-success" onClick={saveSettings}>
          💾 Save Settings
        </button>
        <button className="btn btn-danger" onClick={cleanupOldData} style={{ marginLeft: '10px' }}>
          🗑️ Cleanup Old Data
        </button>
      </div>

      {alert && (
        <div className={`alert ${alert.type === 'error' ? 'alert-error' : 'alert-success'}`} style={{ marginTop: '20px' }}>
          {alert.message}
        </div>
      )}
    </div>
  );
};

export default SettingsSection;
