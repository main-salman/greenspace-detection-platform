#!/usr/bin/env python3
"""
Batch Process Test - Process 3 cities first to verify everything works
"""

import json
import csv
import os
import sys
from pathlib import Path
from datetime import datetime
import time
from typing import Dict, List, Any, Optional
import traceback

# Add the python_scripts directory to the path
sys.path.append('greenspace-app/python_scripts')

try:
    from satellite_processor_fixed import PerfectAlignmentSatelliteProcessor
    print("✅ Successfully imported satellite_processor_fixed")
except ImportError as e:
    print(f"❌ Error: Could not import satellite_processor_fixed.py: {e}")
    print("Make sure you're running this from the project root directory")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

def process_test_cities():
    """Process just 3 cities to test the system"""
    
    # Load cities
    with open("cities.json", 'r') as f:
        all_cities = json.load(f)
    
    # Take first 3 cities for testing
    test_cities = all_cities[:3]
    
    print(f"🧪 TEST MODE: Processing {len(test_cities)} cities")
    print(f"📊 Cities to process:")
    for i, city in enumerate(test_cities):
        print(f"   {i+1}. {city['city']}, {city['country']}")
    
    # Create output directory
    output_dir = Path("test_batch_results")
    output_dir.mkdir(exist_ok=True)
    
    results = []
    
    for i, city in enumerate(test_cities):
        city_name = f"{city['city']}, {city['country']}"
        print(f"\n{'='*60}")
        print(f"🌍 Processing Test City {i+1}/3: {city_name}")
        print(f"{'='*60}")
        
        try:
            # Create city-specific output directory
            city_output_dir = output_dir / f"city_{i:03d}_{city['city'].replace(' ', '_')}"
            city_output_dir.mkdir(exist_ok=True)
            
            # Create processing config
            config = {
                'city': city,
                'startMonth': '07',
                'startYear': 2020,
                'endMonth': '07', 
                'endYear': 2020,
                'ndviThreshold': 0.3,
                'cloudCoverageThreshold': 20,
                'enableVegetationIndices': True,
                'enableAdvancedCloudDetection': True,
                'outputDir': str(city_output_dir)
            }
            
            # Initialize processor
            processor = PerfectAlignmentSatelliteProcessor(config)
            
            # Process the city
            print(f"🔄 Starting processing for {city_name}...")
            start_time = time.time()
            
            result = processor.download_and_process_satellite_data()
            
            processing_time = time.time() - start_time
            print(f"✅ Processing completed in {processing_time:.1f} seconds")
            
            # Extract key metrics directly from result object
            city_result = {
                'city_id': city['city_id'],
                'city': city['city'],
                'country': city['country'],
                'state_province': city.get('state_province', ''),
                'latitude': city['latitude'],
                'longitude': city['longitude'],
                'processing_time_seconds': round(processing_time, 2),
                'status': 'success',
                'vegetation_percentage': result.get('vegetation_percentage', 0),
                'high_density_percentage': result.get('high_density_percentage', 0),
                'medium_density_percentage': result.get('medium_density_percentage', 0),
                'low_density_percentage': result.get('low_density_percentage', 0),
                'total_pixels': result.get('total_pixels', 0),
                'vegetation_pixels': result.get('vegetation_pixels', 0),
                'ndvi_mean': result.get('ndvi_mean', 0),
                'images_processed': result.get('images_processed', 1),
                'images_found': result.get('images_found', 1),
                'error_message': None
            }
            
            print(f"📊 Results for {city_name}:")
            print(f"   🌱 Vegetation: {city_result['vegetation_percentage']:.1f}%")
            print(f"   🟢 High Density: {city_result['high_density_percentage']:.1f}%")
            print(f"   🟡 Medium Density: {city_result['medium_density_percentage']:.1f}%")
            print(f"   🟣 Low Density: {city_result['low_density_percentage']:.1f}%")
            print(f"   📍 Total Pixels: {city_result['total_pixels']:,}")
            
            results.append(city_result)
            
        except Exception as e:
            error_msg = f"Error processing {city_name}: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔍 Full error: {traceback.format_exc()}")
            
            # Add failed result
            city_result = {
                'city_id': city['city_id'],
                'city': city['city'],
                'country': city['country'],
                'state_province': city.get('state_province', ''),
                'latitude': city['latitude'],
                'longitude': city['longitude'],
                'processing_time_seconds': 0,
                'status': 'failed',
                'vegetation_percentage': 0,
                'high_density_percentage': 0,
                'medium_density_percentage': 0,
                'low_density_percentage': 0,
                'total_pixels': 0,
                'vegetation_pixels': 0,
                'ndvi_mean': 0,
                'images_processed': 0,
                'images_found': 0,
                'error_message': str(e)
            }
            
            results.append(city_result)
        
        # Small delay between cities
        time.sleep(2)
    
    # Generate test CSV
    csv_path = output_dir / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'city_id', 'city', 'country', 'state_province', 'latitude', 'longitude',
            'status', 'processing_time_seconds', 'vegetation_percentage', 'high_density_percentage',
            'medium_density_percentage', 'low_density_percentage', 'total_pixels',
            'vegetation_pixels', 'ndvi_mean', 'images_processed', 'images_found', 'error_message'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            writer.writerow(result)
    
    print(f"\n✅ Test CSV saved: {csv_path}")
    print(f"📊 Test processing completed!")
    
    # Show summary
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    print(f"\n📈 TEST SUMMARY:")
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    
    if successful:
        veg_percentages = [r['vegetation_percentage'] for r in successful]
        print(f"   🌱 Average vegetation: {sum(veg_percentages) / len(veg_percentages):.1f}%")
        print(f"   🌱 Range: {min(veg_percentages):.1f}% - {max(veg_percentages):.1f}%")

if __name__ == "__main__":
    print("🧪 BATCH PROCESSING TEST")
    print("=" * 50)
    
    # Check if cities.json exists
    if not os.path.exists("cities.json"):
        print("❌ Error: cities.json not found in current directory")
        print("Please run this script from the project root directory")
        sys.exit(1)
    
    try:
        process_test_cities()
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print(f"🔍 Full error: {traceback.format_exc()}")
