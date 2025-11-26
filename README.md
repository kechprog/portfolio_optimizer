# Portfolio Optimizer

A real-time portfolio optimization application built with React and Python, featuring Modern Portfolio Theory (MPT) allocators with WebSocket-based communication.

## Overview

Portfolio Optimizer allows users to create, configure, and backtest different portfolio allocation strategies. It supports manual allocations as well as automated optimization using Max Sharpe Ratio and Minimum Volatility strategies from Modern Portfolio Theory.

## Key Features

- **Multiple Allocator Types**
  - **Manual**: Define fixed allocations across instruments
  - **Max Sharpe**: Optimize for maximum risk-adjusted returns using the Sharpe ratio
  - **Min Volatility**: Minimize portfolio variance with optional target return constraints

- **Real-Time Computation**: WebSocket-based communication for live progress updates during backtests
- **Dynamic Rebalancing**: Configure automatic portfolio rebalancing at custom intervals
- **Performance Analytics**: Comprehensive metrics including total return, annualized return, volatility, Sharpe ratio, and max drawdown
- **Interactive Charts**: Zoomable, pannable performance charts with selection tooltips
- **Dark/Light Theme**: Full theme support with system preference detection

## Tech Stack

### Frontend
- React 19 with TypeScript
- Vite for build tooling
- Tailwind CSS for styling
- Recharts for data visualization
- WebSocket for real-time communication

### Backend
- Python 3.11+ with FastAPI
- PyPortfolioOpt for MPT optimization
- Pandas for data manipulation
- Alpha Vantage API for price data
- SQLite for caching (optional)

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Alpha Vantage API key (free tier available)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export ALPHA_VANTAGE_API_KEY=your_api_key_here

# Start server
python main.py
```

The backend runs on `ws://localhost:8000/ws`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend runs on `http://localhost:5173`

## Project Structure

```
portfolio_optimizer_react/
├── backend/
│   ├── allocators/           # Allocation strategy implementations
│   │   ├── base.py          # Abstract base classes
│   │   ├── manual.py        # Manual allocator
│   │   ├── max_sharpe.py    # Max Sharpe optimizer
│   │   └── min_volatility.py # Min volatility optimizer
│   ├── services/
│   │   ├── portfolio.py     # Performance calculation
│   │   └── price_fetcher.py # Price data fetching
│   ├── main.py              # FastAPI WebSocket server
│   ├── message_handlers.py  # WebSocket message routing
│   ├── schemas.py           # Pydantic message models
│   └── connection_state.py  # Per-connection state
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── services/        # WebSocket service
│   │   └── types/           # TypeScript definitions
│   └── ...
└── README.md
```

## Usage

1. **Create an Allocator**: Click "+ Add" and choose allocator type
2. **Configure**: Set instruments, weights, and options
3. **Set Date Range**: Define fit period (training) and test period (backtest)
4. **Compute**: Click "Compute" to run the backtest
5. **Analyze**: View performance metrics and charts

## Configuration Options

### Manual Allocator
- Name and fixed percentage allocations per ticker

### Max Sharpe / Min Volatility Allocators
- Instrument list (tickers)
- Allow shorting toggle
- Use adjusted close (dividend-adjusted) prices
- Update interval for dynamic rebalancing
- Target return (Min Volatility only)

## API Reference

### WebSocket Messages

**Client → Server:**
- `create_allocator`: Create new allocator
- `update_allocator`: Update allocator config
- `delete_allocator`: Remove allocator
- `compute`: Run portfolio computation

**Server → Client:**
- `allocator_created`: Confirmation with ID
- `progress`: Computation progress updates
- `result`: Final computation results with performance data
- `error`: Error messages

## Performance Metrics

| Metric | Description |
|--------|-------------|
| Total Return | Cumulative percentage return over test period |
| Annualized Return | CAGR (Compound Annual Growth Rate) |
| Volatility | Annualized standard deviation of daily returns |
| Sharpe Ratio | Risk-adjusted return (assumes 4% risk-free rate) |
| Max Drawdown | Largest peak-to-trough decline |

## Known Limitations

- Alpha Vantage free tier: 25 requests/day, 5 requests/minute
- Price data cached locally to minimize API calls
- Optimization assumes normally distributed returns
- No transaction costs modeled

## Development

```bash
# Run frontend in development mode
cd frontend && npm run dev

# Run backend with auto-reload
cd backend && uvicorn main:app --reload

# Type check frontend
cd frontend && npx tsc --noEmit

# Build for production
cd frontend && npm run build
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read the architecture documentation before submitting PRs.
