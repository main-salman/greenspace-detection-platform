#!/usr/bin/env python3
"""
Demo version of alignment testing system using mock satellite data
This demonstrates the alignment testing process without depending on satellite data downloads
"""

import os
import sys
import numpy as np
import cv2
import folium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime
from pathlib import Path
import json
import matplotlib.pyplot as plt
import logging
from pyproj import Transformer
from rasterio.crs import CRS
import rasterio.transform
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DemoAlignmentTester:
    """Demo alignment testing system with mock satellite data"""
    
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
        
        # Setup browser
        self.setup_browser()
        
        logger.info(f"Demo alignment tester initialized for {city}, {province}, {country}")
    
    def setup_browser(self):
        """Setup headless Chrome browser"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        
        try:
            import chromedriver_autoinstaller
            chromedriver_autoinstaller.install()
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Browser setup successful")
        except Exception as e:
            logger.error(f"Browser setup failed: {e}")
            raise
    
    def get_city_bounds(self):
        """Get city bounds from Nominatim"""
        try:
            address = f"{self.city}, {self.province}, {self.country}"
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={'q': address, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'DemoAlignmentTester/1.0'},
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
        """Create mock satellite data that simulates alignment issues"""
        logger.info(f"Creating mock satellite data with offset: {misalignment_offset}")
        
        # Convert bounds to Web Mercator
        transformer = Transformer.from_crs(CRS.from_epsg(4326), self.target_crs, always_xy=True)
        west_m, south_m = transformer.transform(bounds['west'], bounds['south'])
        east_m, north_m = transformer.transform(bounds['east'], bounds['north'])
        
        # Apply intentional misalignment for testing
        west_m += misalignment_offset[0]
        east_m += misalignment_offset[0]
        south_m += misalignment_offset[1]
        north_m += misalignment_offset[1]
        
        # Create image dimensions
        pixel_size = 10.0  # 10m resolution
        width = int((east_m - west_m) / pixel_size)
        height = int((north_m - south_m) / pixel_size)
        
        # Create transform
        transform = rasterio.transform.from_bounds(west_m, south_m, east_m, north_m, width, height)
        
        # Generate mock satellite image with realistic patterns
        logger.info(f"Generating mock satellite image: {width}x{height}")
        
        # Create base image with urban/natural patterns
        image = np.random.randint(50, 150, (height, width, 3), dtype=np.uint8)
        
        # Add some "roads" (darker lines)
        for i in range(0, height, 30):
            if i + 2 < height:
                image[i:i+2, :] = [80, 80, 80]  # Horizontal roads
        
        for j in range(0, width, 25):
            if j + 2 < width:
                image[:, j:j+2] = [80, 80, 80]  # Vertical roads
        
        # Add some "vegetation" (green areas)
        for _ in range(20):
            cx, cy = np.random.randint(20, width-20), np.random.randint(20, height-20)
            radius = np.random.randint(10, 30)
            y, x = np.ogrid[:height, :width]
            mask = (x - cx)**2 + (y - cy)**2 <= radius**2
            image[mask] = [60, 120, 60]  # Green vegetation
        
        # Add noise for realism
        noise = np.random.randint(-20, 20, image.shape, dtype=np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return {
            'image': image,
            'transform': transform,
            'crs': self.target_crs,
            'bounds': (west_m, south_m, east_m, north_m),
            'misalignment_offset': misalignment_offset
        }
    
    def create_test_map(self, bounds, satellite_data, iteration=0):
        """Create test map with satellite overlay"""
        logger.info(f"Creating test map for iteration {iteration}...")
        
        # Calculate expected misalignment in meters
        offset_x, offset_y = satellite_data['misalignment_offset']
        expected_misalignment = np.sqrt(offset_x**2 + offset_y**2)
        
        try:
            # Create folium map
            m = folium.Map(
                location=[bounds['center_lat'], bounds['center_lon']],
                zoom_start=13,
                tiles='OpenStreetMap'
            )
            
            # Convert satellite bounds back to WGS84 for folium
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
                opacity=0.7,
                name=f"Satellite Overlay (Iter {iteration})"
            ).add_to(m)
            
            # Add test info popup
            folium.Marker(
                [bounds['center_lat'], bounds['center_lon']],
                popup=f"""
                <b>Alignment Test - Iteration {iteration + 1}</b><br>
                Expected Misalignment: {expected_misalignment:.1f}m<br>
                Offset X: {offset_x:.1f}m<br>
                Offset Y: {offset_y:.1f}m<br>
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
    
    def capture_screenshot(self, map_path, iteration=0):
        """Capture screenshot of test map"""
        logger.info(f"Capturing screenshot for iteration {iteration}...")
        
        try:
            self.driver.get(f"file://{map_path.absolute()}")
            time.sleep(3)  # Wait for map to load
            
            screenshot_path = self.screenshots_dir / f"alignment_test_iter_{iteration}.png"
            self.driver.save_screenshot(str(screenshot_path))
            
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            raise
    
    def analyze_alignment(self, screenshot_path, satellite_data, iteration=0):
        """Analyze alignment - for demo, use the known offset"""
        logger.info(f"Analyzing alignment for iteration {iteration}...")
        
        # For demo purposes, calculate alignment based on known offset
        offset_x, offset_y = satellite_data['misalignment_offset']
        actual_misalignment = np.sqrt(offset_x**2 + offset_y**2)
        
        # Simulate some analysis noise
        analysis_noise = np.random.uniform(-0.5, 0.5)
        measured_misalignment = max(0, actual_misalignment + analysis_noise)
        
        # Calculate alignment score (higher is better)
        alignment_score = max(0, 100 - measured_misalignment * 10)
        
        result = {
            'iteration': iteration,
            'alignment_score': alignment_score,
            'misalignment_meters': measured_misalignment,
            'is_acceptable': measured_misalignment <= self.tolerance_meters,
            'screenshot_path': str(screenshot_path),
            'actual_offset': satellite_data['misalignment_offset']
        }
        
        logger.info(f"Alignment analysis: Score={alignment_score:.1f}, Misalignment={measured_misalignment:.1f}m")
        return result
    
    def correct_alignment(self, satellite_data, alignment_result):
        """Apply correction to reduce misalignment"""
        if alignment_result['is_acceptable']:
            return satellite_data
        
        # Apply correction by reducing the offset
        current_offset = satellite_data['misalignment_offset']
        correction_factor = 0.7  # Reduce misalignment by 30% each iteration
        
        new_offset = (
            current_offset[0] * correction_factor,
            current_offset[1] * correction_factor
        )
        
        logger.info(f"Applying correction: {current_offset} -> {new_offset}")
        
        # Get bounds and create corrected satellite data
        bounds = {
            'south': satellite_data.get('original_bounds', {}).get('south', 43.58),
            'north': satellite_data.get('original_bounds', {}).get('north', 43.86),
            'west': satellite_data.get('original_bounds', {}).get('west', -79.64),
            'east': satellite_data.get('original_bounds', {}).get('east', -79.11)
        }
        
        corrected_data = self.create_mock_satellite_data(bounds, new_offset)
        corrected_data['original_bounds'] = bounds
        
        return corrected_data
    
    def run_demo_alignment_test(self):
        """Run the demo alignment test"""
        logger.info("🚀 Starting demo alignment testing system...")
        
        try:
            # Get city bounds
            bounds = self.get_city_bounds()
            if not bounds:
                raise Exception("Could not get city bounds")
            
            # Create initial mock satellite data with intentional misalignment
            initial_offset = (50.0, 30.0)  # 50m east, 30m north misalignment
            satellite_data = self.create_mock_satellite_data(bounds, initial_offset)
            satellite_data['original_bounds'] = bounds
            
            logger.info(f"Starting with intentional misalignment: {initial_offset}")
            
            # Iterative testing
            results = []
            current_satellite_data = satellite_data
            
            for iteration in range(self.max_iterations):
                logger.info(f"\n=== ITERATION {iteration + 1} ===")
                
                # Create test map
                map_path = self.create_test_map(bounds, current_satellite_data, iteration)
                
                # Capture screenshot
                screenshot_path = self.capture_screenshot(map_path, iteration)
                
                # Analyze alignment
                alignment_result = self.analyze_alignment(screenshot_path, current_satellite_data, iteration)
                results.append(alignment_result)
                
                # Check if acceptable
                if alignment_result['is_acceptable']:
                    logger.info(f"🎉 TARGET ALIGNMENT ACHIEVED! Iteration {iteration + 1}")
                    logger.info(f"Misalignment: {alignment_result['misalignment_meters']:.3f}m (≤ {self.tolerance_meters}m)")
                    break
                
                # Apply corrections
                current_satellite_data = self.correct_alignment(current_satellite_data, alignment_result)
                
                logger.info(f"Misalignment: {alignment_result['misalignment_meters']:.1f}m (target: ≤{self.tolerance_meters}m)")
            
            else:
                logger.warning(f"Maximum iterations ({self.max_iterations}) reached")
            
            # Generate report
            self.generate_demo_report(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in demo alignment testing: {e}")
            raise
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()
    
    def generate_demo_report(self, results):
        """Generate demo test report"""
        logger.info("Generating demo alignment test report...")
        
        try:
            report = {
                'test_type': 'DEMO',
                'city': f"{self.city}, {self.province}, {self.country}",
                'test_date': datetime.now().isoformat(),
                'total_iterations': len(results),
                'tolerance_meters': self.tolerance_meters,
                'final_result': results[-1] if results else None,
                'success': any(r['is_acceptable'] for r in results),
                'iterations': results
            }
            
            # Save report
            report_path = self.results_dir / f"demo_alignment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            # Create progress plot
            if results:
                plt.figure(figsize=(12, 6))
                
                iterations = [r['iteration'] for r in results]
                misalignments = [r['misalignment_meters'] for r in results]
                
                plt.plot(iterations, misalignments, 'ro-', linewidth=2, markersize=8, label='Measured Misalignment')
                plt.axhline(y=self.tolerance_meters, color='g', linestyle='--', linewidth=2, label=f'Target (≤{self.tolerance_meters}m)')
                
                plt.xlabel('Iteration')
                plt.ylabel('Misalignment (meters)')
                plt.title('Demo Alignment Correction Progress')
                plt.legend()
                plt.grid(True, alpha=0.3)
                
                # Annotate final result
                final = results[-1]
                if final['is_acceptable']:
                    plt.annotate('✅ SUCCESS!', 
                               xy=(final['iteration'], final['misalignment_meters']),
                               xytext=(final['iteration'], final['misalignment_meters'] + 5),
                               ha='center', fontsize=12, color='green', weight='bold',
                               arrowprops=dict(arrowstyle='->', color='green'))
                
                plot_path = self.results_dir / f"demo_alignment_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                plt.close()
            
            # Print summary
            if results:
                final = results[-1]
                print(f"\n{'='*60}")
                print(f"DEMO ALIGNMENT TEST SUMMARY")
                print(f"{'='*60}")
                print(f"City: {self.city}, {self.province}, {self.country}")
                print(f"Test Type: DEMONSTRATION")
                print(f"Total Iterations: {len(results)}")
                print(f"Initial Misalignment: {results[0]['misalignment_meters']:.1f}m")
                print(f"Final Misalignment: {final['misalignment_meters']:.3f}m")
                print(f"Target Tolerance: ≤{self.tolerance_meters}m")
                print(f"Improvement: {results[0]['misalignment_meters'] - final['misalignment_meters']:.1f}m")
                print(f"Status: {'✅ SUCCESS' if final['is_acceptable'] else '❌ NEEDS MORE ITERATIONS'}")
                print(f"Report: {report_path}")
                if results:
                    print(f"Progress Plot: {plot_path}")
                print(f"{'='*60}")
            
        except Exception as e:
            logger.error(f"Error generating demo report: {e}")

def main():
    """Main demo function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Demo Satellite-OSM Alignment Testing System')
    parser.add_argument('--city', default='Toronto', help='City name')
    parser.add_argument('--province', default='Ontario', help='Province/State')
    parser.add_argument('--country', default='Canada', help='Country')
    parser.add_argument('--tolerance', type=float, default=1.0, help='Tolerance in meters')
    parser.add_argument('--max-iter', type=int, default=10, help='Maximum iterations')
    
    args = parser.parse_args()
    
    try:
        tester = DemoAlignmentTester(args.city, args.province, args.country)
        tester.tolerance_meters = args.tolerance
        tester.max_iterations = args.max_iter
        
        results = tester.run_demo_alignment_test()
        
        return 0 if any(r['is_acceptable'] for r in results) else 1
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())