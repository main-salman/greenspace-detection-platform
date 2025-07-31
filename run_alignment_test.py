#!/usr/bin/env python3
"""
Quick run script for alignment testing
Usage: python run_alignment_test.py
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

try:
    from alignment_testing_system import AlignmentTestingSystem
    import argparse
    
    def main():
        parser = argparse.ArgumentParser(description='Run Satellite-OSM Alignment Test')
        parser.add_argument('--city', default='Toronto', help='City name')
        parser.add_argument('--province', default='Ontario', help='Province/State')
        parser.add_argument('--country', default='Canada', help='Country')
        parser.add_argument('--tolerance', type=float, default=1.0, help='Tolerance in meters (default: 1.0)')
        parser.add_argument('--max-iter', type=int, default=20, help='Maximum iterations (default: 20)')
        parser.add_argument('--setup', action='store_true', help='Run setup first')
        
        args = parser.parse_args()
        
        if args.setup:
            print("🔧 Running setup...")
            os.system(f"{sys.executable} setup_alignment_testing.py")
            print("")
        
        print("🚀 Starting Alignment Test")
        print("="*50)
        print(f"City: {args.city}, {args.province}, {args.country}")
        print(f"Tolerance: ≤{args.tolerance}m")
        print(f"Max Iterations: {args.max_iter}")
        print("="*50)
        
        # Create and run system
        system = AlignmentTestingSystem(args.city, args.province, args.country)
        system.tolerance_meters = args.tolerance
        system.max_iterations = args.max_iter
        
        try:
            results = system.run_full_alignment_test()
            
            if results and any(r['is_acceptable'] for r in results):
                print("\n🎉 ALIGNMENT TEST SUCCESSFUL!")
                final = results[-1]
                print(f"✅ Final misalignment: {final['misalignment_meters']:.3f}m")
                return 0
            else:
                print("\n❌ ALIGNMENT TEST FAILED")
                print("❗ Could not achieve target alignment within maximum iterations")
                return 1
                
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            return 1

    if __name__ == "__main__":
        sys.exit(main())
        
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Please run setup first:")
    print(f"   {sys.executable} setup_alignment_testing.py")
    sys.exit(1)