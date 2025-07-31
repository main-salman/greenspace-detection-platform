'use client';

import { useState, useMemo } from 'react';
import { City } from '@/types';

interface CitySelectorProps {
  cities: City[];
  selectedCity: City | null;
  onCitySelect: (city: City) => void;
}

export default function CitySelector({ cities, selectedCity, onCitySelect }: CitySelectorProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCountry, setSelectedCountry] = useState('');

  const countries = useMemo(() => {
    const countrySet = new Set(cities.map(city => city.country));
    return Array.from(countrySet).sort();
  }, [cities]);

  const filteredCities = useMemo(() => {
    return cities.filter(city => {
      const matchesSearch = searchTerm === '' || 
        city.city.toLowerCase().includes(searchTerm.toLowerCase()) ||
        city.state_province.toLowerCase().includes(searchTerm.toLowerCase()) ||
        city.country.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesCountry = selectedCountry === '' || city.country === selectedCountry;
      
      return matchesSearch && matchesCountry;
    });
  }, [cities, searchTerm, selectedCountry]);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">🏙️ Select City</h2>
      
      {/* Search and Filter Controls */}
      <div className="space-y-4 mb-6">
        <div>
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
            Search Cities
          </label>
          <input
            id="search"
            type="text"
            placeholder="Search by city, state, or country..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          />
        </div>
        
        <div>
          <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-2">
            Filter by Country
          </label>
          <select
            id="country"
            value={selectedCountry}
            onChange={(e) => setSelectedCountry(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          >
            <option value="">All Countries</option>
            {countries.map(country => (
              <option key={country} value={country}>{country}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Selected City Display */}
      {selectedCity && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
          <h3 className="font-semibold text-green-800 mb-2">Selected City</h3>
          <div className="text-sm text-green-700">
            <p><strong>{selectedCity.city}</strong>, {selectedCity.state_province}</p>
            <p>{selectedCity.country}</p>
            <p className="text-xs mt-1">
              📍 {parseFloat(selectedCity.latitude).toFixed(4)}, {parseFloat(selectedCity.longitude).toFixed(4)}
            </p>
          </div>
        </div>
      )}

      {/* Cities List */}
      <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg">
        {filteredCities.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            No cities found matching your criteria
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredCities.map((city) => (
              <button
                key={city.city_id}
                onClick={() => onCitySelect(city)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                  selectedCity?.city_id === city.city_id ? 'bg-green-50 border-l-4 border-green-500' : ''
                }`}
              >
                <div className="font-medium text-gray-900">{city.city}</div>
                <div className="text-sm text-gray-600">
                  {city.state_province}, {city.country}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  📍 {parseFloat(city.latitude).toFixed(2)}, {parseFloat(city.longitude).toFixed(2)}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
      
      {filteredCities.length > 0 && (
        <div className="mt-4 text-sm text-gray-500 text-center">
          Showing {filteredCities.length} of {cities.length} cities
        </div>
      )}
    </div>
  );
} 