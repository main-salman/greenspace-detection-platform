'use client';

import { ProcessingStatus } from '@/types';
import { formatDistanceToNow } from 'date-fns';

interface ProcessingPanelProps {
  status: ProcessingStatus;
}

export default function ProcessingPanel({ status }: ProcessingPanelProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return '⏳';
      case 'downloading': return '📡';
      case 'preprocessing': return '🔧';
      case 'processing': return '🎨';
      case 'completed': return '✅';
      case 'failed': return '❌';
      default: return '⏳';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'downloading': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'preprocessing': return 'text-purple-600 bg-purple-50 border-purple-200';
      case 'processing': return 'text-indigo-600 bg-indigo-50 border-indigo-200';
      case 'completed': return 'text-green-600 bg-green-50 border-green-200';
      case 'failed': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const elapsedTime = formatDistanceToNow(new Date(status.startTime), { addSuffix: true });

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">🚀 Processing Status</h2>
      
      {/* Status Header */}
      <div className={`rounded-lg p-4 border-2 mb-6 ${getStatusColor(status.status)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{getStatusIcon(status.status)}</span>
            <div>
              <h3 className="font-semibold text-lg capitalize">{status.status}</h3>
              <p className="text-sm">{status.message}</p>
            </div>
          </div>
          <div className="text-right text-sm">
            <p>Started {elapsedTime}</p>
            {status.endTime && (
              <p>Completed {formatDistanceToNow(new Date(status.endTime), { addSuffix: true })}</p>
            )}
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      {status.status !== 'completed' && status.status !== 'failed' && (
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Progress</span>
            <span>{Math.round(status.progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-green-500 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${status.progress}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Processing Steps */}
      <div className="space-y-3">
        <h4 className="font-semibold text-gray-700">Processing Steps:</h4>
        
        <div className="space-y-2">
          <div className={`flex items-center space-x-3 p-2 rounded ${
            ['downloading', 'preprocessing', 'processing', 'completed'].includes(status.status) 
              ? 'bg-green-50 text-green-700' 
              : 'bg-gray-50 text-gray-500'
          }`}>
            <span>{status.status === 'downloading' ? '🔄' : '✅'}</span>
            <span>Downloading satellite images</span>
          </div>
          
          <div className={`flex items-center space-x-3 p-2 rounded ${
            ['preprocessing', 'processing', 'completed'].includes(status.status) 
              ? 'bg-green-50 text-green-700' 
              : 'bg-gray-50 text-gray-500'
          }`}>
            <span>{status.status === 'preprocessing' ? '🔄' : status.status === 'downloading' ? '⏳' : '✅'}</span>
            <span>Cloud removal and image compositing</span>
          </div>
          
          <div className={`flex items-center space-x-3 p-2 rounded ${
            ['processing', 'completed'].includes(status.status) 
              ? 'bg-green-50 text-green-700' 
              : 'bg-gray-50 text-gray-500'
          }`}>
            <span>{status.status === 'processing' ? '🔄' : ['downloading', 'preprocessing'].includes(status.status) ? '⏳' : '✅'}</span>
            <span>NDVI calculation and vegetation highlighting</span>
          </div>
          
          <div className={`flex items-center space-x-3 p-2 rounded ${
            status.status === 'completed' 
              ? 'bg-green-50 text-green-700' 
              : 'bg-gray-50 text-gray-500'
          }`}>
            <span>{status.status === 'completed' ? '✅' : '⏳'}</span>
            <span>Generating final results</span>
          </div>
        </div>
      </div>

      {/* Results Preview */}
      {status.result && (
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-semibold text-gray-700 mb-3">Results Preview:</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Downloaded Images:</span>
              <span className="font-medium ml-2">{status.result.downloadedImages}</span>
            </div>
            <div>
              <span className="text-gray-600">Processed Composites:</span>
              <span className="font-medium ml-2">{status.result.processedComposites}</span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-600">Vegetation Coverage:</span>
              <span className="font-medium ml-2 text-green-600">
                {status.result.vegetationPercentage.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {status.status === 'failed' && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <h4 className="font-semibold text-red-700 mb-2">Processing Failed</h4>
          <p className="text-red-600 text-sm">{status.message}</p>
        </div>
      )}
    </div>
  );
} 