"use client"

import { useEffect, useRef, useCallback, useState } from "react"
import { useAppStore } from "@/lib/store"
import type { TimeSeriesPoint } from "@/lib/types"

// Типы сообщений WebSocket
interface MetricsMessage {
  type: "metrics"
  data: {
    test_id: string
    db_key: string
    db_type: string
    db_name?: string
    timestamp: string
    response_time: number
    tps: number
    throughput: number
    active_connections: number
    error_count: number
    cpu_usage: number
    memory_usage: number
    memory_usage_mb: number
    disk_iops: number
    network_in: number
    network_out: number
    cache_hit_ratio: number
    buffer_pool_hit_ratio: number
    lock_waits: number
    deadlocks: number
    progress: number
    elapsed_seconds: number
    remaining_seconds: number
  }
}

interface StatusMessage {
  type: "status"
  data: {
    test_id: string
    status: "pending" | "running" | "completed" | "failed"
    message?: string
    progress: number
  }
}

interface ConnectedMessage {
  type: "connected"
  test_id: string
  message: string
}

type WebSocketMessage = MetricsMessage | StatusMessage | ConnectedMessage | { type: "pong" }

interface UseTestWebSocketOptions {
  testId: string
  onMetrics?: (data: MetricsMessage["data"]) => void
  onStatus?: (data: StatusMessage["data"]) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  autoReconnect?: boolean
  reconnectInterval?: number
}

interface UseTestWebSocketReturn {
  isConnected: boolean
  progress: number
  status: string
  elapsedSeconds: number
  remainingSeconds: number
  connect: () => void
  disconnect: () => void
  sendMessage: (message: object) => void
}

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"

export function useTestWebSocket({
  testId,
  onMetrics,
  onStatus,
  onConnect,
  onDisconnect,
  onError,
  autoReconnect = true,
  reconnectInterval = 3000,
}: UseTestWebSocketOptions): UseTestWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  const [isConnected, setIsConnected] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string>("pending")
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [remainingSeconds, setRemainingSeconds] = useState(0)
  
  const { addRealtimeData, setCurrentTest, currentTest, updateConnectionDbType } = useAppStore()

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      
      switch (message.type) {
        case "metrics":
          const metricsData = message.data
          
          // Обновляем прогресс
          setProgress(metricsData.progress)
          setElapsedSeconds(metricsData.elapsed_seconds)
          setRemainingSeconds(metricsData.remaining_seconds)
          
          const point: TimeSeriesPoint = {
            timestamp: new Date(metricsData.timestamp).getTime(),
            responseTime: metricsData.response_time,
            throughput: metricsData.throughput,
            tps: metricsData.tps,
            activeConnections: metricsData.active_connections,
            errorCount: metricsData.error_count,
            cpuUsage: metricsData.cpu_usage,
            memoryUsage: metricsData.memory_usage,
            memoryUsageMB: metricsData.memory_usage_mb,
            diskIOps: metricsData.disk_iops,
            networkIn: metricsData.network_in,
            networkOut: metricsData.network_out,
            cacheHitRatio: metricsData.cache_hit_ratio,
            bufferPoolHitRatio: metricsData.buffer_pool_hit_ratio,
            lockWaits: metricsData.lock_waits,
            deadlocks: metricsData.deadlocks,
          }
          
          // Добавляем в store для отображения на графиках
          // Используем db_name если есть, иначе db_type
          const dbKey = metricsData.db_key || metricsData.db_name || metricsData.db_type
          addRealtimeData(dbKey, point)
          
          if (metricsData.db_key && metricsData.db_type) {
            updateConnectionDbType(metricsData.db_key, metricsData.db_type)
          }
          
          // Вызываем внешний callback
          onMetrics?.(metricsData)
          break
          
        case "status":
          const statusData = message.data
          setStatus(statusData.status)
          setProgress(statusData.progress)
          
          // Обновляем статус текущего теста
          if (currentTest && currentTest.id === statusData.test_id) {
            setCurrentTest({
              ...currentTest,
              status: statusData.status,
            })
          }
          
          onStatus?.(statusData)
          break
          
        case "connected":
          console.log(`[WS] Connected to test: ${message.test_id}`)
          break
          
        case "pong":
          // Ping-pong для поддержания соединения
          break
      }
    } catch (error) {
      console.error("[WS] Error parsing message:", error)
    }
  }, [addRealtimeData, currentTest, setCurrentTest, onMetrics, onStatus])

  const connect = useCallback(() => {
    // Не подключаемся если testId пустой или невалидный
    if (!testId || testId.trim() === "") {
      console.log("[WS] Skipping connection - no testId provided")
      return
    }
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }
    
    const wsUrl = `${WS_BASE_URL}/ws/test/${testId}`
    console.log(`[WS] Connecting to ${wsUrl}`)
    
    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      
      ws.onopen = () => {
        console.log("[WS] Connected")
        setIsConnected(true)
        onConnect?.()
        
        // Начинаем ping для поддержания соединения
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }))
          }
        }, 30000)
      }
      
      ws.onmessage = handleMessage
      
      ws.onerror = (error) => {
        console.warn("[WS] Connection error - server may not be available")
        onError?.(error)
      }
      
      ws.onclose = (event) => {
        console.log(`[WS] Disconnected (code: ${event.code})`)
        setIsConnected(false)
        onDisconnect?.()
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
        
        // Автопереподключение только если тест ещё выполняется
        if (autoReconnect && status === "running" && event.code !== 1000) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log("[WS] Attempting reconnection...")
            connect()
          }, reconnectInterval)
        }
      }
    } catch (err) {
      console.warn("[WS] Failed to create WebSocket:", err)
    }
  }, [testId, handleMessage, onConnect, onDisconnect, onError, autoReconnect, reconnectInterval, status])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    
    setIsConnected(false)
  }, [])

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  // Автоподключение при монтировании (только при изменении testId)
  useEffect(() => {
    // Подключаемся только если есть валидный testId
    if (testId && testId.trim() !== "") {
      connect()
    }
    
    return () => {
      disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testId]) // Намеренно не добавляем connect/disconnect чтобы избежать циклов

  return {
    isConnected,
    progress,
    status,
    elapsedSeconds,
    remainingSeconds,
    connect,
    disconnect,
    sendMessage,
  }
}

// Hook для глобального WebSocket (все тесты)
export function useGlobalWebSocket(options?: Omit<UseTestWebSocketOptions, "testId">) {
  return useTestWebSocket({
    testId: "global",
    ...options,
  })
}
