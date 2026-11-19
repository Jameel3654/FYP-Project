// Component for selecting LLM provider
import React from 'react';

const LLMSelector = ({ selected, onChange }) => {
  const models = [
    {
      id: 'openai',
      name: 'OpenAI',
      description: 'Answer using the optimized document context.',
      logo: 'O'
    },
    {
      id: 'gemini',
      name: 'Gemini',
      description: 'Answer using the optimized document context.',
      logo: 'G'
    }
  ];

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-3">Select Model</label>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {models.map((model) => (
          <button
            type="button"
            key={model.id}
            disabled={model.disabled}
            aria-pressed={selected === model.id}
            onClick={() => onChange(model.id)}
            className={`text-left rounded-xl border-2 p-4 flex items-start space-x-4 transition-all disabled:opacity-45 disabled:cursor-not-allowed ${
              selected === model.id 
                ? 'border-indigo-500 bg-indigo-50 shadow-sm' 
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${
              selected === model.id ? 'bg-indigo-500 text-white' : 'bg-gray-100 text-gray-500'
            }`}>
              {model.logo}
            </div>
            <div>
              <h4 className={`font-semibold ${selected === model.id ? 'text-indigo-900' : 'text-gray-900'}`}>
                {model.name}
              </h4>
              <p className={`text-xs mt-1 ${selected === model.id ? 'text-indigo-700' : 'text-gray-500'}`}>
                {model.description}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default LLMSelector;
