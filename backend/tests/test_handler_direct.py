"""
Test message handler directly to debug the issue
"""

import asyncio
from datetime import date
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from connection_state import ConnectionState
from schemas import CreateAllocator, ComputePortfolio
from message_handlers import handle_create_allocator, handle_compute_portfolio


class FakeWebSocket:
    """Fake WebSocket for testing"""
    def __init__(self):
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)
        print(f"\n[WS SEND] {data['type']}")
        if data['type'] == 'result':
            print(json.dumps(data, indent=2))


async def main():
    print("Testing message handlers directly...")
    print("=" * 70)

    ws = FakeWebSocket()
    state = ConnectionState()

    # Create allocator
    print("\n[1] Creating manual allocator...")
    create_msg = CreateAllocator(
        type="create_allocator",
        allocator_type="manual",
        config={
            "name": "Direct Test Manual",
            "allocations": {"AAPL": 0.6, "MSFT": 0.4}
        }
    )

    await handle_create_allocator(ws, state, create_msg)

    # Get the allocator ID
    allocator_id = ws.messages[-1].get('id')
    print(f"Created allocator: {allocator_id}")

    # Compute
    print("\n[2] Computing portfolio...")
    compute_msg = ComputePortfolio(
        type="compute",
        allocator_id=allocator_id,
        fit_start_date="2023-01-01",
        fit_end_date="2023-12-31",
        test_end_date="2024-06-01",
        include_dividends=True
    )

    await handle_compute_portfolio(ws, state, compute_msg)

    # Analyze results
    print("\n[3] Results:")
    print("-" * 70)

    result_msg = None
    for msg in ws.messages:
        if msg.get('type') == 'result':
            result_msg = msg
            break

    if result_msg:
        segments = result_msg.get('segments', [])
        performance = result_msg.get('performance', {})

        print(f"\nSegments: {len(segments)}")
        for i, seg in enumerate(segments):
            print(f"  [{i}] {seg.get('start_date')} to {seg.get('end_date')}")
            print(f"      Weights: {seg.get('weights')}")

        dates = performance.get('dates', [])
        returns = performance.get('cumulative_returns', [])

        print(f"\nPerformance data points: {len(dates)}")
        if dates:
            print(f"  First: {dates[0]}: {returns[0]:.4f}%")
            print(f"  Last: {dates[-1]}: {returns[-1]:.4f}%")
        else:
            print("  WARNING: No performance data!")


if __name__ == "__main__":
    asyncio.run(main())
