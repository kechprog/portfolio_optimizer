"""
Verbose WebSocket Test - Shows detailed return data for analysis
"""

import asyncio
import json
import websockets


async def test_max_sharpe_verbose():
    """Test max_sharpe with verbose output."""
    print("\n" + "=" * 70)
    print("  VERBOSE MAX SHARPE TEST")
    print("=" * 70)

    async with websockets.connect("ws://localhost:8000/ws") as ws:
        # Create max_sharpe allocator
        print("\n[1] Creating max_sharpe allocator...")
        create_msg = {
            "type": "create_allocator",
            "allocator_type": "max_sharpe",
            "config": {
                "name": "Verbose Test MaxSharpe",
                "instruments": ["AAPL", "MSFT", "GOOG"],
                "allow_shorting": False,
                "use_adj_close": True,
                "update_enabled": False,
                "update_interval_value": 30,
                "update_interval_unit": "days"
            }
        }

        await ws.send(json.dumps(create_msg))
        response = json.loads(await ws.recv())
        print(f"Created: {json.dumps(response, indent=2)}")

        allocator_id = response.get("id") or response.get("allocator_id")

        # Compute
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

        print("\n[3] Progress and Results:")
        print("-" * 70)

        result_msg = None
        while True:
            response = json.loads(await ws.recv())
            msg_type = response.get("type")

            if msg_type == "progress":
                progress = response.get("progress", 0)
                message = response.get("message", "")
                print(f"  PROGRESS: {progress:.1%} - {message}")

            elif msg_type == "result":
                result_msg = response
                print("\n  FINAL RESULT:")
                print(json.dumps(response, indent=4))
                break

            elif msg_type == "error":
                print(f"\n  ERROR: {response.get('message')}")
                result_msg = response
                break

            else:
                print(f"  OTHER: {msg_type}")
                print(json.dumps(response, indent=4))

        # Analyze the result
        print("\n" + "=" * 70)
        print("  ANALYSIS")
        print("=" * 70)

        if result_msg and result_msg.get("type") == "result":
            segments = result_msg.get("segments", [])
            performance = result_msg.get("performance", {})

            print(f"\n  Segments returned: {len(segments)}")
            if segments:
                print("  Segment details:")
                for i, seg in enumerate(segments):
                    print(f"    [{i}] {seg.get('start_date')} to {seg.get('end_date')}")
                    weights = seg.get("weights", {})
                    print(f"        Weights: {weights}")
                    total_weight = sum(weights.values())
                    print(f"        Total weight: {total_weight:.4f}")
            else:
                print("  WARNING: No segments returned!")

            dates = performance.get("dates", [])
            returns = performance.get("cumulative_returns", [])

            print(f"\n  Performance data points: {len(dates)}")
            if dates:
                print(f"    First date: {dates[0]}")
                print(f"    Last date: {dates[-1]}")
                print(f"    First return: {returns[0]:.4f}%")
                print(f"    Last return: {returns[-1]:.4f}%")
            else:
                print("  WARNING: No performance data returned!")

        # Cleanup
        print("\n[4] Cleaning up...")
        await ws.send(json.dumps({"type": "delete_allocator", "id": allocator_id}))
        await ws.recv()
        print("  Deleted allocator")


if __name__ == "__main__":
    asyncio.run(test_max_sharpe_verbose())
