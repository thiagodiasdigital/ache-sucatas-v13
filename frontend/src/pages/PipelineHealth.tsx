import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card"
import { Badge } from "../components/ui/badge"
import { Skeleton } from "../components/ui/skeleton"
import { AlertsBanner } from "../components/AlertsBanner"
import {
  useExecutions,
  useTopReasonCodes,
  usePipelineEvents,
  useHealthMetrics,
  type MinerExecution,
} from "../hooks/usePipelineHealth"

/**
 * Dashboard de Saude do Pipeline - Brief 3.3
 *
 * Exibe:
 * - Ultimas execucoes (run_id, timestamp, duracao)
 * - Total processados / validos / quarentena
 * - Top 10 reason_code
 * - Custo estimado
 */
export function PipelineHealthPage() {
  const { data: executions, isLoading: loadingExec } = useExecutions(10)
  const { data: topReasons, isLoading: loadingReasons } = useTopReasonCodes(10)
  const { data: events, isLoading: loadingEvents } = usePipelineEvents(15)
  const { data: metrics, isLoading: loadingMetrics } = useHealthMetrics()

  return (
    <div className="container py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pipeline Health Dashboard</h1>
          <p className="text-muted-foreground">
            Monitoramento interno do Miner V18
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          Auto-refresh: 30s
        </Badge>
      </div>

      {/* Alertas */}
      <AlertsBanner />

      {/* Metricas Principais */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Processados"
          value={metrics?.totalProcessados ?? 0}
          loading={loadingMetrics}
        />
        <MetricCard
          title="Validos"
          value={metrics?.totalValidos ?? 0}
          subtitle={`${metrics?.taxaValidosMedia.toFixed(1) ?? 0}% media`}
          loading={loadingMetrics}
          variant="success"
        />
        <MetricCard
          title="Quarentena"
          value={metrics?.totalQuarentena ?? 0}
          subtitle={`${metrics?.taxaQuarentenaMedia.toFixed(1) ?? 0}% media`}
          loading={loadingMetrics}
          variant={metrics?.taxaQuarentenaMedia && metrics.taxaQuarentenaMedia > 20 ? "danger" : "warning"}
        />
        <MetricCard
          title="Custo Estimado"
          value={`$${(metrics?.custoTotal ?? 0).toFixed(4)}`}
          subtitle="ultimas 30 exec"
          loading={loadingMetrics}
        />
      </div>

      {/* Grid de 2 colunas */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Ultimas Execucoes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Ultimas Execucoes</CardTitle>
            <CardDescription>Historico de runs do miner</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingExec ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {executions?.map((exec) => (
                  <ExecutionRow key={exec.id} execution={exec} />
                ))}
                {executions?.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    Nenhuma execucao encontrada
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Reason Codes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Reason Codes</CardTitle>
            <CardDescription>Motivos de quarentena (7 dias)</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingReasons ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {topReasons?.map((reason, idx) => (
                  <div
                    key={reason.reason_code}
                    className="flex items-center justify-between py-2 border-b last:border-0"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground text-sm w-6">
                        #{idx + 1}
                      </span>
                      <code className="text-sm bg-muted px-2 py-0.5 rounded">
                        {reason.reason_code}
                      </code>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{reason.total}</span>
                      <span className="text-muted-foreground text-sm">
                        ({reason.percentual}%)
                      </span>
                    </div>
                  </div>
                ))}
                {topReasons?.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    Nenhum erro nos ultimos 7 dias
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Eventos do Pipeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Eventos do Pipeline</CardTitle>
          <CardDescription>Log de observabilidade em tempo real</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingEvents ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {events?.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center gap-2 py-1.5 border-b last:border-0 text-sm"
                >
                  <Badge
                    variant={
                      event.nivel === "error"
                        ? "destructive"
                        : event.nivel === "warning"
                        ? "secondary"
                        : "outline"
                    }
                    className="text-xs w-16 justify-center"
                  >
                    {event.nivel}
                  </Badge>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded w-20 text-center">
                    {event.etapa}
                  </code>
                  <span className="text-muted-foreground truncate flex-1">
                    {event.mensagem || event.evento}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatTimeAgo(event.created_at)}
                  </span>
                </div>
              ))}
              {events?.length === 0 && (
                <p className="text-muted-foreground text-sm">
                  Nenhum evento registrado
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Card de metrica individual
 */
function MetricCard({
  title,
  value,
  subtitle,
  loading,
  variant = "default",
}: {
  title: string
  value: number | string
  subtitle?: string
  loading?: boolean
  variant?: "default" | "success" | "warning" | "danger"
}) {
  const variantStyles = {
    default: "border-border",
    success: "border-green-500/50 bg-green-500/5",
    warning: "border-yellow-500/50 bg-yellow-500/5",
    danger: "border-red-500/50 bg-red-500/5",
  }

  return (
    <Card className={variantStyles[variant]}>
      <CardContent className="pt-4">
        {loading ? (
          <>
            <Skeleton className="h-4 w-20 mb-2" />
            <Skeleton className="h-8 w-16" />
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Linha de execucao
 */
function ExecutionRow({ execution }: { execution: MinerExecution }) {
  const statusColors = {
    SUCCESS: "bg-green-500",
    RUNNING: "bg-blue-500 animate-pulse",
    FAILED: "bg-red-500",
  }

  const healthStatus =
    execution.taxa_quarentena_percent > 30
      ? "critical"
      : execution.taxa_quarentena_percent > 15
      ? "warning"
      : "healthy"

  const healthColors = {
    healthy: "text-green-600",
    warning: "text-yellow-600",
    critical: "text-red-600",
  }

  return (
    <div className="flex items-center gap-3 py-2 border-b last:border-0">
      {/* Status indicator */}
      <div
        className={`w-2 h-2 rounded-full ${
          statusColors[execution.status as keyof typeof statusColors] || "bg-gray-500"
        }`}
      />

      {/* Run ID */}
      <div className="flex-1 min-w-0">
        <code className="text-xs text-muted-foreground truncate block">
          {execution.run_id?.substring(0, 20) || "N/A"}...
        </code>
        <span className="text-xs text-muted-foreground">
          {formatTimeAgo(execution.inicio)}
        </span>
      </div>

      {/* Modo */}
      <Badge variant="outline" className="text-xs">
        {execution.modo_processamento}
      </Badge>

      {/* Metricas */}
      <div className="text-right text-sm">
        <span className={healthColors[healthStatus]}>
          {execution.taxa_validos_percent?.toFixed(0) || 0}%
        </span>
        <span className="text-muted-foreground"> validos</span>
      </div>

      {/* Duracao */}
      <span className="text-xs text-muted-foreground w-16 text-right">
        {execution.duracao_segundos
          ? `${execution.duracao_segundos.toFixed(1)}s`
          : "-"}
      </span>
    </div>
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
