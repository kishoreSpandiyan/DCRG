#!/usr/bin/env python3
"""
DCRG Hardware Joystick Diagnostic Utility.
Direct interactive test tool for verifying physical USB and Bluetooth controllers.

Usage:
    python hardware/joystick/joystick_diagnostic.py
"""

import sys
import time
import os

try:
    import pygame
except ImportError:
    print("\n[ERROR] Pygame / pygame-ce is not installed in the current environment.")
    print("Please activate your virtual environment: .\\backend\\.venv\\Scripts\\activate.bat\n")
    sys.exit(1)


def main():
    print("=" * 70)
    print(" DCRG PHYSICAL JOYSTICK DIAGNOSTIC UTILITY (PHASE 2)")
    print(" Dynamic Command Reliability Graph Hardware HAL Verification")
    print("=" * 70)

    try:
        pygame.init()
        pygame.joystick.init()
    except Exception as e:
        print(f"[FATAL] Failed to initialize Pygame joystick subsystem: {e}")
        sys.exit(1)

    count = pygame.joystick.get_count()

    if count == 0:
        print("\n[STATUS: HARDWARE NOT DETECTED]")
        print("  • No physical USB or Bluetooth game controllers detected by the OS.")
        print("  • Physical hardware verification remains: PENDING HARDWARE CONNECTION.")
        print("\nTo test with real hardware:")
        print("  1. Plug in a USB flight stick, Xbox controller, or pair a Bluetooth gamepad.")
        print("  2. Re-run this script: python hardware/joystick/joystick_diagnostic.py")
        print("\nExiting cleanly (Return Code 0).")
        pygame.joystick.quit()
        pygame.quit()
        sys.exit(0)

    print(f"\n[OK] Found {count} connected controller(s):\n")
    joysticks = []
    for i in range(count):
        try:
            joy = pygame.joystick.Joystick(i)
            joysticks.append(joy)
            print(f"  [{i}] Device Name : {joy.get_name()}")
            print(f"      GUID        : {joy.get_guid()}")
            print(f"      Axes Count  : {joy.get_numaxes()}")
            print(f"      Buttons     : {joy.get_numbuttons()}")
            print(f"      Hats (POV)  : {joy.get_numhats()}")
            print("-" * 50)
        except Exception as e:
            print(f"  [{i}] Failed to initialize joystick: {e}")

    active_joy = joysticks[0]
    print(f"\nMonitoring live inputs from: {active_joy.get_name()} (Press Ctrl+C to exit)\n")

    try:
        while True:
            pygame.event.pump()
            
            axes = [round(active_joy.get_axis(a), 3) for a in range(active_joy.get_numaxes())]
            buttons = [active_joy.get_button(b) for b in range(active_joy.get_numbuttons())]
            hats = [active_joy.get_hat(h) for h in range(active_joy.get_numhats())]

            pressed_btns = [idx for idx, val in enumerate(buttons) if val == 1]

            sys.stdout.write(
                f"\rAxes: {axes[:4]} | Pressed Buttons: {pressed_btns} | Hats: {hats}   "
            )
            sys.stdout.flush()
            time.sleep(0.05)  # 20Hz refresh

    except KeyboardInterrupt:
        print("\n\n[INFO] Diagnostic session terminated by operator.")
    finally:
        pygame.joystick.quit()
        pygame.quit()
        print("[INFO] Joystick hardware released cleanly. Exiting.")


if __name__ == "__main__":
    main()

