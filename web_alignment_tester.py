#!/usr/bin/env python3
"""
Web-based Alignment Testing API
Integrates with Next.js app for real-time alignment testing
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
from pathlib import Path
import threading
import queue
import time
from alignment_testing_system import AlignmentTestingSystem
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for Next.js integration

# Global variables for testing
current_test = None
test_queue = queue.Queue()
test_results = {}

class WebAlignmentTester(AlignmentTestingSystem):
    """Web-friendly version of alignment testing system"""
    
    def __init__(self, city, province, country):
        super().__init__(city, province, country)
        self.test_id = None
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates"""
        self.progress_callback = callback
    
    def emit_progress(self, message, progress_percent=None, data=None):
        """Emit progress update"""
        if self.progress_callback:
            self.progress_callback({
                'test_id': self.test_id,
                'message': message,
                'progress': progress_percent,
                'data': data,
                'timestamp': time.time()
            })
    
    def run_web_alignment_test(self, test_id):
        """Run alignment test with web progress reporting"""
        self.test_id = test_id
        
        try:
            self.emit_progress("Starting alignment test...", 0)
            
            # Get city bounds
            self.emit_progress("Getting city bounds...", 10)
            bounds = self.get_city_bounds()
            if not bounds:
                raise Exception("Could not get city bounds")
            
            # Download satellite data
            self.emit_progress("Downloading satellite data...", 20)
            satellite_data = self.download_satellite_data(bounds)
            
            # Iterative alignment testing
            results = []
            total_iterations = min(10, self.max_iterations)  # Limit for web
            
            for iteration in range(total_iterations):
                progress = 30 + (iteration / total_iterations) * 60
                self.emit_progress(f"Testing alignment - iteration {iteration + 1}", progress)
                
                # Create test map
                map_path = self.create_test_map(bounds, satellite_data, iteration)
                
                # Capture screenshot
                screenshot_path = self.capture_screenshot(map_path, iteration)
                
                # Analyze alignment
                alignment_result = self.analyze_alignment(screenshot_path, iteration)
                results.append(alignment_result)
                
                # Check if alignment is acceptable
                if alignment_result['is_acceptable']:
                    self.emit_progress(f"Perfect alignment achieved! Misalignment: {alignment_result['misalignment_meters']:.3f}m", 100)
                    break
                
                # Apply corrections for next iteration
                satellite_data = self.correct_alignment(satellite_data, alignment_result, bounds)
                
                self.emit_progress(f"Iteration {iteration + 1}: {alignment_result['misalignment_meters']:.1f}m misalignment", progress)
            
            # Generate report
            self.emit_progress("Generating report...", 95)
            self.generate_alignment_report(results)
            
            self.emit_progress("Test completed!", 100, {
                'results': results,
                'final_misalignment': results[-1]['misalignment_meters'] if results else float('inf'),
                'success': any(r['is_acceptable'] for r in results)
            })
            
            return results
            
        except Exception as e:
            self.emit_progress(f"Test failed: {str(e)}", -1)
            logger.error(f"Web alignment test failed: {e}")
            raise
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()

# API Routes

@app.route('/api/alignment/start', methods=['POST'])
def start_alignment_test():
    """Start a new alignment test"""
    global current_test
    
    try:
        data = request.get_json()
        city = data.get('city', 'Toronto')
        province = data.get('province', 'Ontario')
        country = data.get('country', 'Canada')
        tolerance = data.get('tolerance', 1.0)
        
        # Generate test ID
        test_id = f"test_{int(time.time())}"
        
        # Create progress tracking
        progress_updates = []
        
        def progress_callback(update):
            progress_updates.append(update)
            test_results[test_id] = {
                'status': 'running',
                'progress': progress_updates[-1],
                'all_updates': progress_updates
            }
        
        # Create tester
        tester = WebAlignmentTester(city, province, country)
        tester.tolerance_meters = tolerance
        tester.set_progress_callback(progress_callback)
        
        # Start test in background thread
        def run_test():
            try:
                results = tester.run_web_alignment_test(test_id)
                test_results[test_id]['status'] = 'completed'
                test_results[test_id]['results'] = results
            except Exception as e:
                test_results[test_id]['status'] = 'failed'
                test_results[test_id]['error'] = str(e)
        
        thread = threading.Thread(target=run_test)
        thread.daemon = True
        thread.start()
        
        # Initialize test result
        test_results[test_id] = {
            'status': 'starting',
            'city': city,
            'province': province,
            'country': country,
            'tolerance': tolerance,
            'start_time': time.time()
        }
        
        return jsonify({
            'success': True,
            'test_id': test_id,
            'message': 'Alignment test started'
        })
        
    except Exception as e:
        logger.error(f"Error starting test: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/alignment/status/<test_id>', methods=['GET'])
def get_test_status(test_id):
    """Get status of alignment test"""
    if test_id not in test_results:
        return jsonify({
            'success': False,
            'error': 'Test not found'
        }), 404
    
    return jsonify({
        'success': True,
        'test': test_results[test_id]
    })

@app.route('/api/alignment/screenshot/<test_id>/<int:iteration>', methods=['GET'])
def get_screenshot(test_id, iteration):
    """Get screenshot from specific iteration"""
    try:
        screenshot_path = Path("alignment_testing") / "screenshots" / f"alignment_test_iter_{iteration}.png"
        if screenshot_path.exists():
            return send_file(str(screenshot_path), mimetype='image/png')
        else:
            return jsonify({'error': 'Screenshot not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alignment/report/<test_id>', methods=['GET'])
def get_test_report(test_id):
    """Get detailed test report"""
    if test_id not in test_results:
        return jsonify({'error': 'Test not found'}), 404
    
    test_data = test_results[test_id]
    
    if test_data['status'] != 'completed':
        return jsonify({'error': 'Test not completed'}), 400
    
    return jsonify({
        'success': True,
        'report': {
            'test_id': test_id,
            'city': test_data['city'],
            'province': test_data['province'], 
            'country': test_data['country'],
            'tolerance': test_data['tolerance'],
            'results': test_data.get('results', []),
            'final_result': test_data.get('results', [])[-1] if test_data.get('results') else None,
            'success': any(r['is_acceptable'] for r in test_data.get('results', [])),
            'duration': time.time() - test_data['start_time']
        }
    })

@app.route('/api/alignment/tests', methods=['GET'])
def list_tests():
    """List all tests"""
    return jsonify({
        'success': True,
        'tests': [
            {
                'test_id': test_id,
                'status': data['status'],
                'city': data.get('city'),
                'start_time': data.get('start_time')
            }
            for test_id, data in test_results.items()
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Web Alignment Tester',
        'timestamp': time.time()
    })

if __name__ == '__main__':
    print("🚀 Starting Web Alignment Testing API")
    print("🌐 Server will be available at: http://localhost:5001")
    print("📊 API endpoints:")
    print("   POST /api/alignment/start - Start new test")
    print("   GET  /api/alignment/status/<test_id> - Get test status")
    print("   GET  /api/alignment/screenshot/<test_id>/<iteration> - Get screenshot")
    print("   GET  /api/alignment/report/<test_id> - Get test report")
    print("   GET  /api/alignment/tests - List all tests")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)