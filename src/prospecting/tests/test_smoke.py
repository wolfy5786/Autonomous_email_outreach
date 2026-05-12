#!/usr/bin/env python3
"""
Smoke test - quick sanity check that everything is running.
Useful for CI/CD pipelines or periodic health checks.
"""

import os
import sys
import requests
from pymongo import MongoClient

def quick_smoke_test():
    """Run a quick smoke test."""
    print("\n" + "="*50)
    print("SMOKE TEST - Quick Health Check")
    print("="*50 + "\n")
    
    issues = []
    
    # Check 1: MongoDB
    try:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        print("✓ MongoDB is accessible")
        client.close()
    except Exception as e:
        issues.append(f"✗ MongoDB: {str(e)}")
    
    # Check 2: RabbitMQ
    try:
        import pika
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        connection = pika.BlockingConnection(pika.URLParameters(url))
        connection.close()
        print("✓ RabbitMQ is accessible")
    except Exception as e:
        issues.append(f"✗ RabbitMQ: {str(e)}")
    
    # Check 3: Service API
    try:
        service_url = os.getenv("SERVICE_URL", "http://localhost:8004")
        response = requests.get(f"{service_url}/health", timeout=3)
        if response.status_code == 200:
            print("✓ Prospecting Service is running")
        else:
            issues.append(f"✗ Service returned status code: {response.status_code}")
    except Exception as e:
        issues.append(f"✗ Service: {str(e)}")
    
    print("\n" + "="*50)
    if issues:
        for issue in issues:
            print(issue)
        print("="*50)
        print("\nStatus: FAILED - Some services are unavailable\n")
        return 1
    else:
        print("✓ All systems operational")
        print("="*50)
        print("\nStatus: PASSED\n")
        return 0


if __name__ == "__main__":
    sys.exit(quick_smoke_test())
