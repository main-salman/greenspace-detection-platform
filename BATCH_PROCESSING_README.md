# Batch City Processing - Standalone Scripts

This directory contains standalone Python scripts to process all cities from `cities.json` and generate comprehensive CSV reports, bypassing the web interface entirely.

## 🚀 Quick Start

### 1. Test with 3 Cities First
```bash
# Test the system with just 3 cities
python batch_process_test.py
```

### 2. Process All Cities
```bash
# Process all cities (this will take several hours)
python batch_process_all_cities.py
```

## 📁 Files

- **`batch_process_test.py`** - Test script that processes 3 cities first
- **`batch_process_all_cities.py`** - Full batch processor for all cities
- **`batch_requirements.txt`** - Python dependencies
- **`cities.json`** - City data (should be in project root)

## 🔧 Setup

### 1. Install Dependencies
```bash
pip install -r batch_requirements.txt
```

### 2. Ensure Required Files Exist
- `cities.json` in the project root
- `greenspace-app/python_scripts/satellite_processor_fixed.py`

### 3. Run from Project Root
Make sure you're in the project root directory (where `cities.json` is located).

## 📊 Output

### Test Mode (`batch_process_test.py`)
- Creates `test_batch_results/` directory
- Processes 3 cities
- Generates `test_results_YYYYMMDD_HHMMSS.csv`

### Full Mode (`batch_process_all_cities.py`)
- Creates `batch_results/` directory
- Processes all cities in `cities.json`
- Generates multiple CSV files:
  - `all_cities_results_YYYYMMDD_HHMMSS.csv` - Complete results
  - `summary_statistics_YYYYMMDD_HHMMSS.csv` - Statistical summary
  - `top_cities_by_vegetation_YYYYMMDD_HHMMSS.csv` - Top 20 cities
  - `processing_summary_YYYYMMDD_HHMMSS.txt` - Text report

## 📈 CSV Output Fields

Each city result includes:
- **Basic Info**: city_id, city, country, state_province, latitude, longitude
- **Status**: success/failed, processing time, error message
- **Vegetation Data**: vegetation_percentage, high/medium/low density percentages
- **Technical Data**: total_pixels, vegetation_pixels, NDVI mean, images processed

## ⏱️ Processing Time

- **Small cities**: 5-15 minutes each
- **Large cities**: 15-45 minutes each
- **Total for 50+ cities**: 8-24 hours (depending on city sizes and system performance)

## 🛠️ Configuration

The scripts use these default settings:
- **Time Period**: July 2020
- **NDVI Threshold**: 0.3
- **Cloud Coverage**: 20%
- **Advanced Features**: Enabled

To modify settings, edit the `config` dictionary in the scripts.

## 🚨 Important Notes

1. **Internet Required**: Downloads satellite data from STAC APIs
2. **Storage Space**: Each city requires 100MB-1GB of storage
3. **Memory Usage**: 2-4GB RAM during processing
4. **Interruptible**: Use Ctrl+C to stop processing (partial results saved)
5. **Resume Capability**: Delete failed city directories to retry specific cities

## 🔍 Troubleshooting

### Common Issues

1. **Import Error**: Make sure you're running from project root
2. **Memory Issues**: Close other applications during processing
3. **Network Errors**: Check internet connection and STAC API availability
4. **Storage Full**: Ensure sufficient disk space

### Error Handling

- Failed cities are logged with error messages
- Processing continues even if individual cities fail
- All results are saved regardless of failures

## 📞 Support

If you encounter issues:
1. Check the console output for error messages
2. Verify all dependencies are installed
3. Ensure sufficient system resources
4. Check network connectivity for satellite data downloads

## 🎯 Use Cases

- **Research**: Analyze vegetation patterns across multiple cities
- **Comparison**: Compare green space coverage between regions
- **Reporting**: Generate comprehensive vegetation analysis reports
- **Data Export**: Get structured data for further analysis in other tools

---

**Note**: These scripts bypass the web interface completely, so you'll get direct CSV output without the GUI errors you were experiencing.
