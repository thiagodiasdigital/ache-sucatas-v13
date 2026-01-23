import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react"
import { supabase } from "../lib/supabase"
import { useAuth } from "./AuthContext"
import type { RealtimeChannel } from "@supabase/supabase-js"

// Flag to track if notification functions are available in the database
// Reset: functions were created in Supabase on 2026-01-23
let notificationFunctionsAvailable = true

export interface Notification {
  id: string
  auction_id: number
  filter_id: string | null
  filter_label: string | null
  created_at: string
  titulo: string | null
  orgao: string | null
  uf: string | null
  cidade: string | null
  valor_estimado: number | null
  tags: string[] | null
  data_leilao: string | null
}

interface NotificationContextType {
  notifications: Notification[]
  unreadCount: number
  isLoading: boolean
  markAsRead: (notificationId: string) => Promise<void>
  markAllAsRead: () => Promise<void>
  refetch: () => Promise<void>
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
)

interface NotificationProviderProps {
  children: ReactNode
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const { user } = useAuth()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [isLoading, setIsLoading] = useState(false)

  // Fetch unread notifications
  const fetchNotifications = useCallback(async () => {
    if (!user) {
      setNotifications([])
      setUnreadCount(0)
      return
    }

    // Skip if we already know functions are unavailable
    if (!notificationFunctionsAvailable) {
      return
    }

    setIsLoading(true)
    try {
      const { data, error } = await supabase.rpc(
        "get_unread_notifications" as never,
        { p_limit: 20 } as never
      )

      if (error) {
        // Disable notifications silently on any database error
        // Common errors: function not found, type mismatch, permission denied
        notificationFunctionsAvailable = false
        console.info("Notifications disabled:", error.message || "database error")
        return
      }

      setNotifications((data as Notification[]) || [])
      setUnreadCount((data as Notification[])?.length || 0)
    } catch (err) {
      console.error("Error fetching notifications:", err instanceof Error ? err.message : err)
    } finally {
      setIsLoading(false)
    }
  }, [user])

  // Mark single notification as read
  const markAsRead = useCallback(
    async (notificationId: string) => {
      if (!user || !notificationFunctionsAvailable) return

      try {
        await supabase.rpc("mark_notification_read" as never, {
          p_notification_id: notificationId,
        } as never)

        // Update local state
        setNotifications((prev) => prev.filter((n) => n.id !== notificationId))
        setUnreadCount((prev) => Math.max(0, prev - 1))
      } catch (err) {
        console.error("Error marking notification as read:", err instanceof Error ? err.message : err)
      }
    },
    [user]
  )

  // Mark all notifications as read
  const markAllAsRead = useCallback(async () => {
    if (!user || !notificationFunctionsAvailable) return

    try {
      await supabase.rpc("mark_all_notifications_read" as never)

      // Update local state
      setNotifications([])
      setUnreadCount(0)
    } catch (err) {
      console.error("Error marking all notifications as read:", err instanceof Error ? err.message : err)
    }
  }, [user])

  // Initial fetch on mount and user change
  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  // Subscribe to Realtime changes
  useEffect(() => {
    if (!user || !notificationFunctionsAvailable) return

    let channel: RealtimeChannel | null = null

    const setupRealtime = async () => {
      channel = supabase
        .channel("notifications-changes")
        .on(
          "postgres_changes",
          {
            event: "INSERT",
            schema: "pub",
            table: "notifications",
            filter: `user_id=eq.${user.id}`,
          },
          () => {
            // Refetch when new notification arrives
            fetchNotifications()
          }
        )
        .subscribe()
    }

    setupRealtime()

    return () => {
      if (channel) {
        supabase.removeChannel(channel)
      }
    }
  }, [user, fetchNotifications])

  const value = {
    notifications,
    unreadCount,
    isLoading,
    markAsRead,
    markAllAsRead,
    refetch: fetchNotifications,
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotifications() {
  const context = useContext(NotificationContext)
  if (context === undefined) {
    throw new Error(
      "useNotifications must be used within a NotificationProvider"
    )
  }
  return context
}
