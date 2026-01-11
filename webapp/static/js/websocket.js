/**
 * WebSocket client module for live game data streaming.
 * 
 * Design Pattern: Connection Manager Pattern + Observer Pattern
 * Algorithm: O(1) for connection operations, O(1) for message handling
 * Big O: 
 *   - Connection: O(1)
 *   - Message handling: O(1)
 *   - Reconnection: O(1) per attempt
 */

class WebSocketClient {
    /**
     * WebSocket client for live game data.
     * 
     * Manages connection lifecycle, reconnection, and message handling.
     */
    constructor(gameId) {
        this.gameId = gameId;
        this.websocket = null;
        this.status = 'disconnected'; // disconnected, connecting, connected, reconnecting, error
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.messageHandlers = [];
        this.errorHandlers = [];
        this.reconnectHandlers = [];
        this.lastMessageTime = null;
        this.intentionalDisconnect = false;
        this.reconnectTimer = null;
    }
    
    /**
     * Connect to WebSocket endpoint.
     */
    connect() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            console.log(`WebSocket already connected for game ${this.gameId}`);
            return;
        }
        
        this.intentionalDisconnect = false;
        this.status = 'connecting';
        this._emitStatusChange();
        
        // Build WebSocket URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/ws/live/${this.gameId}`;
        
        console.log(`Connecting to WebSocket: ${url}`);
        
        try {
            this.websocket = new WebSocket(url);
            
            this.websocket.onopen = (event) => {
                console.log(`WebSocket connected for game ${this.gameId}`);
                this.status = 'connected';
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000; // Reset delay
                this._emitStatusChange();
                this._emitReconnect();
            };
            
            this.websocket.onmessage = (event) => {
                this.lastMessageTime = Date.now();
                try {
                    const data = JSON.parse(event.data);
                    this._handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error, event.data);
                }
            };
            
            this.websocket.onerror = (error) => {
                console.error(`WebSocket error for game ${this.gameId}:`, error);
                this.status = 'error';
                this._emitStatusChange();
                this._emitError(new Error('WebSocket connection error'));
            };
            
            this.websocket.onclose = (event) => {
                console.log(`WebSocket closed for game ${this.gameId}:`, event.code, event.reason);
                this.status = 'disconnected';
                this._emitStatusChange();
                
                // Attempt reconnection if not intentional disconnect
                if (!this.intentionalDisconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this._attemptReconnect();
                }
            };
        } catch (error) {
            console.error(`Error creating WebSocket for game ${this.gameId}:`, error);
            this.status = 'error';
            this._emitStatusChange();
            this._emitError(error);
        }
    }
    
    /**
     * Disconnect from WebSocket.
     */
    disconnect() {
        this.intentionalDisconnect = true;
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        this.status = 'disconnected';
        this._emitStatusChange();
        console.log(`WebSocket disconnected for game ${this.gameId}`);
    }
    
    /**
     * Attempt to reconnect with exponential backoff.
     */
    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error(`Max reconnection attempts reached for game ${this.gameId}`);
            this.status = 'error';
            this._emitStatusChange();
            return;
        }
        
        this.reconnectAttempts++;
        this.status = 'reconnecting';
        this._emitStatusChange();
        
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);
        
        console.log(`Reconnecting to WebSocket for game ${this.gameId} (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`);
        
        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    /**
     * Handle incoming WebSocket message.
     */
    _handleMessage(data) {
        // Handle different message types
        if (data.type === 'connected') {
            console.log(`WebSocket connection confirmed for game ${this.gameId}`);
        } else if (data.type === 'data') {
            // Live data update
            this._emitMessage(data);
        } else if (data.type === 'error') {
            console.error(`WebSocket error message for game ${this.gameId}:`, data.message);
            this._emitError(new Error(data.message));
        } else if (data.type === 'ping') {
            // Respond to ping
            this.send({ type: 'pong' });
        } else if (data.type === 'pong') {
            // Pong received (connection health check)
            // No action needed
        } else {
            console.warn(`Unknown WebSocket message type for game ${this.gameId}:`, data.type);
        }
    }
    
    /**
     * Send message to WebSocket server.
     */
    send(data) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            try {
                this.websocket.send(JSON.stringify(data));
            } catch (error) {
                console.error(`Error sending WebSocket message for game ${this.gameId}:`, error);
            }
        } else {
            console.warn(`Cannot send message: WebSocket not connected for game ${this.gameId}`);
        }
    }
    
    /**
     * Register message handler callback.
     */
    onMessage(callback) {
        this.messageHandlers.push(callback);
    }
    
    /**
     * Register error handler callback.
     */
    onError(callback) {
        this.errorHandlers.push(callback);
    }
    
    /**
     * Register reconnection handler callback.
     */
    onReconnect(callback) {
        this.reconnectHandlers.push(callback);
    }
    
    /**
     * Remove all handlers.
     */
    removeAllHandlers() {
        this.messageHandlers = [];
        this.errorHandlers = [];
        this.reconnectHandlers = [];
    }
    
    /**
     * Emit message to handlers.
     */
    _emitMessage(data) {
        this.messageHandlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('Error in message handler:', error);
            }
        });
    }
    
    /**
     * Emit error to handlers.
     */
    _emitError(error) {
        this.errorHandlers.forEach(handler => {
            try {
                handler(error);
            } catch (err) {
                console.error('Error in error handler:', err);
            }
        });
    }
    
    /**
     * Emit reconnection event to handlers.
     */
    _emitReconnect() {
        this.reconnectHandlers.forEach(handler => {
            try {
                handler();
            } catch (error) {
                console.error('Error in reconnect handler:', error);
            }
        });
    }
    
    /**
     * Emit status change (for UI updates).
     */
    _emitStatusChange() {
        // Status changes are handled via getStatus() method
        // UI can poll or listen to status changes
    }
    
    /**
     * Get current connection status.
     */
    getStatus() {
        return this.status;
    }
    
    /**
     * Check if connected.
     */
    isConnected() {
        return this.status === 'connected' && 
               this.websocket && 
               this.websocket.readyState === WebSocket.OPEN;
    }
}

