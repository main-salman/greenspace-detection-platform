export interface City {
  city_id: string;
  country: string;
  state_province: string;
  city: string;
  latitude: string;
  longitude: string;
  notification_email: string;
  polygon_geojson: {
    type: string;
    properties: object;
    geometry: {
      type: string;
      coordinates: number[][][];
    };
  };
  // Add optional state field for better compatibility
  state?: string;
}

export interface ProcessingConfig {
  city: City;
  startMonth: string;
  startYear: number;
  endMonth: string;
  endYear: number;
  ndviThreshold: number;
  cloudCoverageThreshold: number;
  enableVegetationIndices: boolean;
  enableAdvancedCloudDetection: boolean;
}

export interface GeographicBounds {
  north: number;
  south: number;
  east: number;
  west: number;
  transform?: any;
  crs?: any;
  original_shape?: [number, number];
  processed_shape?: [number, number];
}

export interface ProcessingConfigSummary {
  ndvi_threshold: number;
  cloud_threshold: number;
  highlight_alpha: number;
  date_range: string;
}

export interface CityInfo {
  name: string;
  center_lat: number;
  center_lon: number;
}

export interface VegetationSummary {
  vegetation_percentage: number;
  high_density_percentage: number;
  medium_density_percentage: number;
  low_density_percentage: number;
  total_pixels: number;
  vegetation_pixels: number;
  images_processed: number;
  images_found: number;
  ndvi_threshold: number;
  geographic_bounds?: GeographicBounds;
  city_info?: CityInfo;
  processing_config?: ProcessingConfigSummary;
  output_files: string[];
}

export interface ProcessingStatus {
  id: string;
  status: 'pending' | 'downloading' | 'preprocessing' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  startTime: Date;
  endTime?: Date;
  result?: {
    downloadedImages: number;
    processedComposites: number;
    vegetationPercentage: number;
    highDensityPercentage: number;
    mediumDensityPercentage: number;
    lowDensityPercentage: number;
    ndviThreshold?: number;
    outputFiles: string[];
    summary?: VegetationSummary; // Enhanced summary data
  };
}

export interface SatelliteData {
  sentinel1Items: number;
  sentinel2Items: number;
  totalDownloaded: number;
}

export interface VegetationResult {
  ndviRange: [number, number];
  vegetationPixels: number;
  totalPixels: number;
  vegetationPercentage: number;
  highDensityPercentage: number;  // NDVI > 0.7 (enhanced thresholds)
  mediumDensityPercentage: number; // NDVI 0.5-0.7
  lowDensityPercentage: number;    // NDVI threshold-0.5
  ndviThreshold: number;
  outputPath: string;
}

// Legacy interface for backwards compatibility
export interface ProcessingResult {
  downloadedImages: number;
  processedComposites: number;
  vegetationPercentage: number;
  highDensityPercentage: number;
  mediumDensityPercentage: number;
  lowDensityPercentage: number;
  outputFiles: string[];
  summary?: VegetationSummary; // Add satellite bounds data
} 