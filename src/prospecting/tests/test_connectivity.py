#!/usr/bin/env python3
"""
Test connectivity to external services (MongoDB, RabbitMQ).
"""

import os
import sys
from typing import Tuple

def test_mongodb() -> Tuple[bool, str]:
    """Test MongoDB connection."""
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
        
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "email_outreach")
        
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        
        db = client[db_name]
        collections = db.list_collection_names()
        
        client.close()
        return True, f"MongoDB connected. Collections: {collections}"
    except Exception as e:
        return False, f"MongoDB connection failed: {str(e)}"


def test_rabbitmq() -> Tuple[bool, str]:
    """Test RabbitMQ connection."""
    try:
        import pika
        
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        exchange = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")
        
        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()
        
        # Verify exchange exists
        channel.exchange_declare(exchange=exchange, exchange_type='topic', passive=True)
        
        connection.close()
        return True, "RabbitMQ connected successfully"
    except Exception as e:
        return False, f"RabbitMQ connection failed: {str(e)}"


def main():
    """Run connectivity tests."""
    print("\n" + "="*50)
    print("CONNECTIVITY TESTS")
    print("="*50 + "\n")
    
    tests = [
        ("MongoDB", test_mongodb),
        ("RabbitMQ", test_rabbitmq),
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
        print("All connectivity tests passed!")
        return 0
    else:
        print("Some tests failed. Check your configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
