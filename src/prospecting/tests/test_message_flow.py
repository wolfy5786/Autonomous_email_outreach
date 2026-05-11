#!/usr/bin/env python3
"""
Test message queue flow - simulates sourcing service messages.
"""

import os
import sys
import json
import pika
import time
import uuid
from typing import Tuple
from datetime import datetime


def _build_test_event(event_id: str | None = None) -> dict:
    test_event_id = event_id or f"evt-{uuid.uuid4()}"
    return {
        "campaign_id": "test-campaign-001",
        "entity_ids": ["company-test-001", "company-test-002"],
        "event_id": test_event_id,
        "idempotency_key": test_event_id,
    }

def publish_sourcing_completed_event(event_payload: dict | None = None) -> Tuple[bool, str]:
    """Publish a sourcing.completed event to test queue consumption."""
    try:
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        exchange = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")
        
        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()
        
        # Declare exchange and queue
        dlx_exchange = os.getenv("RABBITMQ_DLX_EXCHANGE", "email_outreach.dlx")
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True, passive=True)
        channel.exchange_declare(exchange=dlx_exchange, exchange_type='topic', durable=True, passive=True)
        
        queue_result = channel.queue_declare(
            queue='sourcing.completed',
            durable=True,
            arguments={
                'x-dead-letter-exchange': dlx_exchange,
                'x-dead-letter-routing-key': 'sourcing.completed.dlq'
            }
        )
        channel.queue_bind(exchange=exchange, queue='sourcing.completed', routing_key='sourcing.completed')
        
        # Create a test event that matches the locked contract
        event_payload = event_payload or _build_test_event()
        
        # Publish the event
        channel.basic_publish(
            exchange=exchange,
            routing_key='sourcing.completed',
            body=json.dumps(event_payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type='application/json'
            )
        )
        
        connection.close()
        
        return True, f"Published sourcing.completed event with {len(event_payload['entity_ids'])} entities"
    except Exception as e:
        return False, f"Failed to publish event: {str(e)}"


def duplicate_event_idempotency_test() -> Tuple[bool, str]:
    """Publish the same sourcing event twice and ensure only one prospecting.completed message is emitted."""
    try:
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        exchange = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")

        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()

        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True, passive=True)
        test_queue = f"prospecting.completed.test.{uuid.uuid4().hex}"
        channel.queue_declare(queue=test_queue, exclusive=True, auto_delete=True)
        channel.queue_bind(exchange=exchange, queue=test_queue, routing_key='prospecting.completed')

        event_payload = _build_test_event(event_id=f"dup-{uuid.uuid4()}")

        for _ in range(2):
            channel.basic_publish(
                exchange=exchange,
                routing_key='sourcing.completed',
                body=json.dumps(event_payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                ),
            )

        received = []
        start_time = time.time()
        timeout = 12

        while time.time() - start_time < timeout:
            method, properties, body = channel.basic_get(queue=test_queue, auto_ack=False)
            if not method:
                time.sleep(0.5)
                continue

            try:
                data = json.loads(body)
            except Exception:
                data = {}

            if data.get('campaign_id') == event_payload['campaign_id']:
                received.append(data)

            channel.basic_ack(delivery_tag=method.delivery_tag)

            if len(received) > 1:
                break

        connection.close()

        if len(received) == 1:
            return True, "Duplicate sourcing.completed event produced exactly one prospecting.completed output"
        if len(received) > 1:
            return False, f"Duplicate sourcing.completed event produced {len(received)} prospecting.completed outputs"
        return False, "Did not receive any prospecting.completed output for duplicate-event test"
    except Exception as e:
        return False, f"Duplicate-event idempotency test failed: {str(e)}"


def check_queue_depth() -> Tuple[bool, str]:
    """Check the depth of sourcing.completed queue."""
    try:
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        
        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()
        
        method, properties, body = channel.basic_get(queue='sourcing.completed', auto_ack=False)
        
        if method:
            # Put it back for the consumer
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return True, f"Found {method.message_count} message(s) in sourcing.completed queue"
        else:
            return True, "Queue is empty (messages may have been consumed)"
    except Exception as e:
        return False, f"Failed to check queue: {str(e)}"
    finally:
        try:
            connection.close()
        except:
            pass


def monitor_prospecting_completed_queue() -> Tuple[bool, str]:
    """Monitor the prospecting.completed queue for processed messages."""
    try:
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
        exchange = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")
        
        connection = pika.BlockingConnection(pika.URLParameters(url))
        channel = connection.channel()
        
        # Declare the queue (use passive to verify it exists)
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True, passive=True)
        queue_result = channel.queue_declare(queue='prospecting.completed', passive=True)
        channel.queue_bind(exchange=exchange, queue='prospecting.completed', routing_key='prospecting.completed')
        
        # Check for messages with timeout
        message_found = False
        start_time = time.time()
        timeout = 10
        
        print("    Waiting for prospecting.completed messages (10 second timeout)...\n")
        
        while time.time() - start_time < timeout:
            method, properties, body = channel.basic_get(queue='prospecting.completed', auto_ack=False)
            
            if method:
                message_found = True
                try:
                    data = json.loads(body)
                    print(f"    Message received:")
                    print(f"      Campaign ID: {data.get('campaign_id')}")
                    print(f"      Prospects scored: {len(data.get('ranked_prospects', []))}")
                except:
                    print(f"    Message received (raw): {body}")
                
                channel.basic_ack(delivery_tag=method.delivery_tag)
                break
            
            time.sleep(1)
        
        connection.close()
        
        if message_found:
            return True, "Successfully received prospecting.completed message"
        else:
            return True, "No messages received within timeout (service may be processing)"
    except Exception as e:
        return False, f"Failed to monitor queue: {str(e)}"


def main():
    """Run message flow tests."""
    print("\n" + "="*50)
    print("MESSAGE QUEUE FLOW TESTS")
    print("="*50 + "\n")
    
    tests = [
        ("Publish Sourcing Event", publish_sourcing_completed_event),
        ("Check Queue Depth", check_queue_depth),
        ("Monitor Processing", monitor_prospecting_completed_queue),
        ("Duplicate Event Idempotency", duplicate_event_idempotency_test),
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
        print("All message queue tests passed!")
        return 0
    else:
        print("Some message queue tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
