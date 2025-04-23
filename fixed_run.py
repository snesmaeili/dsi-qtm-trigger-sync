#!/usr/bin/env python3
import asyncio
import qtm_rt
from qtm_rt import QRTEvent, QRTCommandException

import serial
import time
from functools import partial

def send_trigger(code: int,
                 port: str = 'COM6',
                 baudrate: int = 115200,
                 pulse_duration: float = 0.01):
    """
    Send a single trigger pulse to the NeuroSpec hub over serial.
    """
    with serial.Serial(port,
                       baudrate=baudrate,
                       bytesize=serial.EIGHTBITS,
                       parity=serial.PARITY_NONE,
                       stopbits=serial.STOPBITS_ONE,
                       timeout=1) as ser:
        # ensure line is low
        ser.write(bytes([0x00]))
        time.sleep(0.001)
        # send code
        ser.write(bytes([code]))
        time.sleep(pulse_duration)
        # reset line
        ser.write(bytes([0x00]))
        time.sleep(0.001)

async def record_measurement(
    host: str = "127.0.0.1",
    password: str = "",
    duration: float = 10.0,
    filename: str = "my_capture.qtm",
    version: str = "1.22",
    *,
    start_code: int = 2,
    end_code:   int = 3,
    port:       str = "COM6",
    baudrate:   int = 115200,
    pulse_duration: float = 0.1,
):
    # 1) Connect to QTM
    conn = await qtm_rt.connect(host, version=version)
    if conn is None:
        print("Error: Unable to connect to QTM.")
        return
    print("[+] Connected to QTM")

    # 2) Take control & clear previous
    await conn.take_control(password)
    for fn in (conn.stop, conn.close):
        try: await fn()
        except: pass
    print("[+] Control taken; cleared previous session")

    # 3) Build and send XML for duration
    xml = f"""
<QTM_Settings>
  <General>
    <Capture_Time>{duration}</Capture_Time>
  </General>
</QTM_Settings>
"""
    await conn.new()
    try: await conn.await_event(None, timeout=5)
    except asyncio.TimeoutError: pass
    await conn.send_xml(xml)
    print(f"[+] Capture_Time set to {duration}s")

    # 4) Start capture (with retry)
    for attempt in (1, 2):
        try:
            await conn.start()
            break
        except QRTCommandException as e:
            print(f"[!] Start failed ({e}); retrying [{attempt}/2]")
            await conn.new()
            try: await conn.await_event(None, timeout=5)
            except asyncio.TimeoutError: pass
            await conn.send_xml(xml)
    else:
        print("[!] Could not start capture; aborting")
        return

    # 5) Confirm capture
    try:
        await conn.await_event(QRTEvent.EventCaptureStarted, timeout=5)
        print("[+] Capture confirmed active")
    except asyncio.TimeoutError:
        print("[!] No CaptureStarted event; proceeding")

    # Prepare partials for serial triggers
    loop = asyncio.get_running_loop()
    trigger_start = partial(send_trigger,
                             start_code,
                             port=port,
                             baudrate=baudrate,
                             pulse_duration=pulse_duration)
    trigger_end   = partial(send_trigger,
                             end_code,
                             port=port,
                             baudrate=baudrate,
                             pulse_duration=pulse_duration)

    # 6) Fire both Start markers together
    await asyncio.gather(
        conn.set_qtm_event("TaskStart"),
        loop.run_in_executor(None, trigger_start)
    )
    print(f"[+] Sent TaskStart to QTM and serial code {start_code}")

    # 7) Sleep until just before end, then fire End markers together
    await asyncio.sleep(max(0, duration - 0.5))
    await asyncio.gather(
        conn.set_qtm_event("TaskEnd"),
        loop.run_in_executor(None, trigger_end)
    )
    print(f"[+] Sent TaskEnd to QTM and serial code {end_code}")

    # 8) Stop & save
    await conn.stop()
    try:
        await conn.await_event(QRTEvent.EventCaptureStopped, timeout=5)
        print("[+] Capture stopped")
    except asyncio.TimeoutError:
        print("[!] No CaptureStopped event; proceeding")

    await conn.save(filename, overwrite=True)
    print(f"[+] Measurement saved as '{filename}'")

    # 9) Cleanup
    await conn.close()
    await conn.release_control()
    conn.disconnect()
    print("[+] Session closed and control released")


if __name__ == "__main__":
    asyncio.run(record_measurement(
        host="127.0.0.1",
        password="",
        duration=10,
        filename="sina_capture.qtm",
        version="1.22",
        start_code=2,
        end_code=3,
        port='COM6',
        baudrate=115200,
        pulse_duration=0.01
    ))