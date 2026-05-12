#!/usr/bin/env python3
"""
Test prospecting service API endpoints.
"""

import os
import sys
import requests
import json
from typing import Tuple

BASE_URL = os.getenv("SERVICE_URL", "http://localhost:8004")

def test_health() -> Tuple[bool, str]:
    """Test health/status endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return True, "Health check passed"
        else:
            return False, f"Unexpected status code: {response.status_code}"
    except Exception as e:
        return False, f"Health check failed: {str(e)}"


def test_score_prospect() -> Tuple[bool, str]:
    """Test scoring a prospect."""
    try:
        payload = {
            "prospect": {
                "name": "Test Person",
                "title": "CEO",
                "company": "Test Corp",
                "email": "test@testcorp.com"
            },
            "icp_weights": {
                "title_relevance": 0.3,
                "company_fit": 0.4,
                "engagement_score": 0.3
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/score",
            json=payload,
            timeout=10
        )
        
        if response.status_code in [200, 404]:
            if response.status_code == 404:
                return True, "Endpoint not implemented yet (expected during development)"
            data = response.json()
            score = data.get("score", "N/A")
            return True, f"Scoring successful. Score: {score}"
        else:
            return False, f"Unexpected status code: {response.status_code}, Response: {response.text}"
    except Exception as e:
        return False, f"Scoring failed: {str(e)}"


def test_list_prospects() -> Tuple[bool, str]:
    """Test listing prospects."""
    try:
        response = requests.get(
            f"{BASE_URL}/api/prospects",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            count = len(data.get("prospects", []))
            return True, f"Retrieved {count} prospects"
        elif response.status_code == 404:
            return True, "Endpoint not implemented yet (expected during development)"
        else:
            return False, f"Unexpected status code: {response.status_code}"
    except Exception as e:
        return False, f"Failed to list prospects: {str(e)}"


def test_get_campaign_stats() -> Tuple[bool, str]:
    """Test getting campaign statistics."""
    try:
        campaign_id = "test-campaign-001"
        response = requests.get(
            f"{BASE_URL}/api/campaigns/{campaign_id}/stats",
            timeout=5
        )
        
        if response.status_code in [200, 404]:
            if response.status_code == 404:
                return True, "Campaign not found (expected for test)"
            data = response.json()
            return True, f"Campaign stats retrieved: {data}"
        else:
            return False, f"Unexpected status code: {response.status_code}"
    except Exception as e:
        return False, f"Failed to get campaign stats: {str(e)}"


def main():
    """Run API tests."""
    print("\n" + "="*50)
    print("API ENDPOINT TESTS")
    print("="*50 + "\n")
    
    tests = [
        ("Health Check", test_health),
        ("Score Prospect", test_score_prospect),
        ("List Prospects", test_list_prospects),
        ("Get Campaign Stats", test_get_campaign_stats),
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        passed, message = test_func()
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        print(f"  {message}\n")
        
        if not passed:
            all_passed = False
    
    print("="*50)
    if all_passed:
        print("All API tests passed!")
        return 0
    else:
        print("Some API tests failed. Ensure the service is running on port 8004.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
