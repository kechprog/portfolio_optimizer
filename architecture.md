# Architecture Documentation

This document describes the technical architecture of the Portfolio Optimizer application, including design decisions, data flow, and identified issues with improvement recommendations.

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Architecture](#backend-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Data Flow](#data-flow)
5. [Known Issues & Improvements](#known-issues--improvements)
6. [Security Considerations](#security-considerations)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Components │  │    Hooks    │  │   WebSocketService      │  │
│  │  (UI Layer) │  │ (useWebSocket)│ │  (Connection Manager)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket (ws://localhost:8000/ws)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                         Backend (Python)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   FastAPI   │  │  Handlers   │  │      Allocators         │  │
│  │  (main.py)  │  │ (routing)   │  │  (MPT Optimization)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Schemas    │  │  Services   │  │    Price Fetcher        │  │
│  │ (Pydantic)  │  │(Performance)│  │   (Alpha Vantage)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS API
                              ▼
                    ┌─────────────────┐
                    │  Alpha Vantage  │
                    │   (Price Data)  │
                    └─────────────────┘
```

---

## Backend Architecture

### Core Components

#### 1. WebSocket Server (`main.py`)

The entry point for all client connections. Uses FastAPI with WebSocket support.

```python
# Connection lifecycle
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state = ConnectionState()  # Per-connection state
    try:
        while True:
            message = await websocket.receive_text()
            # Route to appropriate handler
    finally:
        state.clear()
```

**Key Characteristics:**
- Per-connection state isolation via `ConnectionState`
- Message routing based on `type` discriminator
- Pydantic validation of all incoming messages

#### 2. Message Handlers (`message_handlers.py`)

Routes messages to appropriate business logic:

| Message Type | Handler | Description |
|--------------|---------|-------------|
| `create_allocator` | `handle_create_allocator` | Creates new allocator instance |
| `update_allocator` | `handle_update_allocator` | Updates allocator configuration |
| `delete_allocator` | `handle_delete_allocator` | Removes allocator |
| `compute` | `handle_compute_portfolio` | Runs portfolio optimization |
| `list_allocators` | `handle_list_allocators` | Returns all allocators |

#### 3. Allocators (`allocators/`)

**Base Classes (`base.py`):**
```python
class Allocator(ABC):
    @abstractmethod
    async def compute(
        self,
        fit_start_date: date,
        fit_end_date: date,
        test_end_date: date,
        include_dividends: bool,
        price_fetcher: PriceFetcher,
        progress_callback: ProgressCallback
    ) -> Portfolio:
        pass

class Portfolio:
    segments: List[PortfolioSegment]

class PortfolioSegment:
    start_date: date
    end_date: date
    allocations: Dict[str, float]  # ticker -> weight
```

**Allocator Implementations:**

| Allocator | File | Strategy |
|-----------|------|----------|
| Manual | `manual.py` | Fixed user-defined allocations |
| Max Sharpe | `max_sharpe.py` | Maximize Sharpe ratio using PyPortfolioOpt |
| Min Volatility | `min_volatility.py` | Minimize variance, optional target return |

**Optimization Flow (Max Sharpe / Min Volatility):**
```
1. Fetch price data for all instruments
2. Calculate expected returns (mean historical)
3. Build covariance matrix (Ledoit-Wolf shrinkage)
4. Run convex optimization (EfficientFrontier)
5. Clean weights and return allocations
6. If dynamic rebalancing: repeat for each interval
```

#### 4. Services

**Portfolio Service (`services/portfolio.py`):**
- `compute_performance()`: Calculates cumulative returns over test period
- `calculate_metrics()`: Computes stats (CAGR, volatility, Sharpe, max drawdown)

**Price Fetcher (`services/price_fetcher.py`):**
- Fetches daily OHLCV data from Alpha Vantage
- Implements caching to minimize API calls
- Handles rate limiting and retries

#### 5. Connection State (`connection_state.py`)

Per-connection state management:
```python
class ConnectionState:
    allocators: Dict[str, Any]  # id -> {type, config, instance}
    matrix_cache: Dict[str, Any]  # Covariance matrix cache
```

---

## Frontend Architecture

### Component Hierarchy

```
App.tsx (State Management + WebSocket)
├── Header (Date selection, compute button)
├── MainLayout
│   ├── AllocatorGrid / AllocatorList (Allocator management)
│   │   └── AllocatorRow / AllocatorCard
│   ├── PerformanceChart (Main chart)
│   └── PortfolioInfo (Allocation chart + stats)
└── Modals
    ├── CreateAllocatorModal
    ├── ManualAllocatorModal
    └── MPTAllocatorModal
```

### State Management

**Current Approach:** Centralized in App.tsx with useState hooks

```typescript
// Core state (App.tsx)
const [allocators, setAllocators] = useState<Allocator[]>([]);
const [results, setResults] = useState<Record<string, AllocatorResult>>({});
const [dateRange, setDateRange] = useState<DateRange>(...);
const [isComputing, setIsComputing] = useState(false);
const [computingProgress, setComputingProgress] = useState<Progress | null>(null);

// UI state
const [selectedAllocatorId, setSelectedAllocatorId] = useState<string | null>(null);
const [showCreateModal, setShowCreateModal] = useState(false);
```

### WebSocket Integration

**WebSocketService (`services/WebSocketService.ts`):**
```typescript
class WebSocketService {
    private ws: WebSocket | null;
    private messageHandlerRef: React.MutableRefObject<...>;

    connect(url: string): void;
    disconnect(): void;
    send(message: ClientMessage): void;

    // Reconnection with exponential backoff
    private attemptReconnect(): void;
}
```

**useWebSocket Hook (`hooks/useWebSocket.ts`):**
```typescript
function useWebSocket(url: string, options?: WebSocketOptions) {
    const [status, setStatus] = useState<ConnectionStatus>('disconnected');
    const [error, setError] = useState<string | null>(null);

    return {
        status,
        error,
        send,
        setMessageHandler,
        connect,
        disconnect,
    };
}
```

### Type System

**Core Types (`types/index.ts`):**
```typescript
type AllocatorType = 'manual' | 'max_sharpe' | 'min_volatility';

interface Allocator {
    id: string;
    type: AllocatorType;
    config: AllocatorConfig;
    enabled: boolean;
}

interface AllocatorResult {
    allocator_id: string;
    segments: PortfolioSegment[];
    performance: PerformanceData;
}

interface PerformanceData {
    dates: string[];
    cumulative_returns: number[];
    stats?: PerformanceStats;
}
```

---

## Data Flow

### 1. Create Allocator Flow

```
User clicks "Add Allocator"
    │
    ▼
CreateAllocatorModal opens
    │
    ▼
User configures → ManualAllocatorModal or MPTAllocatorModal
    │
    ▼
Frontend sends: { type: "create_allocator", allocator_type, config }
    │
    ▼
Backend creates instance → stores in ConnectionState
    │
    ▼
Backend sends: { type: "allocator_created", id, allocator_type, config }
    │
    ▼
Frontend updates allocators state
```

### 2. Compute Flow

```
User clicks "Compute"
    │
    ▼
Frontend sends: { type: "compute", allocator_id, dates, include_dividends }
    │
    ▼
Backend: handle_compute_portfolio()
    ├── Fetch price data (with caching)
    ├── Run optimization algorithm
    ├── Send progress updates: { type: "progress", step, total_steps }
    └── Calculate performance metrics
    │
    ▼
Backend sends: { type: "result", allocator_id, segments, performance }
    │
    ▼
Frontend updates results state → charts re-render
```

### 3. Message Types

**Client → Server:**
```typescript
type ClientMessage =
    | { type: 'create_allocator'; allocator_type: string; config: object }
    | { type: 'update_allocator'; id: string; config: object }
    | { type: 'delete_allocator'; id: string }
    | { type: 'compute'; allocator_id: string; fit_start_date: string; ... }
    | { type: 'list_allocators' };
```

**Server → Client:**
```typescript
type ServerMessage =
    | { type: 'allocator_created'; id: string; ... }
    | { type: 'allocator_updated'; id: string; ... }
    | { type: 'allocator_deleted'; id: string }
    | { type: 'progress'; allocator_id: string; step: number; total_steps: number }
    | { type: 'result'; allocator_id: string; segments: []; performance: {} }
    | { type: 'error'; message: string; allocator_id?: string };
```

---

## Known Issues & Improvements

### Critical Issues

#### Backend

| Issue | Location | Severity | Description |
|-------|----------|----------|-------------|
| Look-ahead bias risk | `portfolio.py:83` | CRITICAL | `ffill().bfill()` can introduce future data into backtest |
| Silent optimization failures | `max_sharpe.py:136` | HIGH | Returns empty portfolio instead of raising error |
| O(n²) price fetching | `max_sharpe.py:174` | HIGH | Dynamic rebalancing re-fetches all data each interval |
| No thread safety | `connection_state.py:26` | HIGH | Dict not protected for concurrent async access |

#### Frontend

| Issue | Location | Severity | Description |
|-------|----------|----------|-------------|
| Memory leak | `WebSocketService.ts:95-98` | CRITICAL | Event listeners not cleaned on reconnect |
| Stale closure | `PortfolioInfo.tsx:193` | CRITICAL | `handleWheel` has empty dependency array |
| Type safety bypass | `App.tsx:71` | HIGH | `as unknown as` casts bypass TypeScript |
| Missing ARIA labels | Multiple modals | HIGH | Accessibility violations |

### Recommended Improvements

#### Priority 1: Critical (Immediate)

1. **Fix WebSocket Memory Leak**
   ```typescript
   // WebSocketService.ts - Add cleanup
   disconnect(): void {
       if (this.ws) {
           this.ws.onopen = null;
           this.ws.onclose = null;
           this.ws.onerror = null;
           this.ws.onmessage = null;
           this.ws.close();
       }
   }
   ```

2. **Add Asyncio Lock to ConnectionState**
   ```python
   # connection_state.py
   import asyncio

   class ConnectionState:
       def __init__(self):
           self._lock = asyncio.Lock()

       async def add_allocator(self, ...):
           async with self._lock:
               # ... safe mutation
   ```

3. **Fix Data Alignment in Portfolio**
   ```python
   # portfolio.py - Don't use global ffill/bfill
   # Only fill within each day's available data
   ```

#### Priority 2: High (Next Sprint)

4. **Implement Proper State Management**
   - Consider Zustand or React Query for frontend
   - Separate server state from UI state

5. **Add Data Validation**
   - Validate allocations sum to ~1.0
   - Check minimum data points before optimization
   - Validate date ranges

6. **Extract Common Allocator Logic**
   ```python
   class OptimizationAllocatorBase(Allocator):
       # Shared _fetch_prices, _get_update_delta
       @abstractmethod
       def _optimize(self, ef: EfficientFrontier) -> Dict[str, float]:
           pass
   ```

#### Priority 3: Medium (Backlog)

7. **Performance Optimizations**
   - Cache price data across allocators
   - Use `asyncio.gather()` for concurrent fetches
   - Implement rolling window caching

8. **Accessibility Improvements**
   - Add focus traps to modals
   - Implement keyboard navigation for charts
   - Add proper ARIA labels

9. **Build Optimization**
   - Configure Vite for chunk splitting
   - Lazy load modal components
   - Upgrade to Tailwind CSS v4

---

## Security Considerations

### Current State

1. **CORS**: Currently set to `allow_origins=["*"]` - **INSECURE FOR PRODUCTION**
2. **API Key**: Alpha Vantage key stored in environment variable (good)
3. **Input Validation**: Pydantic models validate message structure (good)
4. **No Authentication**: WebSocket connections are not authenticated

### Recommendations

1. Restrict CORS to specific origins in production
2. Add WebSocket authentication (token-based)
3. Rate limit compute requests per client
4. Validate allocator configurations more strictly
5. Sanitize error messages to not expose internal details

---

## Performance Metrics

### Current Bundle Sizes

| Asset | Size | Notes |
|-------|------|-------|
| JavaScript | 769 KB | Could be reduced with code splitting |
| CSS | 50 KB | Includes Tailwind utilities |
| **Total** | ~829 KB | Target: <500 KB |

### Optimization Opportunities

1. **Code Splitting**: Lazy load modals and charts
2. **Tree Shaking**: Verify unused Recharts/Lucide components are removed
3. **CSS Purge**: Ensure Tailwind purges unused utilities
4. **Caching**: Implement service worker for static assets

---

## Testing Strategy

### Backend

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

**Test Categories:**
- Unit tests for allocators
- Integration tests for WebSocket handlers
- Performance tests for optimization algorithms

### Frontend

```bash
# Type check
npx tsc --noEmit

# Lint
npm run lint

# Build (validates compilation)
npm run build
```

**Recommended Additions:**
- Jest + React Testing Library for component tests
- Playwright for E2E tests
- Storybook for component documentation

---

## Deployment Considerations

### Backend

- Use Uvicorn with Gunicorn for production
- Set proper WebSocket timeouts
- Configure CORS for production domain
- Use Redis for session state (if scaling horizontally)

### Frontend

- Build with `npm run build`
- Serve static files from CDN
- Configure proper cache headers
- Enable gzip compression

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPHA_VANTAGE_API_KEY` | Yes | API key for price data |
| `WS_HOST` | No | WebSocket bind host (default: 0.0.0.0) |
| `WS_PORT` | No | WebSocket port (default: 8000) |
