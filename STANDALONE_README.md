# Greenspace Standalone App

This is a standalone version of the Greenspace vegetation analysis application.

## Quick Start

### macOS/Linux
Double-click `Greenspace.app` to start the application.

### Windows
Double-click `Greenspace.bat` to start the application.

## Requirements

- Python 3.7+ (the launcher will check and guide you if not installed)
- Internet connection (for downloading satellite imagery)

## First Run

On first run, the launcher will:
1. Create a Python virtual environment
2. Install all required dependencies
3. Start the web server
4. Open the app in your default browser

This setup process only happens once.

## Features

- **City Management**: Add, edit, and delete cities with automatic boundary detection
- **Satellite Analysis**: Download and analyze satellite imagery for vegetation coverage
- **NDVI Calculations**: Advanced vegetation index calculations
- **Batch Processing**: Process multiple cities or time periods
- **Interactive Maps**: View results on interactive maps
- **Data Export**: Download results as images and data files

## Usage

1. **Add a City**: Click "Add City" and enter city details
2. **Configure Analysis**: Set parameters like NDVI threshold and cloud coverage
3. **Start Processing**: Click "Start Processing" to begin satellite analysis
4. **View Results**: Interactive maps and charts will display the results
5. **Download Data**: Export images and data files as needed

## Troubleshooting

### Port Already in Use
If you see "address already in use" error, another instance is running. Close it first.

### Python Not Found
Install Python 3.7+ from python.org and restart the launcher.

### Dependencies Issues
Delete the `local_venv` folder and run the launcher again to reinstall dependencies.

## Technical Details

- **Web Server**: FastAPI serving on localhost:8000
- **UI**: React/Next.js interface served as static files
- **Processing**: Python-based satellite imagery analysis
- **Data**: Sentinel-2 satellite data via STAC API

## Support

For issues or questions, check the main project repository or documentation.