#!/bin/bash

# Master test runner for prospecting service
# This script runs all functional tests in sequence

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${SCRIPT_DIR}/../.venv"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════╗"
echo "║     Prospecting Service - Functional Test Suite        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}✗ Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}  Please run quickstart.sh first${NC}"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Track results
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

run_test() {
    local test_name=$1
    local test_script=$2
    
    echo -e "\n${BLUE}──────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}Running: $test_name${NC}"
    echo -e "${BLUE}──────────────────────────────────────────────────────${NC}\n"
    
    if python3 "$test_script"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("✓ $test_name")
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("✗ $test_name")
    fi
}

# Run all tests
run_test "Connectivity Tests" "$SCRIPT_DIR/test_connectivity.py"
run_test "Integration Tests" "$SCRIPT_DIR/test_integration.py"
run_test "Message Queue Flow Tests" "$SCRIPT_DIR/test_message_flow.py"
run_test "API Endpoint Tests" "$SCRIPT_DIR/test_api.py"

# Print summary
echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

for result in "${TEST_RESULTS[@]}"; do
    echo "$result"
done

echo -e "\n${BLUE}────────────────────────────────────────────────────────${NC}"
echo -e "Total Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Total Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}\n"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}\n"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}\n"
    exit 1
fi
