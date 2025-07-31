'use client';

import React from 'react';
import { ProcessingConfig, City } from '@/types';

interface ConfigurationPanelProps {
  selectedCity: City | null;
  config: Partial<ProcessingConfig>;
  onConfigChange: (config: Partial<ProcessingConfig>) => void;
  onStartProcessing: () => void;
  isProcessing: boolean;
}

export default function ConfigurationPanel({
  selectedCity,
  config,
  onConfigChange,
  onStartProcessing,
  isProcessing
}: ConfigurationPanelProps) {
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 10 }, (_, i) => currentYear - i);
  
  const months = [
    { value: '01', label: 'January' },
    { value: '02', label: 'February' },
    { value: '03', label: 'March' },
    { value: '04', label: 'April' },
    { value: '05', label: 'May' },
    { value: '06', label: 'June' },
    { value: '07', label: 'July' },
    { value: '08', label: 'August' },
    { value: '09', label: 'September' },
    { value: '10', label: 'October' },
    { value: '11', label: 'November' },
    { value: '12', label: 'December' }
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold mb-4 text-gray-800">Processing Configuration</h2>
      
      {!selectedCity && (
        <div className="text-center py-8 text-gray-500">
          Please select a city first
        </div>
      )}

      {selectedCity && (
        <div className="space-y-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <h3 className="font-medium text-blue-900">Selected City</h3>
            <p className="text-blue-700">{selectedCity.city}, {selectedCity.state_province}, {selectedCity.country}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Start Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Start Date
              </label>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={config.startMonth || '07'}
                  onChange={(e) => onConfigChange({ ...config, startMonth: e.target.value })}
                  className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {months.map(month => (
                    <option key={month.value} value={month.value}>
                      {month.label}
                    </option>
                  ))}
                </select>
                <select
                  value={config.startYear || 2020}
                  onChange={(e) => onConfigChange({ ...config, startYear: parseInt(e.target.value) })}
                  className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {years.map(year => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* End Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                End Date
              </label>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={config.endMonth || '07'}
                  onChange={(e) => onConfigChange({ ...config, endMonth: e.target.value })}
                  className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {months.map(month => (
                    <option key={month.value} value={month.value}>
                      {month.label}
                    </option>
                  ))}
                </select>
                <select
                  value={config.endYear || 2020}
                  onChange={(e) => onConfigChange({ ...config, endYear: parseInt(e.target.value) })}
                  className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {years.map(year => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* NDVI Threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                NDVI Threshold: {config.ndviThreshold || 0.3}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.ndviThreshold || 0.3}
                onChange={(e) => onConfigChange({ ...config, ndviThreshold: parseFloat(e.target.value) })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0.0 (No vegetation)</span>
                <span>1.0 (Dense vegetation)</span>
              </div>
            </div>

            {/* Cloud Coverage */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Cloud Coverage: {config.cloudCoverageThreshold || 20}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={config.cloudCoverageThreshold || 20}
                onChange={(e) => onConfigChange({ ...config, cloudCoverageThreshold: parseInt(e.target.value) })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0% (Clear skies only)</span>
                <span>100% (Include cloudy images)</span>
              </div>
            </div>
          </div>

          {/* NDVI Color Legend */}
          <div className="bg-green-50 p-4 rounded-lg">
            <h4 className="font-medium text-green-900 mb-3">Vegetation Density Color Coding</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span>High Density (NDVI &gt; 0.6)</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-yellow-500 rounded"></div>
                <span>Medium Density (NDVI 0.4-0.6)</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-purple-500 rounded"></div>
                <span>Low Density (NDVI 0.2-0.4)</span>
              </div>
            </div>
          </div>

          {/* Advanced Options */}
          <div>
            <h4 className="font-medium text-gray-700 mb-3">Advanced Options</h4>
            <div className="space-y-3">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={config.enableVegetationIndices || false}
                  onChange={(e) => onConfigChange({ ...config, enableVegetationIndices: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Enable additional vegetation indices</span>
              </label>
              
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={config.enableAdvancedCloudDetection || false}
                  onChange={(e) => onConfigChange({ ...config, enableAdvancedCloudDetection: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Enable advanced cloud detection</span>
              </label>
            </div>
          </div>

          {/* Processing Note */}
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
            <div className="flex">
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  <strong>Note:</strong> Processing will only analyze areas within the city's polygon boundaries. 
                  Larger date ranges may take longer to process but provide more comprehensive results.
                </p>
              </div>
            </div>
          </div>

          {/* Start Processing Button */}
          <button
            onClick={onStartProcessing}
            disabled={isProcessing}
            className={`w-full py-3 px-6 rounded-lg font-medium text-white transition-colors ${
              isProcessing
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500'
            }`}
          >
            {isProcessing ? 'Processing...' : 'Start Processing'}
          </button>
        </div>
      )}
    </div>
  );
} 