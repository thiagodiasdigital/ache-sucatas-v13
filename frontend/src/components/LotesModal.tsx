import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "./ui/drawer"
import { Badge } from "./ui/badge"
import { ScrollArea } from "./ui/scroll-area"
import { useLotes, formatLoteValor } from "../hooks/useLotes"
import { Car, Bike, Truck, Package, Hash, CreditCard, FileText } from "lucide-react"
import type { Lote } from "../types/database"

interface LotesModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  idInterno: string | null
  tituloEdital?: string
}

/**
 * Retorna o ícone apropriado baseado na categoria/descrição do lote
 */
function getLoteIcon(lote: Lote) {
  const descLower = (lote.descricao_completa || "").toLowerCase()
  const categoria = (lote.categoria_id || "").toLowerCase()

  if (categoria.includes("moto") || descLower.includes("motocicleta") || descLower.includes("moto")) {
    return <Bike className="h-5 w-5 text-orange-500" />
  }
  if (categoria.includes("caminhao") || descLower.includes("caminhão") || descLower.includes("caminhao")) {
    return <Truck className="h-5 w-5 text-blue-600" />
  }
  if (categoria.includes("veiculo") || descLower.includes("veículo") || descLower.includes("carro") || lote.placa) {
    return <Car className="h-5 w-5 text-green-600" />
  }

  return <Package className="h-5 w-5 text-gray-500" />
}

/**
 * Componente para exibir um lote individual
 */
function LoteItem({ lote, index }: { lote: Lote; index: number }) {
  const hasVeiculoInfo = lote.placa || lote.chassi || lote.marca || lote.modelo

  return (
    <div className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
      {/* Header do Lote */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          {getLoteIcon(lote)}
          <div>
            <h4 className="font-semibold text-sm text-gray-900">
              {lote.numero_lote || `Lote ${index + 1}`}
            </h4>
            {lote.categoria_id && (
              <Badge variant="secondary" className="text-[10px] mt-0.5">
                {lote.categoria_id}
              </Badge>
            )}
          </div>
        </div>

        {/* Valor */}
        {lote.avaliacao_valor && (
          <div className="text-right">
            <p className="text-[10px] text-gray-400 uppercase">Avaliação</p>
            <p className="font-semibold text-green-600 text-sm">
              {formatLoteValor(lote.avaliacao_valor)}
            </p>
          </div>
        )}
      </div>

      {/* Descrição */}
      <p className="text-sm text-gray-600 mb-3 line-clamp-2">
        {lote.descricao_completa || "Sem descrição"}
      </p>

      {/* Informações do Veículo (se disponível) */}
      {hasVeiculoInfo && (
        <div className="bg-gray-50 rounded-md p-3 space-y-2">
          {/* Marca/Modelo/Ano */}
          {(lote.marca || lote.modelo) && (
            <div className="flex items-center gap-2 text-xs">
              <Car className="h-3.5 w-3.5 text-gray-400" />
              <span className="font-medium text-gray-700">
                {[lote.marca, lote.modelo, lote.ano_fabricacao].filter(Boolean).join(" ")}
              </span>
            </div>
          )}

          {/* Placa */}
          {lote.placa && (
            <div className="flex items-center gap-2 text-xs">
              <Hash className="h-3.5 w-3.5 text-gray-400" />
              <span className="text-gray-600">Placa: <span className="font-mono font-medium">{lote.placa}</span></span>
            </div>
          )}

          {/* Chassi */}
          {lote.chassi && (
            <div className="flex items-center gap-2 text-xs">
              <FileText className="h-3.5 w-3.5 text-gray-400" />
              <span className="text-gray-600">Chassi: <span className="font-mono text-[11px]">{lote.chassi}</span></span>
            </div>
          )}

          {/* Renavam */}
          {lote.renavam && (
            <div className="flex items-center gap-2 text-xs">
              <CreditCard className="h-3.5 w-3.5 text-gray-400" />
              <span className="text-gray-600">Renavam: <span className="font-mono">{lote.renavam}</span></span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Modal/Drawer para exibir lista completa de lotes de um edital
 */
export function LotesModal({ open, onOpenChange, idInterno, tituloEdital }: LotesModalProps) {
  const { lotes, isLoading, error, totalLotes } = useLotes(idInterno)

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent side="right" className="w-full sm:max-w-lg">
        <DrawerHeader className="border-b pb-4">
          <DrawerTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Lotes do Edital
          </DrawerTitle>
          <DrawerDescription>
            {tituloEdital ? (
              <span className="line-clamp-1">{tituloEdital}</span>
            ) : (
              "Detalhes dos lotes disponíveis"
            )}
          </DrawerDescription>
          {totalLotes > 0 && (
            <Badge variant="secondary" className="w-fit mt-2">
              {totalLotes} {totalLotes === 1 ? "lote" : "lotes"} encontrados
            </Badge>
          )}
        </DrawerHeader>

        <ScrollArea className="flex-1 h-[calc(100vh-180px)]">
          <div className="p-4 space-y-3">
            {/* Loading */}
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
              </div>
            )}

            {/* Erro */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                <p className="text-red-600 text-sm">Erro ao carregar lotes</p>
                <p className="text-red-400 text-xs mt-1">{error.message}</p>
              </div>
            )}

            {/* Sem lotes */}
            {!isLoading && !error && lotes.length === 0 && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                <Package className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 font-medium">Sem lotes cadastrados</p>
                <p className="text-gray-400 text-sm mt-1">
                  Os lotes deste edital ainda não foram extraídos
                </p>
              </div>
            )}

            {/* Lista de Lotes */}
            {!isLoading && !error && lotes.length > 0 && (
              lotes.map((lote, index) => (
                <LoteItem key={lote.id} lote={lote} index={index} />
              ))
            )}
          </div>
        </ScrollArea>
      </DrawerContent>
    </Drawer>
  )
}
