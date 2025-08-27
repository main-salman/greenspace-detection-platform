#!/usr/bin/env python3
"""
Batch Process All Cities - Standalone Script with Year Comparison (2020 vs 2024)
Processes all cities from cities.json and generates comprehensive CSV reports
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
    print("Make sure you're running this script from the project root directory")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

class BatchCityProcessor:
    def __init__(self, cities_file: str = "cities.json", output_dir: str = "batch_results", selected_city_ids: Optional[List[str]] = None, selected_city_names: Optional[List[str]] = None, annual_mode: bool = False):
        self.cities_file = cities_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.annual_mode = annual_mode
        
        # Load cities
        with open(cities_file, 'r') as f:
            all_cities = json.load(f)
        # Optional filtering
        if selected_city_ids:
            id_set = set(selected_city_ids)
            self.cities = [c for c in all_cities if c.get('city_id') in id_set]
        elif selected_city_names:
            name_set = {n.lower() for n in selected_city_names}
            self.cities = [c for c in all_cities if c.get('city','').lower() in name_set]
        else:
            self.cities = all_cities
        
        mode_str = "Annual (monthly-best avg)" if self.annual_mode else "Single-month (July)"
        print(f"🚀 Batch Processor Initialized with Year Comparison (2020 vs 2024) - {mode_str}")
        print(f"📊 Total cities to process: {len(self.cities)}")
        print(f"📁 Output directory: {self.output_dir}")
        
        # Results storage
        self.results = []
        self.failed_cities = []
        
    def process_city(self, city: Dict[str, Any], city_index: int) -> Optional[Dict[str, Any]]:
        """Process a single city with year comparison and return results"""
        city_name = f"{city['city']}, {city['country']}"
        print(f"\n{'='*60}")
        print(f"🌍 Processing City {city_index + 1}/{len(self.cities)}: {city_name}")
        print(f"📅 Comparing 2020 (baseline) vs 2024 (current)")
        print(f"{'='*60}")
        
        try:
            # Create city-specific output directory
            city_output_dir = self.output_dir / f"city_{city_index:03d}_{city['city'].replace(' ', '_')}"
            city_output_dir.mkdir(exist_ok=True)
            
            def run_one_month(year: int, month: int, out_dir: Path) -> Optional[Dict[str, Any]]:
                cfg = {
                    'city': city,
                    'startMonth': f"{month:02d}",
                    'startYear': year,
                    'endMonth': f"{month:02d}",
                    'endYear': year,
                    'ndviThreshold': 0.3,
                    'cloudCoverageThreshold': 20,
                    'enableVegetationIndices': True,
                    'enableAdvancedCloudDetection': True,
                    'outputDir': str(out_dir)
                }
                proc = PerfectAlignmentSatelliteProcessor(cfg)
                return proc.download_and_process_satellite_data()
            
            def run_year_averaged(year: int, label: str) -> Dict[str, Any]:
                monthly_results: List[Dict[str, Any]] = []
                total_time_s = 0.0
                months_processed = 0
                for m in range(1, 13):
                    subdir = city_output_dir / (f"{year}_{label}") / f"{m:02d}"
                    subdir.mkdir(parents=True, exist_ok=True)
                    print(f"   📆 {label} {year}-{m:02d} ...")
                    try:
                        t0 = time.time()
                        res = run_one_month(year, m, subdir)
                        dt = time.time() - t0
                        total_time_s += dt
                        if res and res.get('total_pixels', 0) > 0:
                            monthly_results.append(res)
                            months_processed += 1
                            print(f"   ✅ Month {m:02d} done ({dt:.1f}s), veg={res.get('vegetation_percentage', 0):.1f}%")
                        else:
                            print(f"   ⚠️ Month {m:02d} produced no valid pixels")
                    except Exception as e:
                        print(f"   ⚠️ Month {m:02d} failed: {e}")
                        continue
                # Aggregate by simple average across months (matches main app)
                def avg(key: str) -> float:
                    vals = [float(r.get(key, 0.0)) for r in monthly_results]
                    return round(sum(vals) / len(vals), 6) if vals else 0.0
                agg = {
                    'vegetation_percentage': avg('vegetation_percentage'),
                    'high_density_percentage': avg('high_density_percentage'),
                    'medium_density_percentage': avg('medium_density_percentage'),
                    'low_density_percentage': avg('low_density_percentage'),
                    'ndvi_mean': avg('ndvi_mean'),
                    'total_pixels': int(sum([r.get('total_pixels', 0) for r in monthly_results]) / max(len(monthly_results), 1)),
                    'vegetation_pixels': int(sum([r.get('vegetation_pixels', 0) for r in monthly_results]) / max(len(monthly_results), 1)),
                    'images_processed': months_processed,
                    'images_found': months_processed,
                    'cloud_excluded_percentage': avg('cloud_excluded_percentage'),
                    'geographic_bounds': monthly_results[0].get('geographic_bounds', {}) if monthly_results else {},
                    'outputFiles': []
                }
                return agg, total_time_s, months_processed
            
            if self.annual_mode:
                print(f"🔄 Processing 2024 annual average (monthly-best) for {city_name}...")
                result_2024, processing_time_2024, _ = run_year_averaged(2024, 'compare')
                print(f"✅ 2024 annual averaging completed in {processing_time_2024:.1f} seconds")
                print(f"🔄 Processing 2020 annual average (monthly-best) for {city_name}...")
                result_2020, processing_time_2020, _ = run_year_averaged(2020, 'baseline')
                print(f"✅ 2020 annual averaging completed in {processing_time_2020:.1f} seconds")
            else:
                # Process 2024 data first (current year) - July only
                print(f"🔄 Processing 2024 data for {city_name}...")
                config_2024 = {
                    'city': city,
                    'startMonth': '07',
                    'startYear': 2024,
                    'endMonth': '07', 
                    'endYear': 2024,
                    'ndviThreshold': 0.3,
                    'cloudCoverageThreshold': 20,
                    'enableVegetationIndices': True,
                    'enableAdvancedCloudDetection': True,
                    'outputDir': str(city_output_dir / '2024_analysis')
                }
                processor_2024 = PerfectAlignmentSatelliteProcessor(config_2024)
                start_time_2024 = time.time()
                result_2024 = processor_2024.download_and_process_satellite_data()
                processing_time_2024 = time.time() - start_time_2024
                print(f"✅ 2024 processing completed in {processing_time_2024:.1f} seconds")
                
                # Process 2020 data (baseline) - July only
                print(f"🔄 Processing 2020 baseline data for {city_name}...")
                config_2020 = {
                    'city': city,
                    'startMonth': '07',
                    'startYear': 2020,
                    'endMonth': '07', 
                    'endYear': 2020,
                    'ndviThreshold': 0.3,
                    'cloudCoverageThreshold': 20,
                    'enableVegetationIndices': True,
                    'enableAdvancedCloudDetection': True,
                    'outputDir': str(city_output_dir / '2020_baseline')
                }
                processor_2020 = PerfectAlignmentSatelliteProcessor(config_2020)
                start_time_2020 = time.time()
                result_2020 = processor_2020.download_and_process_satellite_data()
                processing_time_2020 = time.time() - start_time_2020
                print(f"✅ 2020 baseline processing completed in {processing_time_2020:.1f} seconds")
            
            # Calculate year-over-year changes
            total_processing_time = processing_time_2024 + processing_time_2020
            
            # Extract vegetation percentages
            veg_2020 = result_2020.get('vegetation_percentage', 0)
            veg_2024 = result_2024.get('vegetation_percentage', 0)
            
            # Calculate absolute percentage point change (2024 minus 2020)
            percent_change = veg_2024 - veg_2020
            
            # Create comprehensive result
            city_result = {
                'city_id': city['city_id'],
                'city': city['city'],
                'country': city['country'],
                'state_province': city.get('state_province', ''),
                'latitude': city['latitude'],
                'longitude': city['longitude'],
                'total_processing_time_seconds': round(total_processing_time, 2),
                'status': 'success',
                
                # 2020 Baseline Results
                'vegetation_percentage_2020': veg_2020,
                'high_density_percentage_2020': result_2020.get('high_density_percentage', 0),
                'medium_density_percentage_2020': result_2020.get('medium_density_percentage', 0),
                'low_density_percentage_2020': result_2020.get('low_density_percentage', 0),
                'total_pixels_2020': result_2020.get('total_pixels', 0),
                'vegetation_pixels_2020': result_2020.get('vegetation_pixels', 0),
                'ndvi_mean_2020': result_2020.get('ndvi_mean', 0),
                
                # 2024 Current Results
                'vegetation_percentage_2024': veg_2024,
                'high_density_percentage_2024': result_2024.get('high_density_percentage', 0),
                'medium_density_percentage_2024': result_2024.get('medium_density_percentage', 0),
                'low_density_percentage_2024': result_2024.get('low_density_percentage', 0),
                'total_pixels_2024': result_2024.get('total_pixels', 0),
                'vegetation_pixels_2024': result_2024.get('vegetation_pixels', 0),
                'ndvi_mean_2024': result_2024.get('ndvi_mean', 0),
                
                # Year-over-Year Changes
                'vegetation_percentage_change': round(percent_change, 2),
                'high_density_percentage_change': round(
                    result_2024.get('high_density_percentage', 0) - result_2020.get('high_density_percentage', 0), 2
                ),
                'medium_density_percentage_change': round(
                    result_2024.get('medium_density_percentage', 0) - result_2020.get('medium_density_percentage', 0), 2
                ),
                'low_density_percentage_change': round(
                    result_2024.get('low_density_percentage', 0) - result_2020.get('low_density_percentage', 0), 2
                ),

                # Cloud/coverage diagnostics
                'cloud_excluded_percentage_2020': result_2020.get('cloud_excluded_percentage', 0.0),
                'cloud_excluded_percentage_2024': result_2024.get('cloud_excluded_percentage', 0.0),
                
                # Processing metadata
                'images_processed_2020': result_2020.get('images_processed', 1),
                'images_found_2020': result_2020.get('images_found', 1),
                'images_processed_2024': result_2024.get('images_processed', 1),
                'images_found_2024': result_2024.get('images_found', 1),
                'output_files_2020': result_2020.get('outputFiles', []),
                'output_files_2024': result_2024.get('outputFiles', []),
                'geographic_bounds_2020': result_2020.get('geographic_bounds', {}),
                'geographic_bounds_2024': result_2024.get('geographic_bounds', {}),
                'error_message': None
            }
            
            print(f"📊 Year Comparison Results for {city_name}:")
            print(f"   2020 Baseline: {veg_2020:.1f}% vegetation")
            print(f"   2024 Current:  {veg_2024:.1f}% vegetation")
            print(f"   Change:        {percent_change:+.1f}% ({'↗️' if percent_change > 0 else '↘️' if percent_change < 0 else '➡️'})")
            print(f"   📍 Total Pixels: {city_result['total_pixels_2024']:,}")
            
            return city_result
            
        except Exception as e:
            error_msg = f"Error processing {city_name}: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"🔍 Full error: {traceback.format_exc()}")
            
            # Return failed result
            city_result = {
                'city_id': city['city_id'],
                'city': city['city'],
                'country': city['country'],
                'state_province': city.get('state_province', ''),
                'latitude': city['latitude'],
                'longitude': city['longitude'],
                'total_processing_time_seconds': 0,
                'status': 'failed',
                
                # 2020 Baseline Results
                'vegetation_percentage_2020': 0,
                'high_density_percentage_2020': 0,
                'medium_density_percentage_2020': 0,
                'low_density_percentage_2020': 0,
                'total_pixels_2020': 0,
                'vegetation_pixels_2020': 0,
                'ndvi_mean_2020': 0,
                
                # 2024 Current Results
                'vegetation_percentage_2024': 0,
                'high_density_percentage_2024': 0,
                'medium_density_percentage_2024': 0,
                'low_density_percentage_2024': 0,
                'total_pixels_2024': 0,
                'vegetation_pixels_2024': 0,
                'ndvi_mean_2024': 0,
                
                # Year-over-Year Changes
                'vegetation_percentage_change': 0,
                'high_density_percentage_change': 0,
                'medium_density_percentage_change': 0,
                'low_density_percentage_change': 0,
                
                # Processing metadata
                'images_processed_2020': 0,
                'images_found_2020': 0,
                'images_processed_2024': 0,
                'images_found_2024': 0,
                'output_files_2020': [],
                'output_files_2024': [],
                'geographic_bounds_2020': {},
                'geographic_bounds_2024': {},
                'error_message': str(e)
            }
            
            self.failed_cities.append(city_name)
            return city_result
    
    def process_all_cities(self):
        """Process all cities in the cities.json file with year comparison"""
        print(f"\n🚀 Starting batch processing of {len(self.cities)} cities with 2020 vs 2024 comparison...")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_time = time.time()
        
        for i, city in enumerate(self.cities):
            try:
                result = self.process_city(city, i)
                if result:
                    self.results.append(result)
                
                # Add a small delay between cities to avoid overwhelming the system
                time.sleep(2)
                
            except KeyboardInterrupt:
                print(f"\n⚠️ Processing interrupted by user at city {i+1}")
                break
            except Exception as e:
                print(f"❌ Unexpected error processing city {i+1}: {e}")
                continue
        
        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"🏁 BATCH PROCESSING COMPLETED")
        print(f"{'='*60}")
        print(f"⏰ Total processing time: {total_time/3600:.2f} hours")
        print(f"✅ Successful cities: {len([r for r in self.results if r['status'] == 'success'])}")
        print(f"❌ Failed cities: {len([r for r in self.results if r['status'] == 'failed'])}")
        
        if self.failed_cities:
            print(f"\n❌ Failed cities:")
            for city in self.failed_cities:
                print(f"   - {city}")
    
    def generate_csv_reports(self):
        """Generate comprehensive CSV reports with year comparison data"""
        print(f"\n📊 Generating CSV reports with year comparison...")
        
        # Main results CSV with year comparison
        main_csv_path = self.output_dir / f"year_comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(main_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'city_id', 'city', 'country', 'state_province', 'latitude', 'longitude',
                'status', 'total_processing_time_seconds',
                
                # 2020 Baseline
                'vegetation_percentage_2020', 'high_density_percentage_2020', 'medium_density_percentage_2020', 'low_density_percentage_2020',
                'total_pixels_2020', 'vegetation_pixels_2020', 'ndvi_mean_2020', 'images_processed_2020', 'images_found_2020', 'cloud_excluded_percentage_2020',
                
                # 2024 Current
                'vegetation_percentage_2024', 'high_density_percentage_2024', 'medium_density_percentage_2024', 'low_density_percentage_2024',
                'total_pixels_2024', 'vegetation_pixels_2024', 'ndvi_mean_2024', 'images_processed_2024', 'images_found_2024', 'cloud_excluded_percentage_2024',
                
                # Year-over-Year Changes
                'vegetation_percentage_change', 'high_density_percentage_change', 'medium_density_percentage_change', 'low_density_percentage_change',
                
                'output_files_count_2020', 'output_files_count_2024', 'geographic_bounds_2020', 'geographic_bounds_2024', 'error_message'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                # Prepare row data - only include fields that are in fieldnames
                row = {}
                for field in fieldnames:
                    if field == 'output_files_count_2020':
                        row[field] = len(result.get('output_files_2020', []))
                    elif field == 'output_files_count_2024':
                        row[field] = len(result.get('output_files_2024', []))
                    elif field == 'geographic_bounds_2020':
                        bounds = result.get('geographic_bounds_2020', {})
                        row[field] = f"{bounds.get('west', 0):.6f},{bounds.get('south', 0):.6f},{bounds.get('east', 0):.6f},{bounds.get('north', 0):.6f}"
                    elif field == 'geographic_bounds_2024':
                        bounds = result.get('geographic_bounds_2024', {})
                        row[field] = f"{bounds.get('west', 0):.6f},{bounds.get('south', 0):.6f},{bounds.get('east', 0):.6f},{bounds.get('north', 0):.6f}"
                    else:
                        row[field] = result.get(field, '')
                
                # Write row
                writer.writerow(row)
        
        print(f"✅ Main year comparison CSV saved: {main_csv_path}")
        
        # Summary statistics CSV
        summary_csv_path = self.output_dir / f"year_comparison_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        successful_results = [r for r in self.results if r['status'] == 'success']
        
        if successful_results:
            # Calculate summary statistics
            veg_2020_percentages = [r['vegetation_percentage_2020'] for r in successful_results]
            veg_2024_percentages = [r['vegetation_percentage_2024'] for r in successful_results]
            veg_changes = [r['vegetation_percentage_change'] for r in successful_results]
            processing_times = [r['total_processing_time_seconds'] for r in successful_results]
            
            summary_stats = {
                'metric': [
                    'Total Cities Processed',
                    'Successful Cities',
                    'Failed Cities',
                    'Average Vegetation % (2020)',
                    'Median Vegetation % (2020)',
                    'Min Vegetation % (2020)',
                    'Max Vegetation % (2020)',
                    'Average Vegetation % (2024)',
                    'Median Vegetation % (2024)',
                    'Min Vegetation % (2024)',
                    'Max Vegetation % (2024)',
                    'Average Change % (2020→2024)',
                    'Median Change % (2020→2024)',
                    'Min Change % (2020→2024)',
                    'Max Change % (2020→2024)',
                    'Cities with Increased Vegetation',
                    'Cities with Decreased Vegetation',
                    'Cities with No Change',
                    'Total Processing Time (hours)',
                    'Average Processing Time (seconds)'
                ],
                'value': [
                    len(self.results),
                    len(successful_results),
                    len(self.failed_cities),
                    round(sum(veg_2020_percentages) / len(veg_2020_percentages), 2),
                    round(sorted(veg_2020_percentages)[len(veg_2020_percentages)//2], 2),
                    round(min(veg_2020_percentages), 2),
                    round(max(veg_2020_percentages), 2),
                    round(sum(veg_2024_percentages) / len(veg_2024_percentages), 2),
                    round(sorted(veg_2024_percentages)[len(veg_2024_percentages)//2], 2),
                    round(min(veg_2024_percentages), 2),
                    round(max(veg_2024_percentages), 2),
                    round(sum(veg_changes) / len(veg_changes), 2),
                    round(sorted(veg_changes)[len(veg_changes)//2], 2),
                    round(min(veg_changes), 2),
                    round(max(veg_changes), 2),
                    len([v for v in veg_changes if v > 0]),
                    len([v for v in veg_changes if v < 0]),
                    len([v for v in veg_changes if v == 0]),
                    round(sum(processing_times) / 3600, 2),
                    round(sum(processing_times) / len(processing_times), 2)
                ]
            }
            
            with open(summary_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['metric', 'value'])
                writer.writeheader()
                for i in range(len(summary_stats['metric'])):
                    writer.writerow({
                        'metric': summary_stats['metric'][i],
                        'value': summary_stats['value'][i]
                    })
            
            print(f"✅ Summary statistics CSV saved: {summary_csv_path}")
        
        # Top cities by vegetation change
        if successful_results:
            change_csv_path = self.output_dir / f"top_cities_by_vegetation_change_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Sort by absolute vegetation change (descending)
            top_changes = sorted(successful_results, key=lambda x: abs(x['vegetation_percentage_change']), reverse=True)
            
            with open(change_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['rank', 'city', 'country', 'vegetation_2020', 'vegetation_2024', 'change_percentage', 'change_direction']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, city in enumerate(top_changes[:20]):  # Top 20
                    change_direction = '↗️ Increase' if city['vegetation_percentage_change'] > 0 else '↘️ Decrease' if city['vegetation_percentage_change'] < 0 else '➡️ No Change'
                    writer.writerow({
                        'rank': i + 1,
                        'city': city['city'],
                        'country': city['country'],
                        'vegetation_2020': city['vegetation_percentage_2020'],
                        'vegetation_2024': city['vegetation_percentage_2024'],
                        'change_percentage': city['vegetation_percentage_change'],
                        'change_direction': change_direction
                    })
            
            print(f"✅ Top cities by change CSV saved: {change_csv_path}")
    
    def generate_summary_report(self):
        """Generate a text summary report with year comparison"""
        report_path = self.output_dir / f"year_comparison_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("BATCH CITY PROCESSING SUMMARY REPORT - YEAR COMPARISON (2020 vs 2024)\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total cities processed: {len(self.results)}\n")
            f.write(f"Successful cities: {len([r for r in self.results if r['status'] == 'success'])}\n")
            f.write(f"Failed cities: {len([r for r in self.results if r['status'] == 'failed'])}\n\n")
            
            if self.failed_cities:
                f.write("FAILED CITIES:\n")
                f.write("-" * 20 + "\n")
                for city in self.failed_cities:
                    f.write(f"- {city}\n")
                f.write("\n")
            
            successful_results = [r for r in self.results if r['status'] == 'success']
            if successful_results:
                f.write("YEAR COMPARISON SUMMARY:\n")
                f.write("-" * 30 + "\n")
                
                # Top 10 cities by vegetation change
                top_changes = sorted(successful_results, key=lambda x: abs(x['vegetation_percentage_change']), reverse=True)[:10]
                f.write("Top 10 Cities by Absolute Vegetation Change (2020→2024):\n")
                for i, city in enumerate(top_changes):
                    change_symbol = "↗️" if city['vegetation_percentage_change'] > 0 else "↘️" if city['vegetation_percentage_change'] < 0 else "➡️"
                    f.write(f"{i+1:2d}. {city['city']}, {city['country']}: {city['vegetation_percentage_change']:+.1f}% {change_symbol}\n")
                    f.write(f"    (2020: {city['vegetation_percentage_2020']:.1f}% → 2024: {city['vegetation_percentage_2024']:.1f}%)\n")
                
                f.write("\n")
                
                # Statistics
                veg_2020_percentages = [r['vegetation_percentage_2020'] for r in successful_results]
                veg_2024_percentages = [r['vegetation_percentage_2024'] for r in successful_results]
                veg_changes = [r['vegetation_percentage_change'] for r in successful_results]
                
                f.write(f"Vegetation Coverage Statistics:\n")
                f.write(f"  2020 Average: {sum(veg_2020_percentages) / len(veg_2020_percentages):.1f}%\n")
                f.write(f"  2024 Average: {sum(veg_2024_percentages) / len(veg_2024_percentages):.1f}%\n")
                f.write(f"  Average Change: {sum(veg_changes) / len(veg_changes):+.1f}%\n")
                f.write(f"  Cities with Increase: {len([v for v in veg_changes if v > 0])}\n")
                f.write(f"  Cities with Decrease: {len([v for v in veg_changes if v < 0])}\n")
                f.write(f"  Cities with No Change: {len([v for v in veg_changes if v == 0])}\n")
        
        print(f"✅ Summary report saved: {report_path}")

def main():
    """Main function to run the batch processor with year comparison"""
    print("🌍 BATCH CITY PROCESSOR - YEAR COMPARISON (2020 vs 2024)")
    print("=" * 60)
    
    # Check if cities.json exists
    if not os.path.exists("cities.json"):
        print("❌ Error: cities.json not found in current directory")
        print("Please run this script from the project root directory")
        sys.exit(1)
    
    # Parse optional filters
    selected_ids = []
    selected_names = []
    if '--cities' in sys.argv:
        idx = sys.argv.index('--cities')
        if idx + 1 < len(sys.argv):
            selected_names = [s.strip() for s in sys.argv[idx+1].split(',') if s.strip()]
    if '--city-ids' in sys.argv:
        idx = sys.argv.index('--city-ids')
        if idx + 1 < len(sys.argv):
            selected_ids = [s.strip() for s in sys.argv[idx+1].split(',') if s.strip()]
    annual_mode = '--annual' in sys.argv

    # Initialize processor
    processor = BatchCityProcessor(selected_city_ids=selected_ids or None, selected_city_names=selected_names or None, annual_mode=annual_mode)
    
    try:
        # Process all cities with year comparison
        processor.process_all_cities()
        
        # Generate reports
        processor.generate_csv_reports()
        processor.generate_summary_report()
        
        print(f"\n🎉 BATCH PROCESSING WITH YEAR COMPARISON COMPLETED SUCCESSFULLY!")
        print(f"📁 All results saved in: {processor.output_dir}")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Processing interrupted by user")
        print(f"📊 Partial results saved in: {processor.output_dir}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print(f"🔍 Full error: {traceback.format_exc()}")
        print(f"📊 Partial results saved in: {processor.output_dir}")

if __name__ == "__main__":
    main()
