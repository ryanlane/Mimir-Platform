#!/usr/bin/env python3
"""
Test Runner Script for Mimir API
Provides convenient test execution with different configurations
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found. Make sure pytest is installed.")
        return False


def install_test_dependencies():
    """Install test dependencies"""
    cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"]
    return run_command(cmd, "Installing test dependencies")


def run_unit_tests(verbose=False, coverage=False):
    """Run unit tests"""
    cmd = [sys.executable, "-m", "pytest", "tests/unit/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    cmd.append("--tb=short")
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run integration tests"""
    cmd = [sys.executable, "-m", "pytest", "tests/integration/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("--tb=short")
    
    return run_command(cmd, "Integration Tests")


def run_all_tests(verbose=False, coverage=False):
    """Run all tests"""
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    cmd.append("--tb=short")
    
    return run_command(cmd, "All Tests")


def run_specific_test(test_path, verbose=False):
    """Run a specific test file or test function"""
    cmd = [sys.executable, "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("--tb=short")
    
    return run_command(cmd, f"Specific Test: {test_path}")


def run_tests_by_marker(marker, verbose=False):
    """Run tests by marker (e.g., unit, integration, slow)"""
    cmd = [sys.executable, "-m", "pytest", "-m", marker, "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("--tb=short")
    
    return run_command(cmd, f"Tests with marker: {marker}")


def check_test_setup():
    """Check if test environment is properly set up"""
    print("\n🔍 Checking test environment setup...")
    
    # Check if we're in the right directory
    if not Path("pytest.ini").exists():
        print("❌ pytest.ini not found. Make sure you're in the api-service directory.")
        return False
    
    # Check if tests directory exists
    if not Path("tests").exists():
        print("❌ tests directory not found.")
        return False
    
    # Check if requirements files exist
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found.")
        return False
    
    if not Path("requirements-test.txt").exists():
        print("❌ requirements-test.txt not found.")
        return False
    
    print("✅ Test environment setup looks good!")
    return True


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="Test runner for Mimir API")
    parser.add_argument("--install-deps", action="store_true", 
                       help="Install test dependencies")
    parser.add_argument("--unit", action="store_true", 
                       help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", 
                       help="Run integration tests only")
    parser.add_argument("--all", action="store_true", 
                       help="Run all tests")
    parser.add_argument("--test", type=str, 
                       help="Run specific test file or function")
    parser.add_argument("--marker", type=str, 
                       help="Run tests with specific marker")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output")
    parser.add_argument("--coverage", action="store_true", 
                       help="Run with coverage reporting")
    parser.add_argument("--check", action="store_true", 
                       help="Check test environment setup")
    
    args = parser.parse_args()
    
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("🧪 Mimir API Test Runner")
    print(f"Working directory: {os.getcwd()}")
    
    # Check test setup first
    if args.check or not any([args.install_deps, args.unit, args.integration, 
                             args.all, args.test, args.marker]):
        if not check_test_setup():
            sys.exit(1)
        if args.check:
            sys.exit(0)
    
    success = True
    
    # Install dependencies if requested
    if args.install_deps:
        success = install_test_dependencies() and success
    
    # Run specific test types
    if args.unit:
        success = run_unit_tests(args.verbose, args.coverage) and success
    elif args.integration:
        success = run_integration_tests(args.verbose) and success
    elif args.all:
        success = run_all_tests(args.verbose, args.coverage) and success
    elif args.test:
        success = run_specific_test(args.test, args.verbose) and success
    elif args.marker:
        success = run_tests_by_marker(args.marker, args.verbose) and success
    else:
        # Default: run basic setup check and unit tests
        print("\n💡 No specific test type specified. Running unit tests...")
        success = run_unit_tests(args.verbose, args.coverage) and success
    
    # Summary
    print(f"\n{'='*60}")
    if success:
        print("🎉 All requested tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
