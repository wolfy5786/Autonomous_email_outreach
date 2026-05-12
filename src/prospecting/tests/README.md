# Prospecting Service - Functional Tests

Comprehensive test suite for the Prospecting Service. These tests verify connectivity, API endpoints, message queue operations, and end-to-end workflows.

## Quick Start

Run all tests at once:

```bash
cd src/prospecting
docker compose run --rm tests
```

Or run individual tests in the same container image:

```bash
docker compose run --rm tests python tests/test_connectivity.py
docker compose run --rm tests python tests/test_integration.py
docker compose run --rm tests python tests/test_message_flow.py
docker compose run --rm tests python tests/test_api.py
```

## Prerequisites

- The prospecting stack must be running with Docker Compose
- MongoDB must be accessible
- RabbitMQ must be accessible
- No virtual environment setup is needed on the host

## Test Descriptions

### `test_connectivity.py`
**Purpose**: Verify that the service can connect to external dependencies.

**Tests**:
- MongoDB connection and collection enumeration
- RabbitMQ connection and exchange verification

**Expected Output**: Connection status for each service.

---

### `test_integration.py`
**Purpose**: End-to-end workflow testing with MongoDB data.

**Tests**:
- Set up test campaigns, plans, companies, and persons in MongoDB
- Verify data integrity across collections
- Check that scoring fields are properly applied to prospects

**Expected Output**: Document counts and scoring metadata confirmation.

---

### `test_message_flow.py`
**Purpose**: Test asynchronous message queue operations.

**Tests**:
- Publish a simulated `sourcing.completed` event (from Sourcing Service)
- Check queue depth for pending messages
- Monitor `prospecting.completed` queue for the service's output

**Expected Output**: Message publication confirmation and processing status.

**Note**: This test simulates the upstream Sourcing Service. If the message processing timeout expires, it's likely the service is still processing — this is normal.

---

### `test_api.py`
**Purpose**: Test HTTP API endpoints exposed by the service.

**Tests**:
- Health check endpoint
- Score prospect endpoint
- List prospects endpoint
- Get campaign statistics endpoint

**Expected Output**: HTTP status codes and response data.

---

### `run_tests.py`
**Purpose**: Master test runner that executes all tests in sequence.

**Output**:
- Formatted results for each test
- Summary table with pass/fail counts
- Exit code: 0 if all pass, 1 if any fail

---

## Environment Variables

All tests respect these environment variables (same as the service):

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB="email_outreach"
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/%2F"
export RABBITMQ_EXCHANGE="email_outreach.events"
export SERVICE_URL="http://localhost:8004"
```

## Common Issues

### Test fails: "MongoDB is not accessible"
- Ensure MongoDB is running
- Check `MONGODB_URI` matches your setup
- Test locally: `mongosh "$MONGODB_URI"`

### Test fails: "RabbitMQ is not accessible"
- Ensure RabbitMQ container is running: `docker ps | grep rabbitmq`
- Check `RABBITMQ_URL` format
- Restart RabbitMQ: `cd src/local_infrastructure/rabbit_mq && docker compose down && docker compose up -d`

### Test fails: "Service URL is not accessible"
- Ensure the prospecting service is running: `./quickstart.sh`
- Check that port 8004 is not in use by another process
- Verify `SERVICE_URL` is correct

### Message flow test times out
- This is normal if the service is still processing the message
- The test waits up to 10 seconds and will report "no messages received" if the consumer hasn't published yet
- Check service logs to see processing status

## Next Steps

After tests pass:

1. **Review service logs** — Check the terminal where `quickstart.sh` is running for processing details
2. **Monitor queue depth** — Use RabbitMQ Management UI at `http://localhost:15672` (guest/guest)
3. **Inspect MongoDB** — Use MongoDB clients to view scored prospects: `db.persons.find({"icp_poc_score": {$exists: true}})`
4. **Test other services** — Once prospecting is working, test Sourcing, Planning, Messaging, and Orchestrator services

## Adding Custom Tests

To add a new test:

1. Create a new Python file in this directory: `test_custom.py`
2. Follow the pattern of existing tests (import at top, test functions with Tuple[bool, str] return)
3. Add the test to `run_tests.py`:

```bash
run_test "Custom Test Name" "$SCRIPT_DIR/test_custom.py"
```

---

**Last Updated**: May 9, 2026
