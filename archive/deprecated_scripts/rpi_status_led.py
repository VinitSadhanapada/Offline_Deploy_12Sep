#!/usr/bin/env python3
"""
rpi_status_led.py

Configurable LED status controller supporting PWM-capable pins.

Defaults to single-channel PWM on BCM18 (physical pin 12) which supports hardware PWM.
If you provide 3 pins (comma-separated) it will treat them as R,G,B channels (common-cathode).

Control via writing one of these strings to `/tmp/machine_state`:
  logging        -> steady pulse once every 10 seconds
  not_logging    -> LED off
  usb_detected   -> 5 quick blinks
  copy_completed -> LED solid for 10 seconds

You can set pins via environment variable `LED_PINS`, e.g. `LED_PINS=18` or `LED_PINS=18,13,19`.

Wiring (common-cathode RGB or single yellow LED):
  - GPIO pin(s) -> resistor (330 ohm) -> LED anode(s)
  - LED cathode -> GND

Run as root or with gpio access. Recommended to install a systemd unit to run at boot.
"""
import os
import time
import signal
import threading
import sys

# Set to True to keep this file present but inert (archived).
# Change to False to enable running the LED controller as before.
ARCHIVED = True

try:
    import RPi.GPIO as GPIO
except Exception:
    print("RPi.GPIO not available. Install on Raspberry Pi with: sudo apt install python3-rpi.gpio")
    raise

LED_PINS_ENV = os.environ.get('LED_PINS', '')
if LED_PINS_ENV:
    pins = [int(p.strip()) for p in LED_PINS_ENV.split(',') if p.strip()]
else:
    # default single PWM-capable pin BCM18 (physical pin 12)
    pins = [18]

# Optional environment overrides
# LED_ON_DUTY: percentage 0-100 used for the "ON" level (default 100)
# LED_INVERT: if set to '1' the PWM duty is inverted (useful for PNP high-side)
LED_ON_DUTY = int(os.environ.get('LED_ON_DUTY', '100'))
LED_INVERT = os.environ.get('LED_INVERT', '0') in ('1', 'true', 'True')

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

PWMS = []
for p in pins:
    # Choose initial pin level such that transistor is OFF while we start up.
    # For non-inverted logic (direct LED or low-side NPN) OFF is GPIO.LOW.
    # For inverted logic (PNP high-side) OFF is GPIO.HIGH.
    initial_level = GPIO.HIGH if LED_INVERT else GPIO.LOW
    GPIO.setup(p, GPIO.OUT, initial=initial_level)
    pwm = GPIO.PWM(p, 1000)  # 1kHz default
    # Start PWM with the OFF duty so we don't accidentally drive the LED during init
    off_duty = 100 if LED_INVERT else 0
    pwm.start(off_duty)
    PWMS.append(pwm)

STATE_FILE = '/tmp/machine_state'
shutdown = False
lock = threading.Lock()

def read_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    except Exception:
        return 'not_logging'

def write_state(s):
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(s + '\n')
    except Exception:
        pass

def set_pwm_duty(d):
    # Support inverted semantics when using a PNP high-side (LED_ON logic reversed)
    v = max(0, min(100, int(d)))
    if LED_INVERT:
        v = 100 - v
    for pwm in PWMS:
        try:
            pwm.ChangeDutyCycle(v)
        except Exception:
            pass

def blink_quick(times=5, on=0.08, off=0.08):
    for _ in range(times):
        if shutdown: break
        set_pwm_duty(LED_ON_DUTY)
        time.sleep(on)
        set_pwm_duty(0)
        time.sleep(off)

def solid_for(duration=10):
    set_pwm_duty(LED_ON_DUTY)
    t0 = time.time()
    while time.time() - t0 < duration:
        if shutdown: break
        time.sleep(0.1)
    set_pwm_duty(0)

def logging_pulse_cycle():
    # short pulse then wait ~5s total (LED_ON_DUTY used for ON level)
    set_pwm_duty(LED_ON_DUTY)
    time.sleep(0.25)
    set_pwm_duty(0)
    # sleep for remainder to make the full cycle ~5s total
    t0 = time.time()
    while time.time() - t0 < 4.75:
        if shutdown: break
        time.sleep(0.2)

def main_loop():
    # ensure state file exists
    if not os.path.exists(STATE_FILE):
        write_state('not_logging')

    while not shutdown:
        state = read_state()
        if state == 'usb_detected':
            blink_quick(5, 0.08, 0.08)
            # after transient, revert to not_logging or logging depending on file
            write_state('logging')
            continue
        if state == 'copy_completed':
            solid_for(10)
            write_state('logging')
            continue
        if state == 'logging':
            logging_pulse_cycle()
            continue
        # default: not_logging
        set_pwm_duty(0)
        time.sleep(0.5)

