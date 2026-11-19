// Bar chart displaying token optimization
import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const TokenChart = ({ queryHistory }) => {
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      title: { display: false }
    },
    scales: {
      y: { beginAtZero: true }
    }
  };

  const labels = queryHistory.map((_, i) => `Q${queryHistory.length - i}`);
  
  const data = {
    labels: labels.reverse(),
    datasets: [
      {
        label: 'Original Tokens',
        data: queryHistory.map(q => q.originalTokens || 0).reverse(),
        backgroundColor: 'rgba(156, 163, 175, 0.5)',
      },
      {
        label: 'Compressed Tokens',
        data: queryHistory.map(q => q.compressedTokens || 0).reverse(),
        backgroundColor: 'rgba(79, 70, 229, 0.8)',
      }
    ]
  };

  if (!queryHistory || queryHistory.length === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400">No query data available</div>;
  }

  return <Bar options={options} data={data} />;
};

export default TokenChart;
