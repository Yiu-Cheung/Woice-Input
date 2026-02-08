"""
Test if microphone is detected and working
"""
import sounddevice as sd
import numpy as np

print("=" * 60)
print("Testing Microphone Detection")
print("=" * 60)

# List all audio devices
print("\n1. Available audio devices:")
print(sd.query_devices())

# Get default input device
print("\n2. Default input device:")
try:
    default_input = sd.query_devices(kind='input')
    print(f"   Name: {default_input['name']}")
    print(f"   Channels: {default_input['max_input_channels']}")
    print(f"   Default sample rate: {default_input['default_samplerate']}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test recording for 2 seconds
print("\n3. Testing 2-second recording...")
try:
    duration = 2  # seconds
    sample_rate = 16000

    print(f"   Recording for {duration} seconds...")
    audio = sd.rec(int(duration * sample_rate),
                   samplerate=sample_rate,
                   channels=1,
                   dtype=np.float32)
    sd.wait()

    # Check if audio was captured
    max_amplitude = np.max(np.abs(audio))
    print(f"   Max amplitude: {max_amplitude:.4f}")

    if max_amplitude < 0.001:
        print("   WARNING: Audio is too quiet. Please check:")
        print("   - Is your microphone plugged in?")
        print("   - Is the correct microphone selected as default?")
        print("   - Is the microphone enabled in Windows Sound settings?")
    else:
        print("   [OK] Microphone is working!")

except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

input("\nPress Enter to exit...")
