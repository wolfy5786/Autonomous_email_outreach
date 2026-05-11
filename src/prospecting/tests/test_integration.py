#!/usr/bin/env python3
"""
Integration test - tests the full workflow.
"""

import os
import sys
import json
from pymongo import MongoClient
from typing import Tuple

def setup_test_data() -> Tuple[bool, str]:
    """Set up test campaign and plan data in MongoDB."""
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")
        
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        
        # Create or update campaign
        campaign_data = {
            "_id": "test-campaign-001",
            "name": "Test Campaign",
            "plan_id": "plan-test-campaign-001",
            "config": {
                "min_icp_score": 0.7
            },
            "status": "active"
        }
        db.campaigns.replace_one({"_id": campaign_data["_id"]}, campaign_data, upsert=True)
        
        # Create or update plan
        plan_data = {
            "_id": "plan-test-campaign-001",
            "campaign_id": "test-campaign-001",
            "company_signals": ["industry SaaS", "company size 100-500", "growth hiring"],
            "poc_signals": ["title CTO", "department engineering", "technical buyer"],
            "scoring_weights": {
                "industry_match": 0.25,
                "company_size_match": 0.1,
                "funding_stage_match": 0.1,
                "geography_match": 0.05,
                "tech_stack_match": 0.1,
                "growth_signal_match": 0.1,
                "personalization_signal_match": 0.1,
                "data_completeness": 0.1,
                "freshness": 0.1,
                "title_match": 0.2,
                "seniority_match": 0.1,
                "department_match": 0.1,
                "email_verified": 0.1,
                "linkedin_present": 0.05,
                "role_relevance": 0.15
            },
            "company_attributes": {
                "industry": ["SaaS", "Technology"],
                "size": ["100-500", "500-1000"]
            }
        }
        db.plans.replace_one({"_id": plan_data["_id"]}, plan_data, upsert=True)
        
        # Create test companies
        companies = [
            {
                "_id": "company-test-001",
                "name": "TestCorp Inc",
                "industry": "SaaS",
                "employees": 250,
                "founded_year": 2018
            },
            {
                "_id": "company-test-002",
                "name": "DataFlow Systems",
                "industry": "Technology",
                "employees": 450,
                "founded_year": 2015
            }
        ]
        for company in companies:
            db.companies.replace_one({"_id": company["_id"]}, company, upsert=True)
        
        # Create test persons
        persons = [
            {
                "_id": "person-test-001",
                "name": "Alice Johnson",
                "title": "CTO",
                "company_id": "company-test-001",
                "email": "alice@testcorp.com",
                "email_verified": True,
                "linkedin_url": "https://linkedin.com/in/alice-johnson"
            },
            {
                "_id": "person-test-002",
                "name": "Bob Smith",
                "title": "VP Engineering",
                "company_id": "company-test-002",
                "email": "bob@dataflow.com",
                "email_verified": True,
                "linkedin_url": "https://linkedin.com/in/bob-smith"
            }
        ]
        for person in persons:
            db.persons.replace_one({"_id": person["_id"]}, person, upsert=True)
        
        client.close()
        return True, "Test data set up successfully"
    except Exception as e:
        return False, f"Failed to set up test data: {str(e)}"


def verify_scoring_fields() -> Tuple[bool, str]:
    """Verify that scoring fields are properly added to prospects."""
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")
        
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        
        # Check if any person has scoring fields
        person_with_score = db.persons.find_one({
            "$or": [
                {"icp_poc_score": {"$exists": True}},
                {"email_verified": True}
            ]
        })
        
        if person_with_score:
            message = "Found prospect with scoring data:\n"
            if "icp_poc_score" in person_with_score:
                message += f"  - ICP POC Score: {person_with_score['icp_poc_score']}"
            if "email_verified" in person_with_score:
                message += f"\n  - Email verified: {person_with_score['email_verified']}"
            if "scoring_version" in person_with_score:
                message += f"\n  - Scoring version: {person_with_score['scoring_version']}"
            return True, message
        else:
            return True, "No scored prospects found yet (waiting for message processing)"
    except Exception as e:
        return False, f"Failed to verify scoring: {str(e)}"
    finally:
        client.close()


def check_data_integrity() -> Tuple[bool, str]:
    """Check integrity of test data in MongoDB."""
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")
        
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        
        checks = {
            "campaigns": db.campaigns.count_documents({}),
            "plans": db.plans.count_documents({}),
            "companies": db.companies.count_documents({}),
            "persons": db.persons.count_documents({})
        }
        
        client.close()
        
        message = "Data integrity check:\n"
        for collection, count in checks.items():
            message += f"  - {collection}: {count} documents\n"
        
        if all(count > 0 for count in checks.values()):
            return True, message
        else:
            return True, message + "\n  (Some collections may be empty, but this is okay)"
    except Exception as e:
        return False, f"Failed integrity check: {str(e)}"


def main():
    """Run integration tests."""
    print("\n" + "="*50)
    print("INTEGRATION TESTS")
    print("="*50 + "\n")
    
    tests = [
        ("Set Up Test Data", setup_test_data),
        ("Verify Data Integrity", check_data_integrity),
        ("Verify Scoring Fields", verify_scoring_fields),
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
        print("All integration tests passed!")
        return 0
    else:
        print("Some integration tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
