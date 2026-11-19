// Dashboard main view
import React, { useState, useEffect } from 'react';
import TokenChart from './TokenChart';
import CostCard from './CostCard';
import HistoryList from './HistoryList';
import api from '../../services/api';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ totalCost: 0, totalQueries: 0, avgRatio: 0 });
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const res = await api.get('/query/history'); // Assuming this endpoint provides history and stats
        // Mock stats derivation if not provided by backend directly
        const data = res.data;
        setHistory(data.history || []);
        setStats(data.stats || { 
          totalCost: data.history?.reduce((acc, curr) => acc + (curr.cost || 0), 0) || 0, 
          totalQueries: data.history?.length || 0, 
          avgRatio: data.history?.reduce((acc, curr) => acc + (curr.compressionRatio || 0), 0) / (data.history?.length || 1) || 0 
        });
      } catch (error) {
        console.error("Failed to fetch dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDashboardData();
  }, []);

  if (loading) {
    return <div className="flex justify-center items-center h-64">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-4 sm:p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Token Optimization</h2>
          <div className="h-72">
            <TokenChart queryHistory={history.slice(0, 10)} />
          </div>
        </div>
        
        <div className="lg:col-span-1 flex flex-col space-y-6">
          <CostCard stats={stats} />
        </div>
      </div>
      
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 sm:p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Recent Queries</h2>
        <HistoryList history={history} />
      </div>
    </div>
  );
};

export default Dashboard;
