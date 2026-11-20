import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { AnalysisDashboardPage } from './pages/AnalysisDashboardPage';
import { HistoryPage } from './pages/HistoryPage';
import { ComparePage } from './pages/ComparePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/analyses/:id" element={<AnalysisDashboardPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