def handle_sig(signum, frame):
    global shutdown
    shutdown = True

def cleanup():
    # stop PWM safely and cleanup GPIO, guarding against interpreter shutdown
    try:
        try:
            set_pwm_duty(0)
        except Exception:
            pass
        for pwm in PWMS:
            try:
                if pwm is not None:
                    pwm.stop()
            except Exception:
                pass
    finally:
        try:
            if 'GPIO' in globals() and hasattr(GPIO, 'cleanup'):
                GPIO.cleanup()
        except Exception:
            pass

if __name__ == '__main__':
    # If archived, exit immediately so the file can remain in the project
    # for reference (wiring diagrams, notes) without interacting with the system.
    if ARCHIVED:
        try:
            print('rpi_status_led.py is archived and will not run. Set ARCHIVED=False to enable.')
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)
    try:
        main_loop()
    finally:
        cleanup()
        # exit without running additional Python-level destructors which
        # sometimes trigger RPi.GPIO PWM.__del__ errors during interpreter teardown
        try:
            os._exit(0)
        except Exception:
            pass


# ------------------------- Wiring Diagram (Archive) -------------------------
# This section documents wiring options and notes for the LED controller.
# It is intentionally placed in the file so it is easy to find later.
# The script is archived by default (see ARCHIVED variable above).
#
# 1) PNP high-side (original): E -> 3.3V, B -> GPIO via Rb, C -> LED anode,
#    LED cathode -> R_led -> GND
#    - Use LED_INVERT=1 in script for PNP semantics.
#    - Typical parts: 2N3906 (PNP), Rb ~ 2.2k (or built from 220Ω in series),
#      R_led ~ 100..220Ω depending on desired current.
#
#   ASCII (flat face to you, left->right = E B C typical):
#       3.3V
#         |
#        E  (left)
#           C ----> LED anode
#                  LED cathode -> [R_led] -> GND
#   GPIO --[Rb]--> B (middle)
#
# 2) Recommended: NPN low-side on 5V (brighter, more headroom):
#    5V -> [R_led] -> LED anode
#           LED cathode -> NPN Collector
#           NPN Emitter -> GND
#    GPIO -> [Rb] -> NPN Base
#    - Use LED_INVERT=0 for low-side NPN wiring in the script.
#    - Use Rb ~ 660Ω..2.2kΩ (3x220Ω = 660Ω or 5x220Ω = 1.1kΩ can be used to
#      build a safe base resistor from on-hand 220Ω parts).
#    - R_led choices: 220Ω -> ~12mA (safe), 150Ω -> ~20mA (brighter).
#
#   ASCII (2N3904 common arrangement, flat face left->right = C B E):
#       5V --[R_led]--> LED anode
#                          LED cathode --> 2N3904 Collector (left pin)
#                                           2N3904 Emitter (right pin) --> GND
#   GPIO --[Rb]--> 2N3904 Base (middle pin)
#
# 3) Paralleling resistors:
#    - n identical resistors in parallel: R_eq = R/n.
#    - Example: 2x220Ω -> 110Ω, 3x220Ω -> 73Ω, 4x220Ω -> 55Ω.
#    - Power per resistor = (V_R^2 / R_eq) / n; small-signal resistors typically
#      handle LED currents easily when split across multiple parts.
#
# 4) Base drive guidelines (to reach saturation):
#    - Aim for Ib ≈ Ic/10 for saturation (conservative). For Ic≈12mA, Ib≈1.2mA.
#    - Rb ≈ (V_gpio - Vbe) / Ib. Example: Vgpio=3.3V, Vbe≈0.7V -> Rb≈2.6V/Ib.
#    - Build Rb from series/parallel 220Ω parts if needed.
#
# 5) Safety notes:
#    - Do NOT tie emitter to 5V while driving base from 3.3V (PNP) — transistor
#      will not switch off and you risk damage.
#    - Never remove the series resistor entirely unless a proper current
#      regulated driver is used. LEDs require current limiting.
#    - For high currents (>100mA) use a proper constant-current driver and
#      a logic-level MOSFET rated for the current (IRF540N is not ideal for 3.3V gate).
#
# 6) Quick test checklist (after wiring):
#    - Verify transistor pinout with multimeter diode test out-of-circuit.
#    - Confirm E to supply (3.3V or GND), C to LED anode/cathode as appropriate.
#    - Use conservative Rb first (e.g., 1.1kΩ) then reduce to increase brightness
#      while monitoring temperatures and currents.
#-----------------------------------------------------------------------------
