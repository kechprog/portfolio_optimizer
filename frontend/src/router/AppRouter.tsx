import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { LandingPage, DashboardPage } from '../pages';
import { ProtectedRoute } from '../components/auth';

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<LandingPage />} />
    </Routes>
  );
};
