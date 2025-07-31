'use client';

import { useState, useEffect } from 'react';
import { City, ProcessingConfig, ProcessingStatus } from '@/types';
import CitySelector from '@/components/CitySelector';
import ConfigurationPanel from '@/components/ConfigurationPanel';
import ProcessingPanel from '@/components/ProcessingPanel';
import ResultsPanel from '@/components/ResultsPanel';


export default function Home() {

  const [cities, setCities] = useState<City[]>([]);
  const [selectedCity, setSelectedCity] = useState<City | null>(null);
  const [config, setConfig] = useState<Partial<ProcessingConfig>>({
    startMonth: '07',
    startYear: 2020,
    endMonth: '07',
    endYear: 2020,
    ndviThreshold: 0.3,
    cloudCoverageThreshold: 20,
    enableVegetationIndices: false,
    enableAdvancedCloudDetection: false,
  });
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  // Load cities from JSON file
  useEffect(() => {
    fetch('/cities.json')
      .then(response => response.json())
      .then(data => setCities(data))
      .catch(error => console.error('Error loading cities:', error));
  }, []);

  // Update config when city is selected
  useEffect(() => {
    if (selectedCity) {
      setConfig(prev => ({ ...prev, city: selectedCity }));
    }
  }, [selectedCity]);

  const handleStartProcessing = async () => {
    if (!selectedCity) {
      alert('Please select a city first');
      return;
    }

    const fullConfig: ProcessingConfig = {
      city: selectedCity,
      startMonth: config.startMonth || '07',
      startYear: config.startYear || 2020,
      endMonth: config.endMonth || '07',
      endYear: config.endYear || 2020,
      ndviThreshold: config.ndviThreshold || 0.3,
      cloudCoverageThreshold: config.cloudCoverageThreshold || 20,
      enableVegetationIndices: config.enableVegetationIndices || false,
      enableAdvancedCloudDetection: config.enableAdvancedCloudDetection || false,
    };

    try {
      // Use current window location to avoid port conflicts
      const baseUrl = window.location.origin;
      const response = await fetch(`${baseUrl}/api/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(fullConfig),
      });

      if (!response.ok) {
        throw new Error('Failed to start processing');
      }

      const result = await response.json();
      
      // Start polling for status updates
      setIsPolling(true);
      pollProcessingStatus(result.processingId);
    } catch (error) {
      console.error('Error starting processing:', error);
      alert('Failed to start processing. Please try again.');
    }
  };

  const pollProcessingStatus = async (processingId: string) => {
    const poll = async () => {
      try {
        // Use current window location to avoid port conflicts  
        const baseUrl = window.location.origin;
        const response = await fetch(`${baseUrl}/api/status/${processingId}`);
        
        if (!response.ok) {
          console.error('Failed to fetch status');
          return;
        }

        const status: ProcessingStatus = await response.json();
        setProcessingStatus(status);

        // Continue polling if not completed or failed
        if (status.status !== 'completed' && status.status !== 'failed') {
          setTimeout(poll, 2000); // Poll every 2 seconds
        } else {
          setIsPolling(false);
        }
      } catch (error) {
        console.error('Error polling status:', error);
        setIsPolling(false);
      }
    };

    poll();
  };

  const isProcessing = processingStatus?.status && 
    ['pending', 'downloading', 'preprocessing', 'processing'].includes(processingStatus.status);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🌍 Greenspace Detection Platform
          </h1>
          <p className="text-lg text-gray-600">
            Analyze satellite imagery to detect and visualize vegetation in cities worldwide
          </p>
        </div>

        {/* Main Content */}
        <div className="max-w-6xl mx-auto">
          <div className="space-y-8">
            <div className="space-y-8">
              {/* City Selection & Configuration */}
              <div className="space-y-6">
                <CitySelector
                  cities={cities}
                  selectedCity={selectedCity}
                  onCitySelect={setSelectedCity}
                />
                
                <ConfigurationPanel
                  selectedCity={selectedCity}
                  config={config}
                  onConfigChange={setConfig}
                  onStartProcessing={handleStartProcessing}
                  isProcessing={!!isProcessing}
                />
              </div>

              {/* Processing Status & Results */}
              <div className="space-y-6">
                {processingStatus && (
                  <ProcessingPanel status={processingStatus} />
                )}
                
                {processingStatus?.status === 'completed' && processingStatus.result && (
                  <ResultsPanel status={processingStatus} selectedCity={selectedCity} />
                )}
                
                {!processingStatus && (
                  <div className="bg-white rounded-lg shadow-md p-8 text-center">
                    <div className="text-gray-400 mb-4">
                      <svg className="mx-auto h-24 w-24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 002 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-medium text-gray-500 mb-2">
                      Ready to Process
                    </h3>
                    <p className="text-gray-400">
                      Select a city and configure your settings to begin satellite image analysis
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-gray-500 text-sm">
          <p>
            Powered by Sentinel satellite imagery and NDVI analysis. Processing uses polygon boundaries for accurate city-specific vegetation detection with precise geographic alignment.
          </p>
        </div>
      </div>
    </div>
  );
}