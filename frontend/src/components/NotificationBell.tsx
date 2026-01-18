import { useState, useRef, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Bell, CheckCheck } from "lucide-react"
import { useNotifications } from "../hooks/useNotifications"
import { Button } from "./ui/button"
import { cn, formatDateTime } from "../lib/utils"

function getTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return "Agora"
  if (diffMins < 60) return `Há ${diffMins} min`
  if (diffHours < 24) return `Há ${diffHours}h`
  if (diffDays < 7) return `Há ${diffDays}d`
  return formatDateTime(dateString)
}

export function NotificationBell() {
  const { notifications, unreadCount, markAsRead, markAllAsRead, isLoading } =
    useNotifications()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [])

  const handleNotificationClick = async (notification: (typeof notifications)[0]) => {
    // Mark as read
    await markAsRead(notification.id)

    // Navigate to dashboard with filters applied
    const params = new URLSearchParams()
    if (notification.uf) {
      params.set("uf", notification.uf)
    }
    if (notification.cidade) {
      params.set("cidade", notification.cidade)
    }

    setIsOpen(false)
    navigate(`/dashboard?${params.toString()}`)
    setSearchParams(params)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <Button
        variant="ghost"
        size="sm"
        className="relative"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={`Notificações${unreadCount > 0 ? ` (${unreadCount} não lidas)` : ""}`}
      >
        <Bell className="h-5 w-5" />
        {/* Badge with count */}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-sucata text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </Button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border bg-popover p-0 shadow-lg z-50">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h3 className="font-semibold">Notificações</h3>
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-auto p-1 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => markAllAsRead()}
              >
                <CheckCheck className="h-4 w-4 mr-1" />
                Marcar todas
              </Button>
            )}
          </div>

          {/* Notifications List */}
          <div className="max-h-80 overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Carregando...
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Nenhuma notificação
              </div>
            ) : (
              <ul className="divide-y">
                {notifications.slice(0, 5).map((notification) => (
                  <li key={notification.id}>
                    <button
                      className={cn(
                        "w-full px-4 py-3 text-left hover:bg-accent/50 transition-colors",
                        "flex flex-col gap-1"
                      )}
                      onClick={() => handleNotificationClick(notification)}
                    >
                      {/* Title */}
                      <span className="text-sm font-medium line-clamp-1">
                        {notification.tags?.includes("SUCATA") ? (
                          <span className="text-sucata">Nova Sucata</span>
                        ) : (
                          "Novo Leilão"
                        )}{" "}
                        em {notification.cidade || notification.uf || "Brasil"}
                      </span>

                      {/* Description */}
                      <span className="text-xs text-muted-foreground line-clamp-1">
                        {notification.titulo || notification.orgao || "Ver detalhes"}
                      </span>

                      {/* Time */}
                      <span className="text-xs text-muted-foreground">
                        {getTimeAgo(notification.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="border-t px-4 py-2">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-sm"
                onClick={() => {
                  setIsOpen(false)
                  navigate("/dashboard")
                }}
              >
                Ver todos os leilões
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
