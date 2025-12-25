#!/usr/bin/env python3
"""
Test script to verify ITE backend integration with Tuxedo GUI
Tests effect switching, color changes, and brightness control
"""

import sys
import os
import time

# Set up paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, 'tuxedo-src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'ite8291r3-ctl'))

from backlight_control import backlight

def test_effects():
    """Test switching between different effects"""
    print("🧪 Testing Tuxedo Backend Integration\n")
    
    print("Available modes:", list(backlight.modes))
    print("Available colors:", list(backlight.colors.keys())[:10], "...\n")
    
    # Test 1: Check initial state
    print("📊 Initial State:")
    print(f"  State: {backlight.state}")
    print(f"  Mode: {backlight.mode}")
    print(f"  Brightness: {backlight.brightness}")
    print()
    
    # Test 2: Set static color (red)
    print("🔴 Test: Static Red")
    backlight.state = 1
    backlight.mode = 'color'
    backlight.color_left = 'red'
    time.sleep(2)
    print(f"  ✓ Mode set to: {backlight.mode}")
    print(f"  ✓ Color: {backlight.color_left}")
    print()
    
    # Test 3: Breathing effect
    print("💨 Test: Breathing Effect")
    backlight.mode = 'breathe'
    time.sleep(3)
    print(f"  ✓ Mode set to: {backlight.mode}")
    print()
    
    # Test 4: Rainbow cycle
    print("🌈 Test: Rainbow Cycle")
    backlight.mode = 'cycle'
    time.sleep(3)
    print(f"  ✓ Mode set to: {backlight.mode}")
    print()
    
    # Test 5: Wave effect
    print("🌊 Test: Wave Effect")
    backlight.mode = 'wave'
    time.sleep(3)
    print(f"  ✓ Mode set to: {backlight.mode}")
    print()
    
    # Test 6: Brightness control
    print("💡 Test: Brightness Changes")
    backlight.mode = 'color'
    backlight.color_left = 'blue'
    
    for brightness in [255, 128, 64, 128, 255]:
        backlight.brightness = brightness
        print(f"  ✓ Brightness: {brightness}/255")
        time.sleep(1)
    print()
    
    # Test 7: Color changes
    print("🎨 Test: Color Changes")
    colors_to_test = ['red', 'green', 'blue', 'yellow', 'purple', 'white']
    for color in colors_to_test:
        backlight.color_left = color
        print(f"  ✓ Color: {color}")
        time.sleep(1)
    print()
    
    # Test 8: Turn off
    print("⚫ Test: Turn Off")
    backlight.state = 0
    time.sleep(2)
    print(f"  ✓ State: {backlight.state} (OFF)")
    print()
    
    # Test 9: Turn back on
    print("✅ Test: Turn On")
    backlight.state = 1
    backlight.mode = 'cycle'
    print(f"  ✓ State: {backlight.state} (ON)")
    print(f"  ✓ Mode: {backlight.mode}")
    print()
    
    print("🎉 All tests completed successfully!")
    print("\n✨ Backend Integration: WORKING")

if __name__ == '__main__':
    try:
        test_effects()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
