import { ConnectionStatus } from '../types/websocket';

export interface WebSocketServiceConfig {
  url: string;
  onStatusChange: (status: ConnectionStatus) => void;
  onMessage: (message: any) => void;
  onError: (error: Event | Error) => void;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempts: number = 0;
  private readonly maxReconnectAttempts: number = 5;
  private reconnectTimeoutId: number | null = null;
  private isCleanClose: boolean = false;
  private isReconnecting: boolean = false;

  private readonly url: string;
  private readonly onStatusChange: (status: ConnectionStatus) => void;
  private readonly onMessage: (message: any) => void;
  private readonly onError: (error: Event | Error) => void;

  constructor(config: WebSocketServiceConfig) {
    this.url = config.url;
    this.onStatusChange = config.onStatusChange;
    this.onMessage = config.onMessage;
    this.onError = config.onError;
  }

  /**
   * Establish WebSocket connection
   */
  public connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // Clean up old WebSocket before creating new one
    if (this.ws) {
      this.clearEventHandlers();
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      this.setStatus('error');
      this.onError(error as Error);
    }
  }

  /**
   * Close WebSocket connection cleanly
   */
  public disconnect(): void {
    this.isCleanClose = true;
    this.clearReconnectTimeout();

    if (this.ws) {
      // Clear all event handlers before closing to prevent memory leaks
      this.clearEventHandlers();
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setStatus('disconnected');
    this.reconnectAttempts = 0;
  }

  /**
   * Get current connection status
   */
  public getStatus(): ConnectionStatus {
    return this.status;
  }

  /**
   * Send message through WebSocket
   */
  public send(message: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        const jsonMessage = JSON.stringify(message);
        this.ws.send(jsonMessage);
      } catch (error) {
        console.error('Failed to send message:', error);
        this.onError(error as Error);
      }
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }

  /**
   * Set up WebSocket event handlers
   */
  private setupEventHandlers(): void {
    if (!this.ws) return;

    // Clear any existing handlers first to prevent memory leaks on reconnect
    this.clearEventHandlers();

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
  }

  /**
   * Clear all WebSocket event handlers
   */
  private clearEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = null;
    this.ws.onclose = null;
    this.ws.onerror = null;
    this.ws.onmessage = null;
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    this.setStatus('connected');
    this.reconnectAttempts = 0;
    this.isCleanClose = false;
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    // Clean close (code 1000) or intentional disconnect
    if (event.code === 1000 || this.isCleanClose) {
      this.setStatus('disconnected');
      this.reconnectAttempts = 0;
      return;
    }

    // Unexpected close - attempt reconnection
    this.attemptReconnect();
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(event: Event): void {
    this.onError(event);

    // Trigger reconnection on error if not already reconnecting
    if (this.status !== 'reconnecting' && !this.isReconnecting) {
      this.attemptReconnect();
    }
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data);
      this.onMessage(message);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
      // Still call onMessage with raw data if JSON parsing fails
      this.onMessage(event.data);
    }
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    // Prevent concurrent reconnection attempts
    if (this.isReconnecting) {
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.setStatus('error');
      this.isReconnecting = false;
      console.error('Max reconnection attempts reached');
      return;
    }

    // Clear any existing reconnect timeout
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    // Ensure old WebSocket is properly closed before creating new one
    if (this.ws) {
      this.clearEventHandlers();
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.isReconnecting = true;
    this.setStatus('reconnecting');
    this.reconnectAttempts++;

    // Exponential backoff with jitter: min(1000 * 2^attempt, 30000) + random jitter
    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    const jitter = Math.random() * 1000; // 0-1000ms random jitter
    const delay = baseDelay + jitter;

    console.log(
      `Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimeoutId = window.setTimeout(() => {
      this.isReconnecting = false;
      this.connect();
    }, delay);
  }

  /**
   * Clear reconnection timeout
   */
  private clearReconnectTimeout(): void {
    if (this.reconnectTimeoutId !== null) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  /**
   * Update status and notify callback
   */
  private setStatus(status: ConnectionStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.onStatusChange(status);
    }
  }
}
