// List of historical queries
import React, { useState } from 'react';
import { formatCost, formatTokens } from '../../utils/formatCost';

const HistoryList = ({ history }) => {
  const [expandedId, setExpandedId] = useState(null);

  if (!history || history.length === 0) {
    return <p className="text-gray-500 text-sm">No query history found.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left text-gray-500">
        <thead className="text-xs text-gray-700 uppercase bg-gray-50">
          <tr>
            <th scope="col" className="px-6 py-3">Question</th>
            <th scope="col" className="px-6 py-3">Model</th>
            <th scope="col" className="px-6 py-3 text-right">Tokens (C/O)</th>
            <th scope="col" className="px-6 py-3 text-right">Cost</th>
            <th scope="col" className="px-6 py-3 text-right">Date</th>
          </tr>
        </thead>
        <tbody>
          {history.map((item, idx) => (
            <React.Fragment key={item.id || idx}>
              <tr 
                className="bg-white border-b hover:bg-gray-50 cursor-pointer"
                onClick={() => setExpandedId(expandedId === idx ? null : idx)}
              >
                <td className="px-6 py-4 font-medium text-gray-900 max-w-xs truncate">
                  {item.question}
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                    {item.llmProvider || 'Unknown'}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <span className="text-indigo-600 font-medium">{formatTokens(item.compressedTokens)}</span>
                  <span className="text-gray-400 mx-1">/</span>
                  <span className="text-gray-500">{formatTokens(item.originalTokens)}</span>
                </td>
                <td className="px-6 py-4 text-right">
                  {formatCost(item.cost)}
                </td>
                <td className="px-6 py-4 text-right text-gray-400">
                  {new Date(item.createdAt || Date.now()).toLocaleDateString()}
                </td>
              </tr>
              {expandedId === idx && (
                <tr className="bg-gray-50 border-b">
                  <td colSpan="5" className="px-6 py-4">
                    <div className="text-gray-700">
                      <strong>Full Question:</strong>
                      <p className="mt-1 mb-3">{item.question}</p>
                      <strong>Answer:</strong>
                      <p className="mt-1">{item.answer || 'No answer recorded.'}</p>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default HistoryList;
