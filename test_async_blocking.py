#!/usr/bin/env python3
"""
Test to check if pymodbus serial reads block the event loop or properly yield.

Run this alongside your Home Assistant to see if other tasks can execute
during Modbus reads.
"""

import asyncio
import time
from pymodbus.client import AsyncModbusSerialClient


async def heartbeat_task(name: str, interval: float = 0.5):
    """Task that prints a heartbeat - should run even during Modbus reads."""
    count = 0
    while True:
        count += 1
        print(f"[{time.strftime('%H:%M:%S')}] {name} heartbeat #{count}")
        await asyncio.sleep(interval)


async def modbus_read_task(port: str = "/dev/ttyUSB0"):
    """Perform Modbus reads and measure timing."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Creating serial client...")

    client = AsyncModbusSerialClient(
        port=port,
        baudrate=9600,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=5
    )

    try:
        print(f"[{time.strftime('%H:%M:%S')}] Connecting...")
        await client.connect()

        if not client.connected:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Failed to connect!")
            return

        print(f"[{time.strftime('%H:%M:%S')}] ✅ Connected!")

        # Perform several reads
        for i in range(3):
            print(f"\n[{time.strftime('%H:%M:%S')}] 📖 Starting read #{i+1} (48 registers)...")
            start = time.perf_counter()

            client.slave = 1
            result = await client.read_input_registers(address=33049, count=48)

            elapsed = (time.perf_counter() - start) * 1000

            if result.isError():
                print(f"[{time.strftime('%H:%M:%S')}]   ❌ Read failed: {result}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}]   ✅ Read successful: {len(result.registers)} registers in {elapsed:.1f}ms")

            await asyncio.sleep(1)  # Wait between reads

    finally:
        client.close()
        print(f"\n[{time.strftime('%H:%M:%S')}] Connection closed")


async def main():
    """Run heartbeat and Modbus reads concurrently."""
    print("=" * 70)
    print("Testing if pymodbus yields event loop during serial I/O")
    print("=" * 70)
    print("\n⚠️  WATCH THE HEARTBEAT TIMESTAMPS:")
    print("   - If heartbeats pause during reads: BLOCKING (bad)")
    print("   - If heartbeats continue smoothly: NON-BLOCKING (good)")
    print("\n" + "=" * 70 + "\n")

    # Start heartbeat task
    heartbeat = asyncio.create_task(heartbeat_task("🫀", interval=0.5))

    # Wait a bit for heartbeat to start
    await asyncio.sleep(2)

    # Start Modbus reads
    try:
        await modbus_read_task()
    except Exception as e:
        print(f"\n❌ Error: {e}")

    # Let heartbeat run a bit more
    await asyncio.sleep(2)

    heartbeat.cancel()
    try:
        await heartbeat
    except asyncio.CancelledError:
        pass

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
