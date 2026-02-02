# TESTS_1.03 - Feature 5/6 Blackout Detection & Time Sanitizer Tests

**Archived**: 2026-02-02  
**Features Tested**: Refined blackout detection with Option C deferred confirmation, Comm error state machine, Time sanitizer RTC validation

## Test Files

| Test | Description |
|------|-------------|
| `TEST_08_rtc_battery_fail.py` | RTC battery failure detection and recovery |
| `TEST_09_time_correction_on_boot.py` | System time correction from RTC on boot |
| `TEST_10_time_jump_detection.py` | Time jump detection between readings |
| `TEST_12_rotation_timing.py` | CSV rotation timing and archive naming |
| `TEST_13_archive_cleanup.py` | Old archive cleanup (>14 days retention) |
| `TEST_15_blackout_confirmation_logic.py` | Option C deferred confirmation for blackouts |
| `TEST_16_comm_state_machine.py` | Comm error START/END state machine |
| `TEST_17_blackout_vs_glitch.py` | True blackout vs meter glitch distinction |

## Running Tests

```bash
cd /home/pi/Desktop/offline-setup-12Sep
./archive/TESTS_1.03/run_all_tests.sh
```

Or individually:
```bash
test_venv/bin/python3 archive/TESTS_1.03/TEST_15_blackout_confirmation_logic.py
```

## Related Hardware Tests (in project root)

These tests require physical hardware and remain in the project root:

- `TEST_05_HARDWARE_dual_rate.py` - Dual-rate polling with real meter
- `TEST_11_physical_time_change.sh` - Physical RTC/system time changes
- `TEST_14_physical_rotation.sh` - Physical CSV rotation test
- `TEST_18_physical_blackout.sh` - Physical blackout detection test
