# 🎯 Satellite-OSM Alignment Testing System

This system will automatically test and correct satellite imagery alignment with OpenStreetMap until perfect alignment (≤1m misalignment) is achieved.

## 🚀 Quick Start

### 1. Setup (One-time)
```bash
# Install dependencies and setup system
python setup_alignment_testing.py
```

### 2. Run Alignment Test
```bash
# Quick test with Toronto (default)
python run_alignment_test.py

# Test specific city
python run_alignment_test.py --city "New York" --province "New York" --country "USA"

# Custom tolerance (default is 1.0m)
python run_alignment_test.py --tolerance 0.5

# More iterations for difficult cases
python run_alignment_test.py --max-iter 100
```

### 3. Web Interface (Optional)
```bash
# Start web API server
python web_alignment_tester.py

# Open Next.js app and use AlignmentTester component
```

## 📁 System Components

### Core Files
- `alignment_testing_system.py` - Main alignment testing engine
- `web_alignment_tester.py` - Web API for Next.js integration  
- `run_alignment_test.py` - Quick command-line runner
- `setup_alignment_testing.py` - Automated setup script

### React Component
- `greenspace-app/src/components/AlignmentTester.tsx` - Web UI component

### Requirements
- `alignment_testing_requirements.txt` - Python dependencies
- `web_requirements.txt` - Additional web API dependencies

## 🔧 How It Works

### 1. **Proper Georeferencing**
- Downloads Sentinel-2 satellite imagery with native CRS information
- Reprojects to Web Mercator (EPSG:3857) - same as OpenStreetMap
- Maintains precise coordinate transformations throughout processing

### 2. **Automated Testing**
- Creates test maps overlaying satellite imagery on OSM base maps
- Takes automated screenshots using headless Chrome
- Analyzes alignment using computer vision techniques

### 3. **Iterative Correction**
- Detects misalignment patterns in each iteration
- Applies spatial corrections based on analysis
- Continues until target tolerance (≤1m) is achieved

### 4. **Validation**
- Uses roads, intersections, and landmarks as reference points
- Fetches reference data from Overpass API (OpenStreetMap)
- Validates alignment against known geographic features

## 📊 Output Files

### Screenshots
- `alignment_testing/screenshots/` - Test screenshots for each iteration
- `alignment_test_iter_N.png` - Screenshot from iteration N

### Satellite Data
- `alignment_testing/satellite_data/` - Processed satellite imagery
- `{city}_satellite_georeferenced.tif` - Georeferenced satellite composite

### Results
- `alignment_testing/results/` - Test reports and analysis
- `alignment_report_YYYYMMDD_HHMMSS.json` - Detailed test results
- `alignment_progress_YYYYMMDD_HHMMSS.png` - Progress visualization

## 🎛️ Configuration Options

### Command Line
```bash
python run_alignment_test.py \
  --city "Toronto" \
  --province "Ontario" \
  --country "Canada" \
  --tolerance 1.0 \
  --max-iter 50
```

### Web API
```bash
curl -X POST http://localhost:5001/api/alignment/start \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Toronto",
    "province": "Ontario", 
    "country": "Canada",
    "tolerance": 1.0
  }'
```

## 📈 Success Criteria

### Perfect Alignment ✅
- Misalignment ≤ 1.0 meters (configurable)
- All roads, intersections, landmarks align precisely
- Satellite features match OSM features exactly

### Acceptable Alignment ⚠️
- Misalignment 1-5 meters
- Major features align, minor discrepancies present

### Failed Alignment ❌
- Misalignment > 5 meters
- Visible offset between satellite and map features
- System will continue iterating to improve

## 🔍 Troubleshooting

### Missing Dependencies
```bash
# Run setup again
python setup_alignment_testing.py

# Manual install
pip install -r alignment_testing_requirements.txt
```

### Chrome Driver Issues
```bash
# Install manually
pip install chromedriver-autoinstaller
python -c "import chromedriver_autoinstaller; chromedriver_autoinstaller.install()"
```

### Web API Not Starting
```bash
# Install web dependencies
pip install -r web_requirements.txt

# Check port availability
lsof -i :5001
```

### No Satellite Data Found
- Check internet connection
- Verify city name spelling
- Try different date range (system uses 2020-06 by default)
- Check cloud coverage threshold

## 🏗️ Integration with Next.js App

### 1. Add Component
```tsx
import AlignmentTester from '@/components/AlignmentTester';

// In your page
<AlignmentTester />
```

### 2. Start Web API
```bash
python web_alignment_tester.py
```

### 3. Configure CORS (if needed)
The web API includes CORS headers for localhost development.

## 📚 Technical Details

### Coordinate Systems
- **Input**: Sentinel-2 native CRS (typically UTM zones)
- **Processing**: Web Mercator (EPSG:3857)
- **Output**: Web Mercator for web map compatibility

### Image Processing
- **Resolution**: 10m pixel resolution in final output
- **Bands**: RGB + NIR for vegetation analysis
- **Resampling**: Bilinear interpolation during reprojection

### Alignment Analysis
- **Feature Detection**: Canny edge detection
- **Line Analysis**: Hough line transform for road detection
- **Scoring**: Composite alignment score (0-100)
- **Correction**: Spatial offset adjustment based on detected patterns

## 🎯 Expected Results

After running this system, you should achieve:

1. **Perfect satellite-map alignment** (≤1m misalignment)
2. **Automated verification** through visual screenshots
3. **Detailed reporting** of alignment accuracy
4. **Iterative improvement** until success criteria met

The system addresses the root cause of your 10-150km misalignment issues by properly handling coordinate reference systems and implementing precise geometric transformations.

## 🆘 Support

If alignment testing fails after 50 iterations:

1. Check satellite data quality (cloud coverage, availability)
2. Verify coordinate transformation accuracy
3. Adjust tolerance if needed for specific use cases
4. Contact system maintainer for algorithm improvements

---

**Goal**: Zero misalignment between satellite imagery and OpenStreetMap features. Every road, intersection, and landmark should align perfectly.