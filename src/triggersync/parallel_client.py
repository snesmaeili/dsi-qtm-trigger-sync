"""
Parallel-port trigger interface using pyparallel.
"""

import asyncio
import sys

# Try to import the parallel port module and fall back to dummy if unavailable
try:
    import parallel
except Exception as e:
    print(f"Warning: parallel port interface unavailable ({e}); using dummy stub.")
    class _DummyPort:
        def __init__(self, port=None):
            pass
        def setData(self, data):
            pass
    # Create a dummy `parallel` module with a Parallel class
    parallel = type("parallel", (), {"Parallel": _DummyPort})

class ParallelClient:
    def __init__(self, address: int = 0x4000, pulse_ms: float = 5.0):
        """
        :param address: I/O base address (hex2dec('4000') → 0x4000)
        :param pulse_ms: pulse duration in milliseconds
        """
        self.address = address
        self.duration = pulse_ms / 1000.0
        # Initialize the parallel port interface
        try:
            self.port = parallel.Parallel(port=self.address)
        except Exception as e:
            print(f"Error initializing parallel port at address {hex(self.address)}: {e}")
            print("Make sure you have the necessary permissions to access the parallel port.")
            if sys.platform == 'win32':
                print("On Windows, you may need to install inpoutx64.dll or run as administrator.")
            elif sys.platform == 'linux':
                print("On Linux, you may need to add your user to the 'lp' group or run as root.")
            # fallback to dummy port stub
            self.port = parallel.Parallel(port=None)

    async def send(self, code: int):
        """Send an 8-bit trigger pulse."""
        try:
            self.port.setData(code)
            await asyncio.sleep(self.duration)
            self.port.setData(0)
        except Exception as e:
            print(f"Error sending trigger code {code}: {e}")