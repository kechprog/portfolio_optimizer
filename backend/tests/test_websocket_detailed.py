"""
Detailed WebSocket Test - Shows all data including errors
"""

import asyncio
import json
import websockets


async def test_manual_detailed():
    """Test manual allocator with detailed output."""
    print("\n" + "=" * 70)
    print("  DETAILED MANUAL TEST")
    print("=" * 70)

    async with websockets.connect("ws://localhost:8000/ws") as ws:
        # Create manual allocator
        print("\n[1] Creating manual allocator...")
        create_msg = {
            "type": "create_allocator",
            "allocator_type": "manual",
            "config": {
                "name": "Detailed Test Manual",
                "allocations": {"AAPL": 0.6, "MSFT": 0.4}
            }
        }

        await ws.send(json.dumps(create_msg))
        response = json.loads(await ws.recv())
        print(f"Created: {json.dumps(response, indent=2)}")

        allocator_id = response.get("id") or response.get("allocator_id")

        # Compute with more detailed dates
        print("\n[2] Computing portfolio...")
        compute_msg = {
            "type": "compute",
            "allocator_id": allocator_id,
            "fit_start_date": "2023-01-01",
            "fit_end_date": "2023-12-31",
            "test_end_date": "2024-06-01",
            "include_dividends": True
        }

        await ws.send(json.dumps(compute_msg))

        print("\n[3] All Messages Received:")
        print("-" * 70)

        all_messages = []
        result_msg = None

        while True:
            response = json.loads(await ws.recv())
            all_messages.append(response)
            msg_type = response.get("type")

            print(f"\n  MESSAGE #{len(all_messages)} - Type: {msg_type}")
            print(json.dumps(response, indent=4))

            if msg_type in ["result", "error"]:
                result_msg = response
                break

        # Analyze the result
        print("\n" + "=" * 70)
        print("  DETAILED ANALYSIS")
        print("=" * 70)

        if result_msg and result_msg.get("type") == "result":
            segments = result_msg.get("segments", [])
            performance = result_msg.get("performance", {})

            print(f"\n  Total segments: {len(segments)}")
            for i, seg in enumerate(segments):
                print(f"\n  Segment {i}:")
                print(f"    Start: {seg.get('start_date')}")
                print(f"    End: {seg.get('end_date')}")
                print(f"    Weights: {seg.get('weights')}")
                total = sum(seg.get('weights', {}).values())
                print(f"    Total weight: {total:.4f}")

            dates = performance.get("dates", [])
            returns = performance.get("cumulative_returns", [])

            print(f"\n  Performance:")
            print(f"    Total data points: {len(dates)}")

            if dates:
                print(f"    Date range: {dates[0]} to {dates[-1]}")
                print(f"    Return range: {returns[0]:.4f}% to {returns[-1]:.4f}%")

                # Show first 5 and last 5 data points
                print(f"\n    First 5 data points:")
                for i in range(min(5, len(dates))):
                    print(f"      {dates[i]}: {returns[i]:.4f}%")

                if len(dates) > 10:
                    print(f"\n    Last 5 data points:")
                    for i in range(max(0, len(dates)-5), len(dates)):
                        print(f"      {dates[i]}: {returns[i]:.4f}%")
            else:
                print("    WARNING: No performance data!")

        elif result_msg and result_msg.get("type") == "error":
            print(f"\n  ERROR: {result_msg.get('message')}")

        # Cleanup
        print("\n[4] Cleaning up...")
        await ws.send(json.dumps({"type": "delete_allocator", "id": allocator_id}))
        await ws.recv()
        print("  Deleted allocator")


if __name__ == "__main__":
    asyncio.run(test_manual_detailed())
