
// WFH Monitor Extension - Popup Script
class PopupController {
  constructor() {
    this.initializePopup();
  }
  
  async initializePopup() {
    // Get current tab info
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      document.getElementById('tabTitle').textContent = tab.title || 'Untitled';
      document.getElementById('tabUrl').textContent = tab.url || '';
    }
    
    // Load stored statistics
    await this.loadStats();
    
    // Set up event listeners
    document.getElementById('syncBtn').addEventListener('click', () => this.syncEvents());
    document.getElementById('clearBtn').addEventListener('click', () => this.clearData());
    document.getElementById('testBtn').addEventListener('click', () => this.testConnection());
    
    // Check connection status
    await this.checkConnectionStatus();
  }
  
  async loadStats() {
    try {
      const result = await chrome.storage.local.get(['wfh_events', 'wfh_stats']);
      const events = result.wfh_events || [];
      const stats = result.wfh_stats || {};
      
      document.getElementById('sessionId').textContent = stats.sessionId || 'Unknown';
      document.getElementById('eventCount').textContent = stats.eventCount || 0;
      document.getElementById('storedCount').textContent = events.length;
      
      if (stats.lastActivity) {
        const lastActivity = new Date(stats.lastActivity);
        document.getElementById('lastActivity').textContent = lastActivity.toLocaleTimeString();
      }
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  }
  
  async checkConnectionStatus() {
    try {
      const response = await fetch('http://localhost:8001/browser-extension/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp: Date.now() })
      });
      
      if (response.ok) {
        this.updateStatus(true, 'Connected to agent');
      } else {
        this.updateStatus(false, 'Agent not responding');
      }
    } catch (error) {
      this.updateStatus(false, 'Agent not available');
    }
  }
  
  updateStatus(connected, message) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    indicator.className = 'status-indicator ' + (connected ? 'connected' : 'disconnected');
    statusText.textContent = message;
  }
  
  async syncEvents() {
    try {
      const result = await chrome.storage.local.get(['wfh_events']);
      const events = result.wfh_events || [];
      
      if (events.length === 0) {
        alert('No events to sync');
        return;
      }
      
      const response = await fetch('http://localhost:8001/browser-extension/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: events })
      });
      
      if (response.ok) {
        await chrome.storage.local.set({ wfh_events: [] });
        alert(`Successfully synced ${events.length} events`);
        await this.loadStats();
      } else {
        alert('Failed to sync events');
      }
    } catch (error) {
      alert('Error syncing events: ' + error.message);
    }
  }
  
  async clearData() {
    if (confirm('Clear all local data? This cannot be undone.')) {
      await chrome.storage.local.clear();
      alert('Local data cleared');
      await this.loadStats();
    }
  }
  
  async testConnection() {
    this.updateStatus(false, 'Testing connection...');
    await this.checkConnectionStatus();
  }
}

// Initialize popup when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new PopupController();
});
