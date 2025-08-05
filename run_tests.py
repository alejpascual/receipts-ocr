#!/usr/bin/env python3
"""Test runner for Japanese Receipt OCR system."""

import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run the complete test suite."""
    print("🧪 Running Japanese Receipt OCR Test Suite")
    print("=" * 50)
    
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    try:
        # Check if pytest is available
        result = subprocess.run([sys.executable, '-m', 'pytest', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ pytest not found. Installing...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest'], check=True)
        
        # Run tests with verbose output
        test_args = [
            sys.executable, '-m', 'pytest',
            'tests/',
            '-v',
            '--tb=short',
            '--durations=10',  # Show 10 slowest tests
        ]
        
        print("Running tests...")
        result = subprocess.run(test_args, cwd=project_root)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
            print("\n📊 Test Coverage Summary:")
            print("  • DateParser: ✅ Date formats, OCR corrections, validation")
            print("  • AmountParser: ✅ Keywords, tax exclusion, smart recovery") 
            print("  • VendorParser: ✅ Major chains, business patterns")
            print("  • Integration: ✅ Real receipt scenarios")
        else:
            print(f"\n❌ Tests failed (exit code: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False
    
    return True

def run_specific_test(test_pattern):
    """Run specific test matching pattern."""
    test_args = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',
        '-k', test_pattern
    ]
    
    result = subprocess.run(test_args)
    return result.returncode == 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test pattern
        pattern = sys.argv[1]
        print(f"Running tests matching: {pattern}")
        success = run_specific_test(pattern)
    else:
        # Run all tests
        success = run_tests()
    
    sys.exit(0 if success else 1)