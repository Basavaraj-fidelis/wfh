
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Sidebar from './Sidebar';
import Header from './Header';
import DashboardSection from './sections/DashboardSection';
import EmployeesSection from './sections/EmployeesSection';
import ReportsSection from './sections/ReportsSection';
import AgentSection from './sections/AgentSection';
import SettingsSection from './sections/SettingsSection';

type Section = 'dashboard' | 'employees' | 'reports' | 'agent' | 'settings';

const Dashboard: React.FC = () => {
  const [currentSection, setCurrentSection] = useState<Section>('dashboard');
  const { logout } = useAuth();

  const renderSection = () => {
    switch (currentSection) {
      case 'dashboard':
        return <DashboardSection />;
      case 'employees':
        return <EmployeesSection />;
      case 'reports':
        return <ReportsSection />;
      case 'agent':
        return <AgentSection />;
      case 'settings':
        return <SettingsSection />;
      default:
        return <DashboardSection />;
    }
  };

  const getSectionTitle = () => {
    const titles = {
      dashboard: 'Dashboard',
      employees: 'Employee Management',
      reports: 'Reports & Analytics',
      agent: 'Agent Download',
      settings: 'System Settings'
    };
    return titles[currentSection];
  };

  return (
    <div className="dashboard">
      <Sidebar currentSection={currentSection} onSectionChange={setCurrentSection} />
      <div className="main-content">
        <Header title={getSectionTitle()} onLogout={logout} />
        <div className="content-section active">
          {renderSection()}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
