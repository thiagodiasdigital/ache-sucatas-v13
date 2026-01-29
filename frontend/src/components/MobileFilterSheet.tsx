import { useState, useEffect } from "react"
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerFooter,
} from "./ui/drawer"
import { Filter, X, Calendar, DollarSign, Clock } from "lucide-react"

interface MobileFilterSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  // Valores atuais dos filtros
  valorMin: string
  valorMax: string
  dataPublicacaoDe: string
  dataPublicacaoAte: string
  dataLeilaoDe: string
  dataLeilaoAte: string
  temporalidade: string
  // Callbacks
  onApplyFilters: (filters: {
    valor_min: string
    valor_max: string
    data_publicacao_de: string
    data_publicacao_ate: string
    data_leilao_de: string
    data_leilao_ate: string
    temporalidade: string
  }) => void
  onClearFilters: () => void
  // Contagem de filtros ativos
  activeFiltersCount: number
}

/**
 * Bottom sheet de filtros para mobile.
 * Reutiliza a mesma lógica de filtros do Header desktop.
 */
export function MobileFilterSheet({
  open,
  onOpenChange,
  valorMin,
  valorMax,
  dataPublicacaoDe,
  dataPublicacaoAte,
  dataLeilaoDe,
  dataLeilaoAte,
  temporalidade,
  onApplyFilters,
  onClearFilters,
  activeFiltersCount,
}: MobileFilterSheetProps) {
  // Estado local para edição (só aplica ao clicar em Aplicar)
  const [localValorMin, setLocalValorMin] = useState(valorMin)
  const [localValorMax, setLocalValorMax] = useState(valorMax)
  const [localDataPublicacaoDe, setLocalDataPublicacaoDe] = useState(dataPublicacaoDe)
  const [localDataPublicacaoAte, setLocalDataPublicacaoAte] = useState(dataPublicacaoAte)
  const [localDataLeilaoDe, setLocalDataLeilaoDe] = useState(dataLeilaoDe)
  const [localDataLeilaoAte, setLocalDataLeilaoAte] = useState(dataLeilaoAte)
  const [localTemporalidade, setLocalTemporalidade] = useState(temporalidade)

  // Sincronizar estado local quando props mudarem
  useEffect(() => {
    setLocalValorMin(valorMin)
    setLocalValorMax(valorMax)
    setLocalDataPublicacaoDe(dataPublicacaoDe)
    setLocalDataPublicacaoAte(dataPublicacaoAte)
    setLocalDataLeilaoDe(dataLeilaoDe)
    setLocalDataLeilaoAte(dataLeilaoAte)
    setLocalTemporalidade(temporalidade)
  }, [valorMin, valorMax, dataPublicacaoDe, dataPublicacaoAte, dataLeilaoDe, dataLeilaoAte, temporalidade])

  const handleApply = () => {
    onApplyFilters({
      valor_min: localValorMin,
      valor_max: localValorMax,
      data_publicacao_de: localDataPublicacaoDe,
      data_publicacao_ate: localDataPublicacaoAte,
      data_leilao_de: localDataLeilaoDe,
      data_leilao_ate: localDataLeilaoAte,
      temporalidade: localTemporalidade,
    })
    onOpenChange(false)
  }

  const handleClear = () => {
    setLocalValorMin("")
    setLocalValorMax("")
    setLocalDataPublicacaoDe("")
    setLocalDataPublicacaoAte("")
    setLocalDataLeilaoDe("")
    setLocalDataLeilaoAte("")
    setLocalTemporalidade("futuros")
    onClearFilters()
    onOpenChange(false)
  }

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent side="bottom" className="max-h-[85vh]">
        <DrawerHeader className="border-b pb-4">
          <DrawerTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filtros
            {activeFiltersCount > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
                {activeFiltersCount} ativo{activeFiltersCount > 1 ? "s" : ""}
              </span>
            )}
          </DrawerTitle>
        </DrawerHeader>

        <div className="p-4 space-y-6 overflow-y-auto">
          {/* Seção: Valor */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <DollarSign className="h-4 w-4" />
              Faixa de Valor
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="mobile-valor-min" className="block text-xs text-gray-500 mb-1">
                  Valor Mínimo
                </label>
                <input
                  id="mobile-valor-min"
                  type="number"
                  placeholder="R$ 0"
                  value={localValorMin}
                  onChange={(e) => setLocalValorMin(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  min={0}
                />
              </div>
              <div>
                <label htmlFor="mobile-valor-max" className="block text-xs text-gray-500 mb-1">
                  Valor Máximo
                </label>
                <input
                  id="mobile-valor-max"
                  type="number"
                  placeholder="R$ 999.999"
                  value={localValorMax}
                  onChange={(e) => setLocalValorMax(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  min={0}
                />
              </div>
            </div>
          </div>

          {/* Seção: Data de Publicação */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <Calendar className="h-4 w-4" />
              Data de Publicação
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="mobile-pub-de" className="block text-xs text-gray-500 mb-1">
                  De
                </label>
                <input
                  id="mobile-pub-de"
                  type="date"
                  value={localDataPublicacaoDe}
                  onChange={(e) => setLocalDataPublicacaoDe(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label htmlFor="mobile-pub-ate" className="block text-xs text-gray-500 mb-1">
                  Até
                </label>
                <input
                  id="mobile-pub-ate"
                  type="date"
                  value={localDataPublicacaoAte}
                  onChange={(e) => setLocalDataPublicacaoAte(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Seção: Data do Leilão */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <Calendar className="h-4 w-4" />
              Data do Leilão
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="mobile-leilao-de" className="block text-xs text-gray-500 mb-1">
                  De
                </label>
                <input
                  id="mobile-leilao-de"
                  type="date"
                  value={localDataLeilaoDe}
                  onChange={(e) => setLocalDataLeilaoDe(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label htmlFor="mobile-leilao-ate" className="block text-xs text-gray-500 mb-1">
                  Até
                </label>
                <input
                  id="mobile-leilao-ate"
                  type="date"
                  value={localDataLeilaoAte}
                  onChange={(e) => setLocalDataLeilaoAte(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Seção: Temporalidade */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <Clock className="h-4 w-4" />
              Exibir Leilões
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "futuros", label: "Próximos" },
                { value: "passados", label: "Encerrados" },
                { value: "todos", label: "Todos" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setLocalTemporalidade(option.value)}
                  className={`px-3 py-2.5 text-sm font-medium rounded-lg border transition-colors ${
                    localTemporalidade === option.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <DrawerFooter className="border-t pt-4 flex-row gap-3">
          <button
            type="button"
            onClick={handleClear}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors min-h-[44px]"
          >
            <X className="h-4 w-4" />
            Limpar
          </button>
          <button
            type="button"
            onClick={handleApply}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors min-h-[44px]"
          >
            <Filter className="h-4 w-4" />
            Aplicar
          </button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}

/**
 * Botão para abrir o MobileFilterSheet.
 * Mostra contador de filtros ativos.
 */
interface MobileFilterButtonProps {
  onClick: () => void
  activeFiltersCount: number
}

export function MobileFilterButton({ onClick, activeFiltersCount }: MobileFilterButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors min-h-[44px]"
    >
      <Filter className="h-4 w-4" />
      <span>Filtros</span>
      {activeFiltersCount > 0 && (
        <span className="px-1.5 py-0.5 text-xs font-medium bg-blue-600 text-white rounded-full min-w-[20px] text-center">
          {activeFiltersCount}
        </span>
      )}
    </button>
  )
}
