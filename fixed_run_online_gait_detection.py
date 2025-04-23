#!/usr/bin/env python3
import asyncio
import qtm_rt
from qtm_rt import QRTEvent, QRTCommandException

import serial
import time
from functools import partial

# ———— Serial trigger helper ————
def send_trigger(code: int,
                 port: str = 'COM6',
                 baudrate: int = 115200,
                 pulse_duration: float = 0.01):
    """
    Send a single trigger pulse over serial.
    """
    with serial.Serial(port,
                       baudrate=baudrate,
                       bytesize=serial.EIGHTBITS,
                       parity=serial.PARITY_NONE,
                       stopbits=serial.STOPBITS_ONE,
                       timeout=1) as ser:
        ser.write(bytes([0x00]))
        time.sleep(0.001)
        ser.write(bytes([code]))
        time.sleep(pulse_duration)
        ser.write(bytes([0x00]))
        time.sleep(0.001)

# ———— Gait detection callback ————
def make_gait_callback(
    front_idx: int,
    back_idx: int,
    threshold: float,
    trigger_funcs: dict
):
    """
    Returns an async-compatible callback that:
     - reads analog_data
     - detects HS/TO for front/back (alternating as R/L)
     - sends serial triggers via trigger_funcs mapping
    trigger_funcs: {
        'RHS': func, 'RTO': func,
        'LHS': func, 'LTO': func
    }
    """
    # State
    prev_front_on = False
    prev_back_on  = False
    first_strike_is_right = True  # you can parameterize this
    front_strikes = []  # for alternation

    async def on_packet(packet):
        nonlocal prev_front_on, prev_back_on, front_strikes

        result = packet.get_analog()
        if result is None:
            return
        _, analog_data = result
        # Loop through each sample in this packet
        for sample in analog_data:
            fz_front = sample[front_idx]
            fz_back  = sample[back_idx]

            # Detect rising/falling on front plate (HS)
            front_on = (fz_front >= threshold)
            if front_on and not prev_front_on:
                # heel-strike
                front_strikes.append(time.time())
                is_right = (len(front_strikes) % 2 == 1) == first_strike_is_right
                evt = 'RHS' if is_right else 'LHS'
                # send trigger
                asyncio.get_event_loop().run_in_executor(
                    None, trigger_funcs[evt]
                )
            prev_front_on = front_on

            # Detect rising/falling on back plate (TO)
            back_on = (fz_back >= threshold)
            if not back_on and prev_back_on:
                # toe-off — use same alternation logic
                is_right = (len(front_strikes) % 2 == 1) == first_strike_is_right
                evt = 'RTO' if is_right else 'LTO'
                asyncio.get_event_loop().run_in_executor(
                    None, trigger_funcs[evt]
                )
            prev_back_on = back_on

    return on_packet


# ———— Main measurement function ————
async def record_measurement(
    host: str = "127.0.0.1",
    password: str = "",
    duration: float = 10.0,
    filename: str = "my_capture.qtm",
    version: str = "1.22",
    *,
    start_code:   int = 2,
    end_code:     int = 3,
    port:         str = "COM6",
    baudrate:     int = 115200,
    pulse_duration: float = 0.01,
    # ——— New gait params ———
    online_gait_event: bool = False,
    threshold:   float = 20.0,      # N
    front_fz_idx:int    = 2,       # 0-based
    back_fz_idx: int    = 8,       # 0-based
    rhs_code:    int    = 4,
    rto_code:    int    = 5,
    lhs_code:    int    = 6,
    lto_code:    int    = 7
):
    # 1) Connect
    conn = await qtm_rt.connect(host, version=version)
    if conn is None:
        print("Error: Unable to connect to QTM.")
        return
    print("[+] Connected to QTM")

    # 2) Take control & clear
    await conn.take_control(password)
    for fn in (conn.stop, conn.close):
        try: await fn()
        except: pass
    print("[+] Control taken; cleared previous session")

    # 3) Set capture time via XML
    xml = f"""
<QTM_Settings>
  <General><Capture_Time>{duration}</Capture_Time></General>
</QTM_Settings>
"""
    await conn.new()
    try: 
        await conn.await_event(None, timeout=5)
    except asyncio.TimeoutError: pass
    await conn.send_xml(xml)
    print(f"[+] Capture_Time set to {duration}s")

    # 4) Start capture (retry)
    for attempt in (1, 2):
        try:
            await conn.start(); break
        except QRTCommandException as e:
            print(f"[!] Start failed ({e}); retrying [{attempt}/2]")
            await conn.new()
            try: await conn.await_event(None, timeout=5)
            except: pass
            await conn.send_xml(xml)
    else:
        print("[!] Could not start capture; aborting"); return

    # 5) Confirm capture
    try:
        await conn.await_event(QRTEvent.EventCaptureStarted, timeout=5)
        print("[+] Capture confirmed active")
    except asyncio.TimeoutError:
        print("[!] No CaptureStarted event; proceeding")

    # Prepare start/end triggers
    loop = asyncio.get_running_loop()
    trigger_start = partial(send_trigger, start_code, port, baudrate, pulse_duration)
    trigger_end   = partial(send_trigger, end_code,   port, baudrate, pulse_duration)

    # 6) TaskStart marker
    await asyncio.gather(
        conn.set_qtm_event("TaskStart"),
        loop.run_in_executor(None, trigger_start)
    )
    print(f"[+] Sent TaskStart / code {start_code}")

    # ——— Set up gait detection if enabled ———
    if online_gait_event:
        trigger_funcs = {
            'RHS': partial(send_trigger, rhs_code, port, baudrate, pulse_duration),
            'RTO': partial(send_trigger, rto_code, port, baudrate, pulse_duration),
            'LHS': partial(send_trigger, lhs_code, port, baudrate, pulse_duration),
            'LTO': partial(send_trigger, lto_code, port, baudrate, pulse_duration),
        }
        on_gait = make_gait_callback(
            front_idx=front_fz_idx,
            back_idx=back_fz_idx,
            threshold=threshold,
            trigger_funcs=trigger_funcs
        )
    else:
        on_gait = None

    # 7) Stream frames: always stream analog; if gait enabled, attach callback
    await conn.stream_frames(
        frames="allframes",
        components=["analog"],
        on_packet=on_gait
    )

    # 8) Wait until near end, then TaskEnd
    await asyncio.sleep(max(0, duration - 0.5))
    await asyncio.gather(
        conn.set_qtm_event("TaskEnd"),
        loop.run_in_executor(None, trigger_end)
    )
    print(f"[+] Sent TaskEnd / code {end_code}")

    # 9) Stop & save
    await conn.stop()
    try: 
        await conn.await_event(QRTEvent.EventCaptureStopped, timeout=5)
        print("[+] Capture stopped")
    except asyncio.TimeoutError:
        print("[!] No CaptureStopped event; proceeding")

    await conn.save(filename, overwrite=True)
    print(f"[+] Saved as '{filename}'")

    # 10) Cleanup
    await conn.close()
    await conn.release_control()
    conn.disconnect()
    print("[+] Session closed")

# ———— Entry point ————
if __name__ == "__main__":
    asyncio.run(record_measurement(
        host="127.0.0.1",
        password="",
        duration=10.0,
        filename="sina_capture.qtm",
        version="1.22",
        start_code=2,
        end_code=3,
        port='COM6',
        baudrate=115200,
        pulse_duration=0.01,
        online_gait_event=True,   # enable real-time HS/TO detection
        threshold=20.0,
        front_fz_idx=2,
        back_fz_idx=8,
        rhs_code=4,
        rto_code=5,
        lhs_code=6,
        lto_code=7
    ))
