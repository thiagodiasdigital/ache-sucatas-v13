import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { useAvailableUFs, useCitiesByUF } from "../hooks/useAuctions"
import { Select } from "./ui/select"
import { Input } from "./ui/input"
import { Button } from "./ui/button"
import { Label } from "./ui/label"
import { Search, X, CalendarDays } from "lucide-react"

/**
 * Barra de filtros superior.
 * Usa URL Search Params como única fonte de verdade.
 * Inclui filtros de data por intervalo (data_publicacao e data_leilao).
 */
export function TopFilterBar() {
  const [searchParams, setSearchParams] = useSearchParams()

  const currentUF = searchParams.get("uf") || ""
  const currentCidade = searchParams.get("cidade") || ""
  const currentValorMin = searchParams.get("valor_min") || ""

  // Filtros de data da URL
  const urlDataPublicacaoDe = searchParams.get("data_publicacao_de") || ""
  const urlDataPublicacaoAte = searchParams.get("data_publicacao_ate") || ""
  const urlDataLeilaoDe = searchParams.get("data_leilao_de") || ""
  const urlDataLeilaoAte = searchParams.get("data_leilao_ate") || ""

  // Estado local para inputs de data (evita reload a cada tecla)
  const [localDataPublicacaoDe, setLocalDataPublicacaoDe] = useState(urlDataPublicacaoDe)
  const [localDataPublicacaoAte, setLocalDataPublicacaoAte] = useState(urlDataPublicacaoAte)
  const [localDataLeilaoDe, setLocalDataLeilaoDe] = useState(urlDataLeilaoDe)
  const [localDataLeilaoAte, setLocalDataLeilaoAte] = useState(urlDataLeilaoAte)

  // Sincronizar estado local quando URL mudar (ex: ao limpar filtros)
  useEffect(() => {
    setLocalDataPublicacaoDe(urlDataPublicacaoDe)
    setLocalDataPublicacaoAte(urlDataPublicacaoAte)
    setLocalDataLeilaoDe(urlDataLeilaoDe)
    setLocalDataLeilaoAte(urlDataLeilaoAte)
  }, [urlDataPublicacaoDe, urlDataPublicacaoAte, urlDataLeilaoDe, urlDataLeilaoAte])

  const { data: ufs, isLoading: loadingUFs } = useAvailableUFs()
  const { data: cidades, isLoading: loadingCidades } = useCitiesByUF(
    currentUF || undefined
  )

  const updateFilter = (key: string, value: string, additionalUpdates?: Record<string, string>) => {
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set(key, value)
    } else {
      newParams.delete(key)
    }
    // Aplicar atualizações adicionais (ex: limpar cidade ao mudar UF)
    if (additionalUpdates) {
      for (const [k, v] of Object.entries(additionalUpdates)) {
        if (v) {
          newParams.set(k, v)
        } else {
          newParams.delete(k)
        }
      }
    }
    // Reset página ao mudar filtros
    newParams.delete("page")
    setSearchParams(newParams)
  }

  const clearFilters = () => {
    setSearchParams(new URLSearchParams())
  }

  const hasFilters = currentUF || currentCidade || currentValorMin ||
    urlDataPublicacaoDe || urlDataPublicacaoAte ||
    urlDataLeilaoDe || urlDataLeilaoAte

  // Função para aplicar filtro de data (chamada no onBlur ou seleção de data válida)
  const applyDateFilter = (key: string, value: string) => {
    // Só aplica se a data for válida (formato YYYY-MM-DD) ou vazia
    if (value === "" || /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      updateFilter(key, value)
    }
  }

  // Handler para mudança de data - atualiza local e aplica se data válida
  const handleDateChange = (
    key: string,
    value: string,
    setLocal: (v: string) => void
  ) => {
    setLocal(value)
    // Se a data estiver no formato válido (usuário selecionou no picker), aplica imediatamente
    if (value === "" || /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      applyDateFilter(key, value)
    }
  }

  const ufOptions = [
    { value: "", label: "Todas as UFs" },
    ...(ufs?.map((uf) => ({
      value: uf.uf,
      label: `${uf.uf} (${uf.count})`,
    })) || []),
  ]

  const cidadeOptions = [
    { value: "", label: "Todas as cidades" },
    ...(cidades?.map((c) => ({
      value: c.cidade,
      label: `${c.cidade} (${c.count})`,
    })) || []),
  ]

  return (
    <div className="sticky top-0 z-10 bg-background border-b">
      <div className="container py-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Filtro UF */}
          <div className="flex flex-col gap-1.5 min-w-[150px]">
            <Label htmlFor="uf">Estado</Label>
            <Select
              id="uf"
              value={currentUF}
              onChange={(e) => {
                // Atualizar UF e limpar cidade em uma única operação
                updateFilter("uf", e.target.value, { cidade: "" })
              }}
              options={ufOptions}
              disabled={loadingUFs}
            />
          </div>

          {/* Filtro Cidade (dependente de UF) */}
          <div className="flex flex-col gap-1.5 min-w-[200px]">
            <Label htmlFor="cidade">Cidade</Label>
            <Select
              id="cidade"
              value={currentCidade}
              onChange={(e) => updateFilter("cidade", e.target.value)}
              options={cidadeOptions}
              disabled={!currentUF || loadingCidades}
            />
          </div>

          {/* Filtro Valor Mínimo */}
          <div className="flex flex-col gap-1.5 min-w-[150px]">
            <Label htmlFor="valor_min">Valor Mínimo (R$)</Label>
            <Input
              id="valor_min"
              type="number"
              placeholder="0"
              value={currentValorMin}
              onChange={(e) => updateFilter("valor_min", e.target.value)}
              min={0}
            />
          </div>

          {/* Separador visual */}
          <div className="hidden lg:block h-8 w-px bg-border" />

          {/* Filtro Data Publicação */}
          <div className="flex flex-col gap-1.5">
            <Label className="flex items-center gap-1">
              <CalendarDays className="h-3 w-3" />
              Data Publicação
            </Label>
            <div className="flex items-center gap-2">
              <Input
                type="date"
                value={localDataPublicacaoDe}
                onChange={(e) => handleDateChange("data_publicacao_de", e.target.value, setLocalDataPublicacaoDe)}
                onBlur={(e) => applyDateFilter("data_publicacao_de", e.target.value)}
                className="w-[140px]"
              />
              <span className="text-muted-foreground text-sm">até</span>
              <Input
                type="date"
                value={localDataPublicacaoAte}
                onChange={(e) => handleDateChange("data_publicacao_ate", e.target.value, setLocalDataPublicacaoAte)}
                onBlur={(e) => applyDateFilter("data_publicacao_ate", e.target.value)}
                className="w-[140px]"
              />
            </div>
          </div>

          {/* Filtro Data Leilão */}
          <div className="flex flex-col gap-1.5">
            <Label className="flex items-center gap-1">
              <CalendarDays className="h-3 w-3" />
              Data Leilão
            </Label>
            <div className="flex items-center gap-2">
              <Input
                type="date"
                value={localDataLeilaoDe}
                onChange={(e) => handleDateChange("data_leilao_de", e.target.value, setLocalDataLeilaoDe)}
                onBlur={(e) => applyDateFilter("data_leilao_de", e.target.value)}
                className="w-[140px]"
              />
              <span className="text-muted-foreground text-sm">até</span>
              <Input
                type="date"
                value={localDataLeilaoAte}
                onChange={(e) => handleDateChange("data_leilao_ate", e.target.value, setLocalDataLeilaoAte)}
                onBlur={(e) => applyDateFilter("data_leilao_ate", e.target.value)}
                className="w-[140px]"
              />
            </div>
          </div>

          {/* Botões de Ação */}
          <div className="flex items-center gap-2 ml-auto">
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="gap-2"
              >
                <X className="h-4 w-4" />
                Limpar
              </Button>
            )}
            <Button variant="default" size="sm" className="gap-2">
              <Search className="h-4 w-4" />
              Buscar
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
