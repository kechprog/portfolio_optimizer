import React from 'react';
import { PanelGroup, Panel, PanelResizeHandle } from 'react-resizable-panels';
import './styles.css';

interface MainLayoutProps {
  performanceChart: React.ReactNode;
  allocatorList: React.ReactNode;
  controlPanel: React.ReactNode;
  portfolioInfo: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  performanceChart,
  allocatorList,
  controlPanel,
  portfolioInfo,
}) => {
  return (
    <div className="main-layout">
      <PanelGroup direction="horizontal" className="panel-group">
        {/* Left Panel - 60% default */}
        <Panel defaultSize={60} minSize={30}>
          <PanelGroup direction="vertical" className="panel-group">
            {/* Performance Chart - 60% of left panel */}
            <Panel defaultSize={60} minSize={20}>
              <div style={{ height: '100%', padding: '8px' }}>
                {performanceChart}
              </div>
            </Panel>

            {/* Vertical Resize Handle */}
            <PanelResizeHandle className="resize-handle resize-handle-vertical" />

            {/* Allocator List - 40% of left panel */}
            <Panel defaultSize={40} minSize={20}>
              <div style={{ height: '100%', padding: '8px' }}>
                {allocatorList}
              </div>
            </Panel>
          </PanelGroup>
        </Panel>

        {/* Horizontal Resize Handle */}
        <PanelResizeHandle className="resize-handle resize-handle-horizontal" />

        {/* Right Panel - 40% default */}
        <Panel defaultSize={40} minSize={30}>
          <PanelGroup direction="vertical" className="panel-group">
            {/* Control Panel - 10% of right panel */}
            <Panel defaultSize={10} minSize={5}>
              <div style={{ height: '100%', padding: '8px' }}>
                {controlPanel}
              </div>
            </Panel>

            {/* Vertical Resize Handle */}
            <PanelResizeHandle className="resize-handle resize-handle-vertical" />

            {/* Portfolio Info - 90% of right panel */}
            <Panel defaultSize={90} minSize={20}>
              <div style={{ height: '100%', padding: '8px' }}>
                {portfolioInfo}
              </div>
            </Panel>
          </PanelGroup>
        </Panel>
      </PanelGroup>
    </div>
  );
};
