#!/bin/bash
# Run all TESTS_1.03 unit tests
# Usage: ./run_all_tests.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Running TESTS_1.03 - Blackout Detection & Time Sanitizer ==="
echo ""

PASS=0
FAIL=0

for test in "$SCRIPT_DIR"/TEST_*.py; do
    name=$(basename "$test")
    echo -n "Running $name... "
    if test_venv/bin/python3 "$test" 2>&1 | grep -qE "PASS|✓"; then
        echo "✓ PASSED"
        PASS=$((PASS + 1))
    else
        echo "✗ FAILED"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ $FAIL -eq 0 ]; then
    echo "All tests passed!"
    exit 0
else
    echo "Some tests failed!"
    exit 1
fi
