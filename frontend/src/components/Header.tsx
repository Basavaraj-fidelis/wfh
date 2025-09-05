
import React from 'react';

interface HeaderProps {
  title: string;
  onLogout: () => void;
}

const Header: React.FC<HeaderProps> = ({ title, onLogout }) => {
  return (
    <div className="header">
      <div>
        <h1>{title}</h1>
        <p>Welcome to the WFH Employee Monitoring System</p>
      </div>
      <div>
        <span>Admin User</span>
        <button className="btn btn-danger" onClick={onLogout}>
          Logout
        </button>
      </div>
    </div>
  );
};

export default Header;
