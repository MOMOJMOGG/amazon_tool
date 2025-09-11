#!/usr/bin/env python3
"""Run comprehensive M2 API tests automatically.

This script executes all the manual API tests from the M2 Testing Guide
automatically, providing a complete verification of the ETL pipeline.

Usage:
    python tools/testing/run_api_tests.py

Prerequisites:
    - FastAPI server running on localhost:8000
    - Celery worker running
    - Redis running
    - Database initialized
"""

import requests
import json
import time
import sys
import os
from typing import Dict, Any

# Add src to path to import test data configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from test.fixtures.real_test_data import RealTestData, get_test_asin

BASE_URL = "http://localhost:8000"

class APITester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def test_endpoint(self, name: str, method: str, url: str, data: Dict[Any, Any] = None, expected_status: int = 200) -> Dict[str, Any]:
        """Test a single API endpoint."""
        print(f"\n🧪 Testing: {name}")
        print(f"   {method} {url}")
        
        try:
            if method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            
            if success:
                print(f"   ✅ PASSED - Status: {response.status_code}")
                self.passed += 1
            else:
                print(f"   ❌ FAILED - Status: {response.status_code}, Expected: {expected_status}")
                self.failed += 1
            
            result = {
                "name": name,
                "method": method,
                "url": url,
                "status_code": response.status_code,
                "success": success,
                "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
            
            if success and isinstance(result["response"], dict):
                # Print key response data
                if "job_id" in result["response"]:
                    print(f"   📋 Job ID: {result['response']['job_id']}")
                if "status" in result["response"]:
                    print(f"   📊 Status: {result['response']['status']}")
            
            self.results.append(result)
            return result
            
        except requests.exceptions.ConnectionError:
            print(f"   ❌ FAILED - Connection error. Is the API server running?")
            self.failed += 1
            return None
        except Exception as e:
            print(f"   ❌ FAILED - Error: {e}")
            self.failed += 1
            return None

    def run_tests(self):
        """Run all M2 API tests."""
        print("="*80)
        print("🧪 M2 API TESTING SUITE")
        print("="*80)
        
        # Prerequisites
        print("\n📋 Prerequisites Check:")
        health_result = self.test_endpoint("Health Check", "GET", f"{BASE_URL}/health")
        
        if not health_result or not health_result["success"]:
            print("\n❌ Health check failed. Ensure API server is running.")
            return False
        
        # Test Group 1: ETL Job Management
        print("\n" + "="*60)
        print("📦 Test Group 1: ETL Job Management")
        print("="*60)
        
        # Trigger jobs
        job1 = self.test_endpoint(
            "Trigger Daily ETL Pipeline",
            "POST",
            f"{BASE_URL}/v1/etl/jobs/trigger",
            {"job_name": "daily_etl_pipeline", "target_date": "2023-12-01", "metadata": {"test": True}}
        )
        
        job2 = self.test_endpoint(
            "Trigger Refresh Summaries",
            "POST", 
            f"{BASE_URL}/v1/etl/jobs/trigger",
            {"job_name": "refresh_summaries", "target_date": "2023-12-01"}
        )
        
        job3 = self.test_endpoint(
            "Trigger Process Alerts",
            "POST",
            f"{BASE_URL}/v1/etl/jobs/trigger", 
            {"job_name": "process_alerts", "target_date": "2023-12-01"}
        )
        
        # Wait for processing
        print("\n⏳ Waiting 20 seconds for Celery processing...")
        time.sleep(20)
        
        # Test Group 2: Raw Event Ingestion
        print("\n" + "="*60)
        print("📥 Test Group 2: Raw Event Ingestion")
        print("="*60)
        
        self.test_endpoint(
            "Ingest Single Event",
            "POST",
            f"{BASE_URL}/v1/etl/events/ingest",
            {
                "asin": RealTestData.PRIMARY_TEST_ASIN,
                "source": "api_test",
                "event_type": "product_update",
                "raw_data": {
                    "asin": RealTestData.PRIMARY_TEST_ASIN,
                    "title": "Soundcore by Anker, Space One, Active Noise Cancelling Headphones API Test",
                    "brand": "Amazon",
                    "price": 49.99,
                    "bsr": 1000,
                    "rating": 4.5,
                    "reviews_count": 500
                },
                "job_id": "api-test-123"
            }
        )
        
        self.test_endpoint(
            "Process Events for Job",
            "POST",
            f"{BASE_URL}/v1/etl/events/process/api-test-123"
        )
        
        # Test Group 3: Mart Layer Operations
        print("\n" + "="*60)
        print("🏪 Test Group 3: Mart Layer Operations")
        print("="*60)
        
        self.test_endpoint(
            "Manual Mart Refresh",
            "POST",
            f"{BASE_URL}/v1/etl/mart/refresh?target_date=2023-12-01"
        )
        
        # Test Group 4: Alerts Management
        print("\n" + "="*60)
        print("🚨 Test Group 4: Alerts Management")
        print("="*60)
        
        self.test_endpoint(
            "Get Active Alerts",
            "GET",
            f"{BASE_URL}/v1/etl/alerts?limit=10"
        )
        
        self.test_endpoint(
            "Get Alerts for ASIN",
            "GET",
            f"{BASE_URL}/v1/etl/alerts?asin={RealTestData.PRIMARY_TEST_ASIN}&limit=5"
        )
        
        self.test_endpoint(
            "Get Alert Summary",
            "GET",
            f"{BASE_URL}/v1/etl/alerts/summary?days=7"
        )
        
        # Test Group 5: ETL Statistics
        print("\n" + "="*60)
        print("📊 Test Group 5: ETL Statistics")
        print("="*60)
        
        self.test_endpoint(
            "Get ETL Pipeline Stats",
            "GET",
            f"{BASE_URL}/v1/etl/stats"
        )
        
        return True

    def print_summary(self):
        """Print test results summary."""
        print("\n" + "="*80)
        print("📋 TEST RESULTS SUMMARY")
        print("="*80)
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📊 Total: {total}")
        print(f"🎯 Pass Rate: {pass_rate:.1f}%")
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! M2 implementation fully functional!")
        else:
            print(f"\n⚠️  {self.failed} tests failed. Check the output above for details.")
        
        return self.failed == 0

if __name__ == "__main__":
    tester = APITester()
    
    success = tester.run_tests()
    all_passed = tester.print_summary()
    
    if not success:
        print("\n💥 Test suite execution failed")
        sys.exit(1)
    elif not all_passed:
        print("\n💥 Some tests failed")
        sys.exit(1)
    else:
        print("\n🚀 M2 API testing completed successfully!")
        sys.exit(0)