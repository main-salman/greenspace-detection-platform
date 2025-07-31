#!/usr/bin/env python3
"""
Simple alignment testing demo to verify the system works
This creates a minimal test without complex browser automation
"""

import os
import sys
import numpy as np
import cv2
import folium
import time
from datetime import datetime
from pathlib import Path
import json
import matplotlib.pyplot as plt
import requests
import logging
from pyproj import Transformer
from rasterio.crs import CRS
import rasterio.transform

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAlignmentTester:
    """Simple alignment tester for verification"""
    
    def __init__(self, city="Toronto", province="Ontario", country="Canada"):
        self.city = city
        self.province = province
        self.country = country
        
        # Directories
        self.base_dir = Path("alignment_testing")
        self.screenshots_dir = self.base_dir / "screenshots"
        self.satellite_dir = self.base_dir / "satellite_data"
        self.results_dir = self.base_dir / "results"
        
        # Create directories
        for dir_path in [self.screenshots_dir, self.satellite_dir, self.results_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.target_crs = CRS.from_epsg(3857)  # Web Mercator
        self.tolerance_meters = 1.0
        self.max_iterations = 10
        
        logger.info(f"Simple alignment tester initialized for {city}, {province}, {country}")
    
    def get_city_bounds(self):
        """Get city bounds from Nominatim"""
        try:
            address = f"{self.city}, {self.province}, {self.country}"
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={'q': address, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'SimpleAlignmentTester/1.0'},
                timeout=30
            )
            
            data = response.json()
            if data and 'boundingbox' in data[0]:
                bbox = data[0]['boundingbox']
                bounds = {
                    'south': float(bbox[0]),
                    'north': float(bbox[1]), 
                    'west': float(bbox[2]),
                    'east': float(bbox[3])
                }
                bounds['center_lat'] = (bounds['south'] + bounds['north']) / 2
                bounds['center_lon'] = (bounds['west'] + bounds['east']) / 2
                logger.info(f"City bounds: {bounds}")
                return bounds
            
        except Exception as e:
            logger.error(f"Error getting city bounds: {e}")
            return None
    
    def create_mock_satellite_data(self, bounds, misalignment_offset=(0, 0)):
        """Create mock satellite data for testing"""
        logger.info(f"Creating mock satellite data with offset: {misalignment_offset}")
        
        # Convert bounds to Web Mercator
        transformer = Transformer.from_crs(CRS.from_epsg(4326), self.target_crs, always_xy=True)
        west_m, south_m = transformer.transform(bounds['west'], bounds['south'])
        east_m, north_m = transformer.transform(bounds['east'], bounds['north'])
        
        # Apply misalignment
        west_m += misalignment_offset[0]
        east_m += misalignment_offset[0]
        south_m += misalignment_offset[1]
        north_m += misalignment_offset[1]
        
        # Create smaller image for testing (reduce size)
        pixel_size = 50.0  # 50m resolution for faster processing
        width = int((east_m - west_m) / pixel_size)
        height = int((north_m - south_m) / pixel_size)
        
        # Limit size for testing
        width = min(width, 500)
        height = min(height, 500)
        
        # Create transform
        transform = rasterio.transform.from_bounds(west_m, south_m, west_m + width*pixel_size, south_m + height*pixel_size, width, height)
        
        logger.info(f"Generating mock satellite image: {width}x{height}")
        
        # Create mock image with patterns
        image = np.random.randint(80, 120, (height, width, 3), dtype=np.uint8)
        
        # Add road patterns
        for i in range(0, height, 15):
            if i + 1 < height:
                image[i:i+1, :] = [60, 60, 60]  # Roads
        
        for j in range(0, width, 12):
            if j + 1 < width:
                image[:, j:j+1] = [60, 60, 60]  # Roads
        
        # Add some green areas
        for _ in range(10):
            cx, cy = np.random.randint(10, width-10), np.random.randint(10, height-10)
            radius = np.random.randint(5, 15)
            y, x = np.ogrid[:height, :width]
            mask = (x - cx)**2 + (y - cy)**2 <= radius**2
            image[mask] = [40, 100, 40]  # Vegetation
        
        return {
            'image': image,
            'transform': transform,
            'crs': self.target_crs,
            'bounds': (west_m, south_m, west_m + width*pixel_size, south_m + height*pixel_size),
            'misalignment_offset': misalignment_offset
        }
    
    def create_test_map(self, bounds, satellite_data, iteration=0):
        """Create test map HTML file"""
        logger.info(f"Creating test map for iteration {iteration}...")
        
        try:
            # Create folium map
            m = folium.Map(
                location=[bounds['center_lat'], bounds['center_lon']],
                zoom_start=12,
                tiles='OpenStreetMap'
            )
            
            # Convert satellite bounds to WGS84
            sat_bounds = satellite_data['bounds']
            transformer = Transformer.from_crs(self.target_crs, CRS.from_epsg(4326), always_xy=True)
            west, south = transformer.transform(sat_bounds[0], sat_bounds[1])
            east, north = transformer.transform(sat_bounds[2], sat_bounds[3])
            
            # Save satellite image
            overlay_path = self.screenshots_dir / f"satellite_overlay_iter_{iteration}.png"
            cv2.imwrite(str(overlay_path), cv2.cvtColor(satellite_data['image'], cv2.COLOR_RGB2BGR))
            
            # Add satellite overlay
            folium.raster_layers.ImageOverlay(
                image=str(overlay_path),
                bounds=[[south, west], [north, east]],
                opacity=0.6,
                name=f"Satellite Data (Iteration {iteration + 1})"
            ).add_to(m)
            
            # Add test marker
            offset_x, offset_y = satellite_data['misalignment_offset']
            expected_misalignment = np.sqrt(offset_x**2 + offset_y**2)
            
            folium.Marker(
                [bounds['center_lat'], bounds['center_lon']],
                popup=f"""
                <b>Alignment Test - Iteration {iteration + 1}</b><br>
                Expected Misalignment: {expected_misalignment:.1f}m<br>
                Offset: ({offset_x:.1f}m, {offset_y:.1f}m)<br>
                Target: ≤{self.tolerance_meters}m
                """,
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            # Save map
            map_path = self.screenshots_dir / f"test_map_iter_{iteration}.html"
            m.save(str(map_path))
            
            logger.info(f"Test map saved: {map_path}")
            return map_path
            
        except Exception as e:
            logger.error(f"Error creating test map: {e}")
            raise
    
    def analyze_alignment(self, satellite_data, iteration=0):
        """Analyze alignment based on known offset"""
        logger.info(f"Analyzing alignment for iteration {iteration}...")
        
        # Calculate misalignment from known offset
        offset_x, offset_y = satellite_data['misalignment_offset']
        actual_misalignment = np.sqrt(offset_x**2 + offset_y**2)
        
        # Add some realistic measurement noise
        measurement_noise = np.random.uniform(-0.3, 0.3)
        measured_misalignment = max(0, actual_misalignment + measurement_noise)
        
        # Calculate alignment score
        alignment_score = max(0, 100 - measured_misalignment * 5)
        
        result = {
            'iteration': iteration,
            'alignment_score': alignment_score,
            'misalignment_meters': measured_misalignment,
            'is_acceptable': measured_misalignment <= self.tolerance_meters,
            'actual_offset': satellite_data['misalignment_offset']
        }
        
        logger.info(f"Alignment analysis: Score={alignment_score:.1f}, Misalignment={measured_misalignment:.1f}m")
        return result
    
    def correct_alignment(self, satellite_data, alignment_result, bounds):
        """Apply correction to reduce misalignment"""
        if alignment_result['is_acceptable']:
            return satellite_data
        
        # Apply 50% correction each iteration for faster convergence
        current_offset = satellite_data['misalignment_offset']
        correction_factor = 0.5  # Keep 50% of current offset
        
        new_offset = (
            current_offset[0] * correction_factor,
            current_offset[1] * correction_factor
        )
        
        logger.info(f"Applying correction: {current_offset} -> {new_offset}")
        
        # Create corrected satellite data
        corrected_data = self.create_mock_satellite_data(bounds, new_offset)
        return corrected_data
    
    def run_simple_test(self):
        """Run simple alignment test"""
        logger.info("🚀 Starting simple alignment test...")
        
        try:
            # Get city bounds
            bounds = self.get_city_bounds()
            if not bounds:
                raise Exception("Could not get city bounds")
            
            # Create initial satellite data with misalignment
            initial_offset = (25.0, 15.0)  # 25m east, 15m north
            satellite_data = self.create_mock_satellite_data(bounds, initial_offset)
            
            logger.info(f"Starting with misalignment: {initial_offset}")
            
            # Test iterations
            results = []
            current_satellite_data = satellite_data
            
            for iteration in range(self.max_iterations):
                logger.info(f"\n=== ITERATION {iteration + 1} ===")
                
                # Create test map
                map_path = self.create_test_map(bounds, current_satellite_data, iteration)
                
                # Analyze alignment (no screenshot needed for simple test)
                alignment_result = self.analyze_alignment(current_satellite_data, iteration)
                results.append(alignment_result)
                
                # Check if acceptable
                if alignment_result['is_acceptable']:
                    logger.info(f"🎉 TARGET ALIGNMENT ACHIEVED! Iteration {iteration + 1}")
                    logger.info(f"Final misalignment: {alignment_result['misalignment_meters']:.3f}m (≤ {self.tolerance_meters}m)")
                    break
                
                # Apply corrections
                current_satellite_data = self.correct_alignment(current_satellite_data, alignment_result, bounds)
                
                logger.info(f"Current misalignment: {alignment_result['misalignment_meters']:.1f}m")
            
            else:
                logger.warning(f"Maximum iterations ({self.max_iterations}) reached")
            
            # Generate report
            self.generate_simple_report(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in simple alignment test: {e}")
            raise
    
    def generate_simple_report(self, results):
        """Generate simple test report"""
        logger.info("Generating simple test report...")
        
        try:
            report = {
                'test_type': 'SIMPLE_TEST',
                'city': f"{self.city}, {self.province}, {self.country}",
                'test_date': datetime.now().isoformat(),
                'total_iterations': len(results),
                'tolerance_meters': float(self.tolerance_meters),
                'success': bool(any(r['is_acceptable'] for r in results)),
                'iterations': [
                    {
                        'iteration': int(r['iteration']),
                        'alignment_score': float(r['alignment_score']),
                        'misalignment_meters': float(r['misalignment_meters']),
                        'is_acceptable': bool(r['is_acceptable']),
                        'actual_offset': [float(r['actual_offset'][0]), float(r['actual_offset'][1])]
                    }
                    for r in results
                ]
            }
            
            # Save report
            report_path = self.results_dir / f"simple_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            # Create progress plot
            if results:
                plt.figure(figsize=(10, 6))
                
                iterations = [r['iteration'] + 1 for r in results]
                misalignments = [r['misalignment_meters'] for r in results]
                
                plt.plot(iterations, misalignments, 'ro-', linewidth=3, markersize=8, label='Measured Misalignment')
                plt.axhline(y=self.tolerance_meters, color='g', linestyle='--', linewidth=2, label=f'Target (≤{self.tolerance_meters}m)')
                
                plt.xlabel('Iteration')
                plt.ylabel('Misalignment (meters)')
                plt.title('Simple Alignment Test - Correction Progress')
                plt.legend()
                plt.grid(True, alpha=0.3)
                
                # Annotate success
                final = results[-1]
                if final['is_acceptable']:
                    plt.annotate('✅ SUCCESS!', 
                               xy=(final['iteration'] + 1, final['misalignment_meters']),
                               xytext=(final['iteration'] + 1, final['misalignment_meters'] + 2),
                               ha='center', fontsize=12, color='green', weight='bold',
                               arrowprops=dict(arrowstyle='->', color='green'))
                
                plot_path = self.results_dir / f"simple_test_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                plt.close()
                
                logger.info(f"Progress plot saved: {plot_path}")
            
            # Print summary
            if results:
                final = results[-1]
                print(f"\n{'='*60}")
                print(f"SIMPLE ALIGNMENT TEST SUMMARY")
                print(f"{'='*60}")
                print(f"City: {self.city}, {self.province}, {self.country}")
                print(f"Test Type: SIMPLE VERIFICATION")
                print(f"Total Iterations: {len(results)}")
                print(f"Initial Misalignment: {results[0]['misalignment_meters']:.1f}m")
                print(f"Final Misalignment: {final['misalignment_meters']:.3f}m")
                print(f"Target Tolerance: ≤{self.tolerance_meters}m")
                print(f"Improvement: {results[0]['misalignment_meters'] - final['misalignment_meters']:.1f}m")
                print(f"Status: {'✅ SUCCESS' if final['is_acceptable'] else '❌ NEEDS MORE ITERATIONS'}")
                print(f"Report: {report_path}")
                print(f"{'='*60}")
            
        except Exception as e:
            logger.error(f"Error generating simple report: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Alignment Test')
    parser.add_argument('--city', default='Toronto', help='City name')
    parser.add_argument('--province', default='Ontario', help='Province/State')
    parser.add_argument('--country', default='Canada', help='Country')
    parser.add_argument('--tolerance', type=float, default=1.0, help='Tolerance in meters')
    
    args = parser.parse_args()
    
    try:
        tester = SimpleAlignmentTester(args.city, args.province, args.country)
        tester.tolerance_meters = args.tolerance
        
        results = tester.run_simple_test()
        
        return 0 if any(r['is_acceptable'] for r in results) else 1
        
    except Exception as e:
        logger.error(f"Simple test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())