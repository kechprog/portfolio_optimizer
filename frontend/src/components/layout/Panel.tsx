import React from 'react';
import './styles.css';

interface PanelProps {
  title: string;
  children: React.ReactNode;
  headerActions?: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({ title, children, headerActions }) => {
  return (
    <div className="panel-wrapper">
      <div className="panel-header">
        <h2 className="panel-title">{title}</h2>
        {headerActions && (
          <div className="panel-header-actions">
            {headerActions}
          </div>
        )}
      </div>
      <div className="panel-content">
        {children}
      </div>
    </div>
  );
};
