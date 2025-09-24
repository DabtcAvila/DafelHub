'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './useAuth';

// Types
interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  user_id?: string;
  room?: string;
}

interface UseWebSocketOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
}

interface WebSocketState {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  lastMessage: WebSocketMessage | null;
  connectionAttempts: number;
}

interface RealTimeNotification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  data?: any;
}

interface RealTimeMetrics {
  activeUsers: number;
  systemLoad: number;
  memoryUsage: number;
  apiCalls: number;
  errorRate: number;
  responseTime: number;
  timestamp: Date;
}

interface RealTimeActivity {
  id: string;
  user_id: string;
  username: string;
  action: string;
  resource: string;
  timestamp: Date;
  details?: any;
}

// WebSocket configuration
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// Main WebSocket hook
export const useWebSocket = (
  endpoint: string,
  options: UseWebSocketOptions = {}
) => {
  const { user, isAuthenticated } = useAuth();
  const {
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    onOpen,
    onClose,
    onError,
    onMessage,
  } = options;

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const messageQueue = useRef<any[]>([]);

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    error: null,
    lastMessage: null,
    connectionAttempts: 0,
  });

  // Get authorization token
  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('dafelhub_access_token');
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!isAuthenticated || state.isConnecting || state.isConnected) {
      return;
    }

    setState(prev => ({ 
      ...prev, 
      isConnecting: true, 
      error: null 
    }));

    try {
      const token = getToken();
      const wsUrl = `${WS_BASE}${endpoint}${token ? `?token=${token}` : ''}`;
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        setState(prev => ({
          ...prev,
          isConnected: true,
          isConnecting: false,
          error: null,
          connectionAttempts: 0,
        }));

        // Send queued messages
        while (messageQueue.current.length > 0) {
          const message = messageQueue.current.shift();
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message));
          }
        }

        onOpen?.();
      };

      ws.current.onclose = () => {
        setState(prev => ({
          ...prev,
          isConnected: false,
          isConnecting: false,
        }));

        onClose?.();

        // Attempt reconnection
        if (state.connectionAttempts < reconnectAttempts) {
          setState(prev => ({
            ...prev,
            connectionAttempts: prev.connectionAttempts + 1,
          }));

          reconnectTimeoutRef.current = setTimeout(() => {
            if (isAuthenticated) {
              connect();
            }
          }, reconnectInterval);
        }
      };

      ws.current.onerror = (error) => {
        setState(prev => ({
          ...prev,
          isConnected: false,
          isConnecting: false,
          error: 'WebSocket connection error',
        }));

        onError?.(error);
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setState(prev => ({ ...prev, lastMessage: message }));
          onMessage?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

    } catch (error) {
      setState(prev => ({
        ...prev,
        isConnected: false,
        isConnecting: false,
        error: 'Failed to create WebSocket connection',
      }));
    }
  }, [endpoint, isAuthenticated, state.isConnecting, state.isConnected, state.connectionAttempts, reconnectAttempts, reconnectInterval, getToken, onOpen, onClose, onError, onMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setState({
      isConnected: false,
      isConnecting: false,
      error: null,
      lastMessage: null,
      connectionAttempts: 0,
    });
  }, []);

  // Send message
  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      // Queue message for when connection is established
      messageQueue.current.push(message);
    }
  }, []);

  // Subscribe to specific message types
  const subscribe = useCallback((messageType: string, handler: (data: any) => void) => {
    sendMessage({
      type: 'subscribe',
      channel: messageType,
      user_id: user?.user_id,
    });

    return () => {
      sendMessage({
        type: 'unsubscribe',
        channel: messageType,
        user_id: user?.user_id,
      });
    };
  }, [sendMessage, user]);

  // Auto-connect/disconnect based on authentication
  useEffect(() => {
    if (autoConnect && isAuthenticated && !state.isConnected && !state.isConnecting) {
      connect();
    } else if (!isAuthenticated && (state.isConnected || state.isConnecting)) {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, isAuthenticated, state.isConnected, state.isConnecting, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
    subscribe,
  };
};

// Hook for real-time notifications
export const useRealTimeNotifications = () => {
  const [notifications, setNotifications] = useState<RealTimeNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const { lastMessage, sendMessage, subscribe } = useWebSocket('/ws/notifications', {
    onMessage: (message) => {
      if (message.type === 'notification') {
        const notification: RealTimeNotification = {
          id: message.data.id || Date.now().toString(),
          type: message.data.type || 'info',
          title: message.data.title,
          message: message.data.message,
          timestamp: new Date(message.timestamp),
          read: false,
          data: message.data.data,
        };

        setNotifications(prev => [notification, ...prev]);
        setUnreadCount(prev => prev + 1);
      }
    },
  });

  // Mark notification as read
  const markAsRead = useCallback((notificationId: string) => {
    setNotifications(prev =>
      prev.map(notif =>
        notif.id === notificationId
          ? { ...notif, read: true }
          : notif
      )
    );

    setUnreadCount(prev => Math.max(0, prev - 1));

    sendMessage({
      type: 'mark_read',
      notification_id: notificationId,
    });
  }, [sendMessage]);

  // Mark all notifications as read
  const markAllAsRead = useCallback(() => {
    setNotifications(prev =>
      prev.map(notif => ({ ...notif, read: true }))
    );

    setUnreadCount(0);

    sendMessage({
      type: 'mark_all_read',
    });
  }, [sendMessage]);

  // Clear notification
  const clearNotification = useCallback((notificationId: string) => {
    setNotifications(prev => prev.filter(notif => notif.id !== notificationId));
    setUnreadCount(prev => {
      const notification = notifications.find(n => n.id === notificationId);
      return notification && !notification.read ? prev - 1 : prev;
    });
  }, [notifications]);

  // Clear all notifications
  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  return {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAllNotifications,
  };
};

// Hook for real-time metrics
export const useRealTimeMetrics = () => {
  const [metrics, setMetrics] = useState<RealTimeMetrics | null>(null);
  const [history, setHistory] = useState<RealTimeMetrics[]>([]);

  useWebSocket('/ws/metrics', {
    onMessage: (message) => {
      if (message.type === 'metrics_update') {
        const newMetrics: RealTimeMetrics = {
          activeUsers: message.data.activeUsers || 0,
          systemLoad: message.data.systemLoad || 0,
          memoryUsage: message.data.memoryUsage || 0,
          apiCalls: message.data.apiCalls || 0,
          errorRate: message.data.errorRate || 0,
          responseTime: message.data.responseTime || 0,
          timestamp: new Date(message.timestamp),
        };

        setMetrics(newMetrics);
        
        // Keep last 60 data points (for charts)
        setHistory(prev => {
          const newHistory = [...prev, newMetrics];
          return newHistory.slice(-60);
        });
      }
    },
  });

  return {
    metrics,
    history,
  };
};

// Hook for real-time activity feed
export const useRealTimeActivity = () => {
  const [activities, setActivities] = useState<RealTimeActivity[]>([]);

  useWebSocket('/ws/activity', {
    onMessage: (message) => {
      if (message.type === 'user_activity') {
        const activity: RealTimeActivity = {
          id: message.data.id || Date.now().toString(),
          user_id: message.data.user_id,
          username: message.data.username,
          action: message.data.action,
          resource: message.data.resource,
          timestamp: new Date(message.timestamp),
          details: message.data.details,
        };

        setActivities(prev => [activity, ...prev.slice(0, 99)]); // Keep last 100 activities
      }
    },
  });

  return {
    activities,
  };
};

// Hook for real-time user presence
export const useUserPresence = () => {
  const [onlineUsers, setOnlineUsers] = useState<string[]>([]);
  const { user } = useAuth();

  const { sendMessage } = useWebSocket('/ws/presence', {
    onMessage: (message) => {
      if (message.type === 'user_joined') {
        setOnlineUsers(prev => [...new Set([...prev, message.data.user_id])]);
      } else if (message.type === 'user_left') {
        setOnlineUsers(prev => prev.filter(userId => userId !== message.data.user_id));
      } else if (message.type === 'users_list') {
        setOnlineUsers(message.data.users || []);
      }
    },
  });

  // Update user status
  const updateStatus = useCallback((status: 'online' | 'away' | 'busy' | 'offline') => {
    sendMessage({
      type: 'status_update',
      status,
      user_id: user?.user_id,
    });
  }, [sendMessage, user]);

  return {
    onlineUsers,
    updateStatus,
    isUserOnline: (userId: string) => onlineUsers.includes(userId),
  };
};

export default useWebSocket;