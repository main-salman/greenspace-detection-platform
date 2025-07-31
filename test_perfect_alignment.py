#!/usr/bin/env python3
"""
Test the new perfect alignment satellite processor
"""
import json
import tempfile
import os
import sys
sys.path.append('greenspace-app/python_scripts')

from satellite_processor_fixed import PerfectAlignmentSatelliteProcessor

def test_toronto_alignment():
    """Test perfect alignment for Toronto"""
    
    # Toronto city data (same as used in the app)
    city_data = {
        "city": "Toronto",
        "country": "Canada", 
        "province": "Ontario",
        "latitude": "43.718227",
        "longitude": "-79.378100",
        "polygon_geojson": {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-79.639265, 43.580997],
                    [-79.639265, 43.855457],
                    [-79.116936, 43.855457],
                    [-79.116936, 43.580997],
                    [-79.639265, 43.580997]
                ]]
            }
        }
    }
    
    # Create test config
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            "city": city_data,
            "startMonth": "07",
            "startYear": 2020,
            "endMonth": "07", 
            "endYear": 2020,
            "ndviThreshold": 0.3,
            "cloudCoverageThreshold": 20,
            "outputDir": temp_dir
        }
        
        print("🧪 TESTING PERFECT ALIGNMENT PROCESSOR")
        print("=" * 50)
        print(f"📍 City: {city_data['city']}, {city_data['country']}")
        print(f"📅 Date: {config['startMonth']}/{config['startYear']}")
        print(f"📁 Output: {temp_dir}")
        print()
        
        try:
            # Create processor and run
            processor = PerfectAlignmentSatelliteProcessor(config)
            result = processor.download_and_process_satellite_data()
            
            print("\n✅ PROCESSING COMPLETED SUCCESSFULLY!")
            print("\n📊 ALIGNMENT TEST RESULTS:")
            print("=" * 30)
            print(f"Vegetation Coverage: {result['vegetation_percentage']:.2f}%")
            print(f"Perfect Bounds: {processor.wgs84_bounds}")
            
            # Check if bounds are reasonable for Toronto
            bounds = processor.wgs84_bounds
            if bounds:
                toronto_lat = 43.718227
                toronto_lon = -79.378100
                
                lat_center = (bounds['north'] + bounds['south']) / 2
                lon_center = (bounds['east'] + bounds['west']) / 2
                
                lat_diff = abs(lat_center - toronto_lat)
                lon_diff = abs(lon_center - toronto_lon)
                
                print(f"\n🎯 ALIGNMENT VALIDATION:")
                print(f"Expected center: {toronto_lat}, {toronto_lon}")
                print(f"Actual center: {lat_center:.6f}, {lon_center:.6f}")
                print(f"Lat difference: {lat_diff:.6f}°")
                print(f"Lon difference: {lon_diff:.6f}°")
                
                if lat_diff < 0.01 and lon_diff < 0.01:
                    print("✅ PERFECT ALIGNMENT ACHIEVED!")
                    return True
                else:
                    print("❌ ALIGNMENT STILL OFF")
                    return False
            else:
                print("❌ NO BOUNDS GENERATED")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_toronto_alignment()
    if success:
        print("\n🎉 PERFECT ALIGNMENT TEST PASSED!")
        sys.exit(0)
    else:
        print("\n💥 PERFECT ALIGNMENT TEST FAILED!")
        sys.exit(1)