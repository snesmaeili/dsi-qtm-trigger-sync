"""
Qualisys QTM real-time recording wrapper.
"""

import qtm_rt
from qtm_rt import QRTEvent, QRTCommandException
import asyncio

class QTMClient:
    def __init__(self, host: str = "127.0.0.1", version: str = "1.22"):
        self.host = host
        self.version = version
        self.conn = None

    async def connect(self, password: str = ""):
        self.conn = await qtm_rt.connect(self.host, version=self.version)
        if not self.conn:
            raise ConnectionError("Cannot connect to QTM")
        await self.conn.take_control(password)

    async def start_recording(self, duration: float):
        """Start capture with XML override."""
        xml = f"""
<QTM_Parameters_Ver_{self.version}>
  <General><Capture_Time>{duration}</Capture_Time></General>
</QTM_Parameters_Ver_{self.version}>
"""
        await self.conn.new()
        await self.conn.send_xml(xml)
        try:
            await self.conn.start()
        except QRTCommandException:
            await self.conn.new()
            await self.conn.send_xml(xml)
            await self.conn.start()
        await self.conn.await_event(QRTEvent.EventCaptureStarted, timeout=5)

    async def stop_recording(self, filename: str):
        """Stop capture and save."""
        await self.conn.stop()
        try:
            await self.conn.await_event(QRTEvent.EventCaptureStopped, timeout=5)
        except asyncio.TimeoutError:
            pass
        await self.conn.save(filename, overwrite=True)

    async def disconnect(self):
        await self.conn.release_control()
        await self.conn.close()
        self.conn.disconnect()