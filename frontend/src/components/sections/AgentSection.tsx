
import React from 'react';
import axios from 'axios';

const AgentSection: React.FC = () => {
  const downloadAgent = async (platform: string) => {
    try {
      const response = await axios.get(`/download/agent/${platform}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `wfh-agent-${platform}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      alert(`Agent for ${platform} downloaded successfully!`);
    } catch (error) {
      alert('Download failed: ' + (error as any).message);
    }
  };

  return (
    <div>
      <h3>Agent Download & Setup</h3>
      <p>Download the monitoring agent to install on employee computers.</p>

      <div className="download-card">
        <h4>Windows Agent (.msi)</h4>
        <p>For Windows 7/8/10/11 systems</p>
        <p><strong>Silent Install:</strong> <code>msiexec /i agent.msi /qn</code></p>
        <button className="btn btn-primary-sm" onClick={() => downloadAgent('windows')}>
          Download Windows Installer
        </button>
      </div>

      <div className="download-card">
        <h4>macOS Agent (.pkg)</h4>
        <p>For macOS 10.12 and newer</p>
        <p><strong>Install:</strong> Double-click to install or <code>sudo installer -pkg agent.pkg -target /</code></p>
        <button className="btn btn-primary-sm" onClick={() => downloadAgent('mac')}>
          Download macOS Package
        </button>
      </div>

      <div className="download-card">
        <h4>Linux Agent (.deb)</h4>
        <p>For Ubuntu, Debian, and derivatives</p>
        <p><strong>Install:</strong> <code>sudo dpkg -i agent.deb</code></p>
        <button className="btn btn-primary-sm" onClick={() => downloadAgent('linux')}>
          Download Linux Package
        </button>
      </div>

      <div style={{ marginTop: '30px', padding: '20px', background: '#f8f9fa', borderRadius: '5px' }}>
        <h4>Installation Instructions</h4>
        <ol>
          <li>Download the appropriate agent for your system</li>
          <li>Install Python 3.7+ on the target machine</li>
          <li>Extract the agent files to a directory</li>
          <li>Run: <code>pip install -r agent_requirements.txt</code></li>
          <li>Update the server URL in the agent configuration</li>
          <li>Run: <code>python agent.py</code> to start monitoring</li>
        </ol>

        <h4 style={{ marginTop: '20px' }}>Configuration</h4>
        <p><strong>Server URL:</strong> <span>{window.location.origin}</span></p>
        <p><strong>Agent Token:</strong> <code>agent-secret-token-change-this-in-production</code></p>
      </div>
    </div>
  );
};

export default AgentSection;
