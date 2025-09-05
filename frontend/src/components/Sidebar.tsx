
import React from 'react';

interface SidebarProps {
  currentSection: string;
  onSectionChange: (section: 'dashboard' | 'employees' | 'reports' | 'agent' | 'settings') => void;
}

const Sidebar: React.FC<SidebarProps> = ({ currentSection, onSectionChange }) => {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h3>WFH Monitor</h3>
        <p>Admin Panel</p>
      </div>
      <ul className="nav-menu">
        <li>
          <a 
            href="#" 
            onClick={() => onSectionChange('dashboard')}
            className={currentSection === 'dashboard' ? 'active' : ''}
          >
            📊 Dashboard
          </a>
        </li>
        <li>
          <a 
            href="#" 
            onClick={() => onSectionChange('employees')}
            className={currentSection === 'employees' ? 'active' : ''}
          >
            👥 Employees
          </a>
        </li>
        <li>
          <a 
            href="#" 
            onClick={() => onSectionChange('reports')}
            className={currentSection === 'reports' ? 'active' : ''}
          >
            📈 Reports
          </a>
        </li>
        <li>
          <a 
            href="#" 
            onClick={() => onSectionChange('agent')}
            className={currentSection === 'agent' ? 'active' : ''}
          >
            💾 Agent Download
          </a>
        </li>
        <li>
          <a 
            href="#" 
            onClick={() => onSectionChange('settings')}
            className={currentSection === 'settings' ? 'active' : ''}
          >
            ⚙️ Settings
          </a>
        </li>
      </ul>
    </div>
  );
};

export default Sidebar;
