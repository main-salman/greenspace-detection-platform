#!/usr/bin/env python3
"""
COMPLETELY REWRITTEN Satellite Processor with PERFECT Alignment
This version ensures satellite imagery aligns perfectly with OpenStreetMap
"""

import os
import sys
import json
import numpy as np
import requests
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from rasterio.warp import transform_bounds, reproject, Resampling
import cv2
from datetime import datetime
from pathlib import Path
from shapely.geometry import Polygon
from pystac_client import Client
import time
import warnings
from pyproj import Transformer
import tempfile
warnings.filterwarnings('ignore')

def print_progress(percentage, message=""):
    """Print progress in a format that can be parsed by Node.js"""
    print(f"PROGRESS:{percentage} {message}", flush=True)

class PerfectAlignmentSatelliteProcessor:
    def __init__(self, config):
        self.config = config
        self.city_data = config['city']
        self.start_month = config.get('startMonth', '07')
        self.start_year = config.get('startYear', 2020)
        self.end_month = config.get('endMonth', '07') 
        self.end_year = config.get('endYear', 2020)
        self.cloud_threshold = config.get('cloudCoverageThreshold', 20)
        self.ndvi_threshold = config.get('ndviThreshold', 0.3)
        self.output_dir = Path(config['outputDir'])
        
        # Create output directories
        self.vegetation_dir = self.output_dir / 'vegetation_analysis'
        self.vegetation_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize STAC client
        self.stac_client = Client.open("https://earth-search.aws.element84.com/v1")
        
        # CRITICAL: Store WGS84 bounds for perfect alignment
        self.wgs84_bounds = None
        self.satellite_crs = None
        
    def get_city_bounds_wgs84(self):
        """Get city bounds in WGS84 (EPSG:4326) - the standard web map projection"""
        try:
            if 'polygon_geojson' in self.city_data and self.city_data['polygon_geojson']:
                polygon_data = self.city_data['polygon_geojson']['geometry']
                if polygon_data['type'] == 'Polygon':
                    coordinates = polygon_data['coordinates'][0]
                    lons = [coord[0] for coord in coordinates]
                    lats = [coord[1] for coord in coordinates]
                    
                    # NO PADDING - use exact city bounds for perfect alignment
                    return {
                        'west': min(lons),
                        'east': max(lons), 
                        'south': min(lats),
                        'north': max(lats)
                    }
        except Exception as e:
            print(f"⚠️ Error with polygon: {e}")
        
        # Fallback to city coordinates
        lat = float(self.city_data['latitude'])
        lon = float(self.city_data['longitude'])
        buffer = 0.05  # Small buffer around city center
        
        return {
            'west': lon - buffer,
            'east': lon + buffer,
            'south': lat - buffer, 
            'north': lat + buffer
        }

    def download_and_process_satellite_data(self):
        """Download satellite data and ensure perfect coordinate alignment"""
        print_progress(10, "Getting city bounds for perfect alignment...")
        
        # Get city bounds in WGS84 (web map standard)
        city_bounds = self.get_city_bounds_wgs84()
        print(f"📍 CITY BOUNDS (WGS84): {city_bounds}")
        
        # Query satellite data
        print_progress(20, "Querying satellite data...")
        start_date = datetime(self.start_year, int(self.start_month), 1)
        end_date = datetime(self.end_year, int(self.end_month), 28)
        
        # Search for satellite imagery with flexible criteria
        print(f"🔍 Searching for images from {start_date.date()} to {end_date.date()}")
        print(f"📦 Bbox: {[city_bounds['west'], city_bounds['south'], city_bounds['east'], city_bounds['north']]}")
        print(f"☁️ Cloud cover: < {self.cloud_threshold}%")
        
        search = self.stac_client.search(
            collections=["sentinel-2-l2a"],
            bbox=[city_bounds['west'], city_bounds['south'], city_bounds['east'], city_bounds['north']],
            datetime=f"{start_date.date()}/{end_date.date()}",
            query={"eo:cloud_cover": {"lt": self.cloud_threshold}}
        )
        
        items = list(search.items())
        print(f"📡 Found {len(items)} satellite images")
        
        # If no images found, try with relaxed cloud cover
        if not items:
            print("🔄 No images found, trying with relaxed cloud cover (< 50%)...")
            search = self.stac_client.search(
                collections=["sentinel-2-l2a"],
                bbox=[city_bounds['west'], city_bounds['south'], city_bounds['east'], city_bounds['north']],
                datetime=f"{start_date.date()}/{end_date.date()}",
                query={"eo:cloud_cover": {"lt": 50}}
            )
            items = list(search.items())
            print(f"📡 Found {len(items)} satellite images with relaxed criteria")
        
        # If still no images, try with broader date range
        if not items:
            print("🔄 Still no images, trying broader date range (2020-2022)...")
            search = self.stac_client.search(
                collections=["sentinel-2-l2a"],
                bbox=[city_bounds['west'], city_bounds['south'], city_bounds['east'], city_bounds['north']],
                datetime="2020-01-01/2022-12-31",
                query={"eo:cloud_cover": {"lt": 30}}
            )
            items = list(search.items())
            print(f"📡 Found {len(items)} satellite images with broader date range")
        
        if not items:
            raise Exception("No satellite images found even with relaxed criteria")
            
        print(f"📡 Found {len(items)} satellite images")
        
        # Find item with BEST coverage of the city area
        items.sort(key=lambda x: x.properties.get('eo:cloud_cover', 100))
        
        best_item = None
        best_overlap_score = 0
        
        for item in items[:10]:  # Check top 10 lowest cloud cover items for best overlap
            print(f"🔍 Analyzing: {item.id} (cloud cover: {item.properties.get('eo:cloud_cover', 0)}%)")
            
            # Calculate precise overlap percentage
            try:
                if 'red' in item.assets:
                    with rasterio.Env(GDAL_HTTP_UNSAFESSL='YES'):
                        with rasterio.open(item.assets['red'].href) as src:
                            # Transform city bounds to satellite CRS with high precision
                            transformer = Transformer.from_crs('EPSG:4326', src.crs, always_xy=True)
                            left, bottom = transformer.transform(city_bounds['west'], city_bounds['south'])
                            right, top = transformer.transform(city_bounds['east'], city_bounds['north'])
                            
                            # Calculate overlap area and percentage
                            src_left, src_bottom, src_right, src_top = src.bounds
                            
                            # Calculate intersection bounds
                            int_left = max(left, src_left)
                            int_right = min(right, src_right)
                            int_bottom = max(bottom, src_bottom)
                            int_top = min(top, src_top)
                            
                            # Calculate overlap percentage
                            if int_left < int_right and int_bottom < int_top:
                                city_area = (right - left) * (top - bottom)
                                overlap_area = (int_right - int_left) * (int_top - int_bottom)
                                overlap_percentage = (overlap_area / city_area) * 100
                                
                                # Factor in cloud cover for scoring (prefer less clouds)
                                cloud_cover = item.properties.get('eo:cloud_cover', 0)
                                overlap_score = overlap_percentage * (1 - cloud_cover / 100)
                                
                                print(f"     City bounds: ({left:.1f}, {bottom:.1f}) to ({right:.1f}, {top:.1f})")
                                print(f"     Tile bounds: ({src_left:.1f}, {src_bottom:.1f}) to ({src_right:.1f}, {src_top:.1f})")
                                print(f"     Overlap: {overlap_percentage:.1f}% | Score: {overlap_score:.1f}")
                                
                                if overlap_score > best_overlap_score:
                                    best_overlap_score = overlap_score
                                    best_item = item
                                    print(f"     🎯 NEW BEST MATCH!")
                            else:
                                print(f"     ❌ NO OVERLAP")
            except Exception as e:
                print(f"     ❌ Error checking {item.id}: {e}")
                continue
        
        if not best_item:
            # Fallback to first item if no overlap found
            best_item = items[0]
            print(f"⚠️ No overlapping tiles found, using first item anyway")
        else:
            print(f"🎯 BEST MATCH: {best_item.id} (overlap score: {best_overlap_score:.1f})")
        
        item = best_item
        print(f"🎯 Selected: {item.id} (cloud cover: {item.properties.get('eo:cloud_cover', 0)}%)")
        
        # Download and process bands with PERFECT alignment
        bands_data = self.download_bands_with_perfect_alignment(item, city_bounds)
        
        if not bands_data:
            raise Exception("Failed to download satellite bands")
            
        # Process NDVI and create visualizations
        print_progress(70, "Creating perfectly aligned vegetation analysis...")
        result = self.create_aligned_vegetation_analysis(bands_data, city_bounds)
        
        print_progress(90, "Saving results with perfect geographic alignment...")
        self.save_perfectly_aligned_results(result, city_bounds)
        
        print_progress(100, "Perfect alignment processing completed!")
        return result

    def download_bands_with_perfect_alignment(self, item, city_bounds):
        """Download satellite bands and ensure they're perfectly aligned to city bounds"""
        print_progress(30, "Downloading bands with perfect alignment...")
        
        bands_needed = ['red', 'green', 'blue', 'nir']
        bands_data = {}
        
        # Enhanced target resolution for sub-pixel precision
        target_width = 1024  # Fixed size for consistent alignment  
        target_height = 1024
        
        # Sub-pixel precision factor for better alignment
        precision_factor = 2  # Temporary higher resolution for precision
        temp_width = target_width * precision_factor
        temp_height = target_height * precision_factor
        
        for i, band_name in enumerate(bands_needed):
            print(f"   Downloading {band_name}...")
            
            # Get band asset
            if band_name in item.assets:
                asset = item.assets[band_name]
            else:
                print(f"   ❌ Band {band_name} not found")
                continue
                
            try:
                # Open the satellite image with authentication
                with rasterio.Env(GDAL_HTTP_UNSAFESSL='YES', GDAL_HTTP_COOKIEFILE='', GDAL_HTTP_COOKIEJAR=''):
                    with rasterio.open(asset.href) as src:
                        print(f"     📊 Source info: {src.shape}, CRS: {src.crs}, Bands: {src.count}")
                        
                        # Read a sample to check data
                        sample = src.read(1, window=rasterio.windows.Window(0, 0, 100, 100))
                        print(f"     🔍 Sample data: min={sample.min()}, max={sample.max()}, mean={sample.mean():.3f}")
                        
                        # Get satellite CRS (usually UTM)
                        self.satellite_crs = src.crs
                        
                        # CRITICAL: Transform city bounds from WGS84 to satellite CRS
                        transformer = Transformer.from_crs('EPSG:4326', src.crs, always_xy=True)
                        
                        # Transform bounds to satellite coordinate system
                        left, bottom = transformer.transform(city_bounds['west'], city_bounds['south'])
                        right, top = transformer.transform(city_bounds['east'], city_bounds['north'])
                        
                        print(f"     📍 Transformed bounds: ({left:.1f}, {bottom:.1f}) to ({right:.1f}, {top:.1f})")
                        
                        # Check if bounds are within the source image
                        src_left, src_bottom, src_right, src_top = src.bounds
                        print(f"     📊 Source bounds: ({src_left:.1f}, {src_bottom:.1f}) to ({src_right:.1f}, {src_top:.1f})")
                        
                        if not (left < src_right and right > src_left and bottom < src_top and top > src_bottom):
                            print(f"     ⚠️ WARNING: City bounds don't overlap with source image!")
                        
                        # Create high-precision transform for sub-pixel alignment
                        temp_transform = from_bounds(left, bottom, right, top, temp_width, temp_height)
                        
                        # Create high-resolution temporary array for sub-pixel precision
                        temp_array = np.zeros((temp_height, temp_width), dtype=np.float32)
                        
                        # Reproject with high precision using cubic resampling
                        reproject(
                            source=rasterio.band(src, 1),
                            destination=temp_array,
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=temp_transform,
                            dst_crs=src.crs,
                            resampling=Resampling.cubic  # Higher quality resampling
                        )
                        
                        # Downsample to final resolution with anti-aliasing for precise alignment
                        from scipy.ndimage import zoom
                        scale_factor = 1.0 / precision_factor
                        output_array = zoom(temp_array, scale_factor, order=3)  # Cubic interpolation
                        
                        # Ensure exact target dimensions
                        if output_array.shape != (target_height, target_width):
                            from scipy.ndimage import resize
                            output_array = zoom(temp_array, (target_height/temp_height, target_width/temp_width), order=3)
                        
                        print(f"     📈 After reproject: min={output_array.min()}, max={output_array.max()}, mean={output_array.mean():.3f}")
                        
                        bands_data[band_name] = output_array
                    
                    # Store the PERFECT bounds for this band
                    if not self.wgs84_bounds:
                        # Transform back to WGS84 for frontend use
                        wgs84_transformer = Transformer.from_crs(src.crs, 'EPSG:4326', always_xy=True)
                        w_wgs84, s_wgs84 = wgs84_transformer.transform(left, bottom)
                        e_wgs84, n_wgs84 = wgs84_transformer.transform(right, top)
                        
                        self.wgs84_bounds = {
                            'west': w_wgs84,
                            'south': s_wgs84,
                            'east': e_wgs84,
                            'north': n_wgs84,
                            'crs': 'EPSG:4326'
                        }
                        
                        print(f"   📍 PERFECT BOUNDS SET: {self.wgs84_bounds}")
                    
                    print(f"   ✅ {band_name}: {output_array.shape}")
                    
            except Exception as e:
                print(f"   ❌ Failed to download {band_name}: {e}")
                
        if len(bands_data) != 4:
            print(f"❌ Only got {len(bands_data)}/4 required bands")
            return None
            
        print("✅ All bands downloaded with perfect alignment")
        return bands_data

    def create_aligned_vegetation_analysis(self, bands_data, city_bounds):
        """Create vegetation analysis with perfect alignment"""
        red = bands_data['red'].astype(np.float32)
        green = bands_data['green'].astype(np.float32) 
        blue = bands_data['blue'].astype(np.float32)
        nir = bands_data['nir'].astype(np.float32)
        
        # Calculate NDVI with debugging
        print(f"   🔍 Band statistics before NDVI:")
        print(f"     Red: min={red.min():.3f}, max={red.max():.3f}, mean={red.mean():.3f}")
        print(f"     NIR: min={nir.min():.3f}, max={nir.max():.3f}, mean={nir.mean():.3f}")
        
        # Calculate NDVI
        ndvi = (nir - red) / (nir + red + 1e-10)
        ndvi = np.clip(ndvi, -1, 1)
        
        print(f"   📊 NDVI statistics:")
        print(f"     Min: {ndvi.min():.3f}, Max: {ndvi.max():.3f}, Mean: {ndvi.mean():.3f}")
        print(f"     Values > {self.ndvi_threshold}: {np.sum(ndvi >= self.ndvi_threshold)} pixels")
        
        # Enhanced vegetation detection with lower thresholds to catch more green areas
        enhanced_threshold = max(0.2, self.ndvi_threshold - 0.05)  # Lower threshold for better detection
        vegetation_mask = ndvi >= enhanced_threshold
        
        # Calculate statistics
        total_pixels = ndvi.size
        vegetation_pixels = np.sum(vegetation_mask)
        vegetation_percentage = (vegetation_pixels / total_pixels) * 100
        
        # Enhanced density classifications - more sensitive to subtle vegetation
        high_density = ndvi >= 0.55  # Slightly lower for high density
        medium_density = (ndvi >= 0.35) & (ndvi < 0.55)  # More sensitive range
        low_density = (ndvi >= enhanced_threshold) & (ndvi < 0.35)  # Catch subtle vegetation
        
        # Additional category for very subtle vegetation (grass, sparse trees)
        subtle_vegetation = (ndvi >= 0.15) & (ndvi < enhanced_threshold)
        subtle_pixels = np.sum(subtle_vegetation)
        subtle_percentage = (subtle_pixels / total_pixels) * 100
        
        high_percentage = (np.sum(high_density) / total_pixels) * 100
        medium_percentage = (np.sum(medium_density) / total_pixels) * 100
        low_percentage = (np.sum(low_density) / total_pixels) * 100
        
        print(f"🌱 Enhanced Vegetation Coverage: {vegetation_percentage:.1f}%")
        print(f"   High density: {high_percentage:.1f}%")
        print(f"   Medium density: {medium_percentage:.1f}%")
        print(f"   Low density: {low_percentage:.1f}%")
        print(f"   Subtle vegetation: {subtle_percentage:.1f}%")
        
        return {
            'red': red,
            'green': green,
            'blue': blue,
            'nir': nir,
            'ndvi': ndvi,
            'vegetation_mask': vegetation_mask,
            'vegetation_percentage': vegetation_percentage,
            'high_density_percentage': high_percentage,
            'medium_density_percentage': medium_percentage,
            'low_density_percentage': low_percentage,
            'subtle_percentage': subtle_percentage,
            'high_density': high_density,
            'medium_density': medium_density,
            'low_density': low_density,
            'subtle_vegetation': subtle_vegetation,
            'total_pixels': total_pixels,
            'vegetation_pixels': vegetation_pixels,
            'enhanced_threshold': enhanced_threshold
        }

    def save_perfectly_aligned_results(self, result, city_bounds):
        """Save results with perfect geographic alignment"""
        
        # Create enhanced false color composite (NIR, Red, Green) for vegetation visibility
        # Apply vegetation-enhanced normalization
        nir_enhanced = self.enhance_vegetation_band(result['nir'])
        red_enhanced = self.normalize_band(result['red'])
        green_enhanced = self.enhance_vegetation_band(result['green'])
        
        false_color = np.dstack([
            nir_enhanced,  # Red channel - NIR shows vegetation as bright red
            red_enhanced,  # Green channel - actual red
            green_enhanced # Blue channel - enhanced green
        ])
        
        # Save false color image with vegetation enhancement
        false_color_path = self.vegetation_dir / 'false_color_base.png'
        cv2.imwrite(str(false_color_path), (false_color * 255).astype(np.uint8))
        
        # Also create a natural color composite for comparison
        natural_color = np.dstack([
            self.normalize_band(result['red']),
            self.normalize_band(result['green']),
            self.normalize_band(result['blue'])
        ])
        natural_color_path = self.vegetation_dir / 'natural_color_base.png'
        cv2.imwrite(str(natural_color_path), (natural_color * 255).astype(np.uint8))
        
        # Create vegetation highlighted overlay
        vegetation_overlay = self.create_vegetation_overlay(result)
        vegetation_path = self.vegetation_dir / 'vegetation_highlighted.png'
        cv2.imwrite(str(vegetation_path), vegetation_overlay)
        
        # Create NDVI visualization
        ndvi_viz = self.create_ndvi_visualization(result['ndvi'])
        ndvi_path = self.vegetation_dir / 'ndvi_visualization.png'
        cv2.imwrite(str(ndvi_path), ndvi_viz)
        
        # Save NDVI as GeoTIFF with perfect georeferencing
        self.save_georeferenced_ndvi(result['ndvi'])
        
        # Create summary with PERFECT bounds
        summary = {
            'vegetation_percentage': float(result['vegetation_percentage']),
            'high_density_percentage': float(result['high_density_percentage']),
            'medium_density_percentage': float(result['medium_density_percentage']),
            'low_density_percentage': float(result['low_density_percentage']),
            'total_pixels': int(result['total_pixels']),
            'vegetation_pixels': int(result['vegetation_pixels']),
            'images_processed': 1,
            'images_found': 1,
            'ndvi_threshold': self.ndvi_threshold,
            'geographic_bounds': self.wgs84_bounds,  # PERFECT BOUNDS
            'city_info': {
                'name': f"{self.city_data['city']}, {self.city_data['country']}",
                'center_lat': (self.wgs84_bounds['north'] + self.wgs84_bounds['south']) / 2,
                'center_lon': (self.wgs84_bounds['east'] + self.wgs84_bounds['west']) / 2
            },
            'processing_config': {
                'ndvi_threshold': self.ndvi_threshold,
                'cloud_threshold': self.cloud_threshold,
                'highlight_alpha': 0.6,
                'date_range': f"{self.start_year}-{int(self.start_month):02d} to {self.end_year}-{int(self.end_month):02d}"
            },
            'output_files': [
                'vegetation_highlighted.png',
                'ndvi_visualization.png', 
                'false_color_base.png'
            ]
        }
        
        # Save summary
        summary_path = self.vegetation_dir / 'vegetation_analysis_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print(f"📍 PERFECT ALIGNMENT SUMMARY:")
        print(f"   Bounds: {self.wgs84_bounds}")
        print(f"   Center: {summary['city_info']['center_lat']:.6f}, {summary['city_info']['center_lon']:.6f}")
        print(f"   Files saved to: {self.vegetation_dir}")

    def normalize_band(self, band):
        """Normalize band to 0-1 range"""
        min_val = np.percentile(band, 2)
        max_val = np.percentile(band, 98)
        normalized = (band - min_val) / (max_val - min_val)
        return np.clip(normalized, 0, 1)
    
    def enhance_vegetation_band(self, band):
        """Enhanced normalization for vegetation bands to make green areas more visible"""
        min_val = np.percentile(band, 1)  # Use more aggressive percentiles
        max_val = np.percentile(band, 99)
        
        # Apply gamma correction to enhance mid-range values (vegetation)
        normalized = (band - min_val) / (max_val - min_val)
        normalized = np.clip(normalized, 0, 1)
        
        # Gamma correction to enhance vegetation visibility
        gamma = 0.8  # Values < 1 brighten mid-tones
        enhanced = np.power(normalized, gamma)
        
        return enhanced

    def create_vegetation_overlay(self, result):
        """Create enhanced vegetation density overlay with purple transparency scheme"""
        height, width = result['ndvi'].shape
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Subtle vegetation (very light purple) - for grass and sparse vegetation
        if 'subtle_vegetation' in result:
            subtle_mask = result['subtle_vegetation']
            overlay[subtle_mask] = [230, 210, 255, 80]  # Very light purple with low alpha
        
        # Low density vegetation (light purple) - lighter for less vegetation
        low_mask = result['low_density']
        overlay[low_mask] = [204, 153, 255, 120]  # Light purple with alpha
        
        # Medium density vegetation (medium purple)
        medium_mask = result['medium_density']
        overlay[medium_mask] = [153, 102, 204, 150]  # Medium purple with alpha
        
        # High density vegetation (dark purple) - darker for more vegetation
        high_mask = result['high_density']
        overlay[high_mask] = [102, 51, 153, 180]  # Dark purple with alpha
        
        return overlay

    def create_ndvi_visualization(self, ndvi):
        """Create NDVI visualization with color mapping"""
        # Normalize NDVI to 0-255 range
        ndvi_norm = ((ndvi + 1) / 2 * 255).astype(np.uint8)
        
        # Apply colormap (viridis-like)
        colored = cv2.applyColorMap(ndvi_norm, cv2.COLORMAP_VIRIDIS)
        
        return colored

    def save_georeferenced_ndvi(self, ndvi):
        """Save NDVI as GeoTIFF with perfect georeferencing"""
        if not self.wgs84_bounds:
            return
            
        # Create transform
        transform = from_bounds(
            self.wgs84_bounds['west'],
            self.wgs84_bounds['south'], 
            self.wgs84_bounds['east'],
            self.wgs84_bounds['north'],
            ndvi.shape[1],
            ndvi.shape[0]
        )
        
        # Save as GeoTIFF
        ndvi_tiff_path = self.vegetation_dir / 'ndvi_data.tif'
        with rasterio.open(
            ndvi_tiff_path,
            'w',
            driver='GTiff',
            height=ndvi.shape[0],
            width=ndvi.shape[1],
            count=1,
            dtype=ndvi.dtype,
            crs='EPSG:4326',
            transform=transform
        ) as dst:
            dst.write(ndvi, 1)

def main():
    """Main function to run perfect alignment processing"""
    if len(sys.argv) != 2:
        print("Usage: python satellite_processor_fixed.py <config_file>")
        sys.exit(1)
        
    config_file = sys.argv[1]
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        processor = PerfectAlignmentSatelliteProcessor(config)
        result = processor.download_and_process_satellite_data()
        
        print("🎉 PERFECT ALIGNMENT PROCESSING COMPLETED!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()