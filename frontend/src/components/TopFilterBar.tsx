import { useSearchParams } from "react-router-dom"
import { useAvailableUFs, useCitiesByUF } from "../hooks/useAuctions"
import { Select } from "./ui/select"
import { Input } from "./ui/input"
import { Button } from "./ui/button"
import { Label } from "./ui/label"
import { Search, X } from "lucide-react"

/**
 * Barra de filtros superior.
 * Usa URL Search Params como única fonte de verdade.
 */
export function TopFilterBar() {
  const [searchParams, setSearchParams] = useSearchParams()

  const currentUF = searchParams.get("uf") || ""
  const currentCidade = searchParams.get("cidade") || ""
  const currentValorMin = searchParams.get("valor_min") || ""

  const { data: ufs, isLoading: loadingUFs } = useAvailableUFs()
  const { data: cidades, isLoading: loadingCidades } = useCitiesByUF(
    currentUF || undefined
  )

  const updateFilter = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set(key, value)
    } else {
      newParams.delete(key)
    }
    // Reset página ao mudar filtros
    newParams.delete("page")
    setSearchParams(newParams)
  }

  const clearFilters = () => {
    setSearchParams(new URLSearchParams())
  }

  const hasFilters = currentUF || currentCidade || currentValorMin

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
                updateFilter("uf", e.target.value)
                // Limpar cidade quando mudar UF
                updateFilter("cidade", "")
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
