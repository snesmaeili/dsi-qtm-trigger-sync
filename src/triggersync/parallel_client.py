"""
Parallel-port trigger interface using PsychoPy.
"""

from psychopy import parallel
import asyncio

class ParallelClient:
    def __init__(self, address: int = 0x4000, pulse_ms: float = 5.0):
        """
        :param address: I/O base address (hex2dec('4000') → 0x4000)
        :param pulse_ms: pulse duration in milliseconds
        """
        self.address = address
        self.duration = pulse_ms / 1000.0
        parallel.setPortAddress(self.address)

    async def send(self, code: int):
        """Send an 8-bit trigger pulse."""
        parallel.setData(code)
        await asyncio.sleep(self.duration)
        parallel.setData(0)