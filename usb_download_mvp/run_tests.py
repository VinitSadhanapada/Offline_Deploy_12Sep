#!/usr/bin/env python3
"""
Simple test runner for the USB Download MVP
Run this to verify everything works correctly
"""
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from test_e2e import run_all_tests

if __name__ == '__main__':
    print("🧪 Running USB Download MVP Test Suite...")
    print("=" * 60)
    
    success = run_all_tests()
    
    if success:
        print("\n🎉 SUCCESS! The application is ready for users.")
        print("   All functionality has been validated end-to-end.")
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        print("   Fix any issues before deploying to users.")
    
    sys.exit(0 if success else 1)