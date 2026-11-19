// Card showing cost statistics
import React from 'react';
import { formatCost } from '../../utils/formatCost';

const CostCard = ({ stats }) => {
  const { totalCost, totalQueries, avgRatio } = stats;

  return (
    <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl shadow-lg p-6 text-white h-full flex flex-col justify-between">
      <div>
        <h3 className="text-indigo-100 font-medium mb-1">Total Estimated Cost</h3>
        <div className="text-4xl font-bold mb-6">{formatCost(totalCost)}</div>
        
        <div className="space-y-4">
          <div className="flex justify-between items-center border-b border-indigo-400/30 pb-2">
            <span className="text-indigo-100">Total Queries</span>
            <span className="font-semibold">{totalQueries}</span>
          </div>
          <div className="flex justify-between items-center pb-2">
            <span className="text-indigo-100">Avg. Compression</span>
            <span className="font-semibold bg-white/20 px-2 py-1 rounded">
              {(avgRatio * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
      
      <div className="mt-8 text-xs text-indigo-200">
        Cost calculated based on average API rates
      </div>
    </div>
  );
};

export default CostCard;
