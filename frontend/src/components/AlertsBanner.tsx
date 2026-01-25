import { useState } from "react"
import { AlertTriangle, AlertCircle, Info, X, Check, Bell } from "lucide-react"
import { Card, CardContent } from "./ui/card"
import { Button } from "./ui/button"
import { Badge } from "./ui/badge"
import {
  useOpenAlerts,
  useAlertCounts,
  useAcknowledgeAlert,
  type PipelineAlert,
} from "../hooks/usePipelineHealth"
import { useQueryClient } from "@tanstack/react-query"

/**
 * Banner de Alertas do Pipeline
 *
 * Exibe alertas abertos com opções para reconhecer/resolver.
 * Cores por severidade:
 *   - critical: vermelho
 *   - warning: amarelo
 *   - info: azul
 */
export function AlertsBanner() {
  const { data: alerts, isLoading } = useOpenAlerts(5)
  const { data: counts } = useAlertCounts()
  const { acknowledge, resolve } = useAcknowledgeAlert()
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(true)

  // Sem alertas, não mostra nada
  if (!isLoading && (!alerts || alerts.length === 0)) {
    return null
  }

  const handleAcknowledge = async (alertId: number) => {
    try {
      await acknowledge(alertId)
      queryClient.invalidateQueries({ queryKey: ["pipeline-alerts-open"] })
      queryClient.invalidateQueries({ queryKey: ["pipeline-alerts-counts"] })
    } catch (error) {
      console.error("Erro ao reconhecer alerta:", error)
    }
  }

  const handleResolve = async (alertId: number) => {
    try {
      await resolve(alertId)
      queryClient.invalidateQueries({ queryKey: ["pipeline-alerts-open"] })
      queryClient.invalidateQueries({ queryKey: ["pipeline-alerts-counts"] })
    } catch (error) {
      console.error("Erro ao resolver alerta:", error)
    }
  }

  const severityConfig = {
    critical: {
      icon: AlertTriangle,
      bgClass: "bg-red-500/10 border-red-500/50",
      textClass: "text-red-600 dark:text-red-400",
      badgeClass: "bg-red-500 text-white",
    },
    warning: {
      icon: AlertCircle,
      bgClass: "bg-yellow-500/10 border-yellow-500/50",
      textClass: "text-yellow-600 dark:text-yellow-400",
      badgeClass: "bg-yellow-500 text-black",
    },
    info: {
      icon: Info,
      bgClass: "bg-blue-500/10 border-blue-500/50",
      textClass: "text-blue-600 dark:text-blue-400",
      badgeClass: "bg-blue-500 text-white",
    },
  }

  return (
    <div className="space-y-2">
      {/* Header com contagem */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4" />
          <span className="font-medium">Alertas</span>
          {counts && counts.total > 0 && (
            <div className="flex gap-1">
              {counts.critical > 0 && (
                <Badge className="bg-red-500 text-white text-xs">
                  {counts.critical}
                </Badge>
              )}
              {counts.warning > 0 && (
                <Badge className="bg-yellow-500 text-black text-xs">
                  {counts.warning}
                </Badge>
              )}
              {counts.info > 0 && (
                <Badge className="bg-blue-500 text-white text-xs">
                  {counts.info}
                </Badge>
              )}
            </div>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {expanded ? "Minimizar" : "Expandir"}
        </span>
      </div>

      {/* Lista de alertas */}
      {expanded && alerts && alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              config={severityConfig[alert.severidade]}
              onAcknowledge={() => handleAcknowledge(alert.id)}
              onResolve={() => handleResolve(alert.id)}
            />
          ))}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="text-sm text-muted-foreground">
          Carregando alertas...
        </div>
      )}
    </div>
  )
}

/**
 * Card individual de alerta
 */
function AlertCard({
  alert,
  config,
  onAcknowledge,
  onResolve,
}: {
  alert: PipelineAlert
  config: {
    icon: React.ElementType
    bgClass: string
    textClass: string
    badgeClass: string
  }
  onAcknowledge: () => void
  onResolve: () => void
}) {
  const Icon = config.icon
  const timeAgo = formatTimeAgo(alert.created_at)

  return (
    <Card className={`${config.bgClass} border`}>
      <CardContent className="py-3 px-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <Icon className={`h-5 w-5 mt-0.5 ${config.textClass}`} />

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge className={`${config.badgeClass} text-xs`}>
                {alert.severidade}
              </Badge>
              <span className="text-xs text-muted-foreground">{timeAgo}</span>
            </div>
            <p className={`font-medium text-sm ${config.textClass}`}>
              {alert.titulo}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {alert.mensagem}
            </p>
            {alert.run_id && (
              <code className="text-xs text-muted-foreground mt-1 block">
                Run: {alert.run_id.substring(0, 25)}...
              </code>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onAcknowledge}
              title="Reconhecer"
              className="h-8 w-8 p-0"
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onResolve}
              title="Resolver"
              className="h-8 w-8 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Formata tempo relativo
 */
function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return "agora"
  if (diffMins < 60) return `${diffMins}m atras`
  if (diffHours < 24) return `${diffHours}h atras`
  return `${diffDays}d atras`
}
