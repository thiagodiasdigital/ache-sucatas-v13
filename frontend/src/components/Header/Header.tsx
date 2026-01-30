import { useState, useRef, useEffect } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useAuth } from "../../contexts/AuthContext"
import { useAvailableUFs, useCitiesByUF } from "../../hooks/useAuctions"
import { useIsMobile } from "../../hooks/useIsMobile"
import { NotificationBell } from "../NotificationBell"
import { MobileFilterSheet, MobileFilterButton } from "../MobileFilterSheet"
import { Search, User, LogOut, ChevronDown, X, Activity } from "lucide-react"
import { cn } from "../../lib/utils"

// Estados brasileiros para fallback
const ESTADOS_BR = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
  "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"
]

interface SearchableDropdownProps {
  id: string
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
  disabled?: boolean
  placeholder?: string
}

function SearchableDropdown({
  id,
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder = "Selecione..."
}: SearchableDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState("")
  const dropdownRef = useRef<HTMLDivElement>(null)

  const filteredOptions = options.filter(opt =>
    opt.label.toLowerCase().includes(search.toLowerCase())
  )

  const selectedOption = options.find(opt => opt.value === value)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearch("")
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        id={id}
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "header-select flex items-center justify-between gap-2 cursor-pointer",
          disabled && "opacity-50 cursor-not-allowed bg-gray-100"
        )}
        aria-label={label}
        aria-expanded={isOpen}
      >
        <span className="truncate text-gray-700">
          {selectedOption?.label || placeholder}
        </span>
        <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="p-2 border-b">
            <input
              type="text"
              placeholder={`Buscar ${label.toLowerCase()}...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded focus:outline-none focus:border-blue-500"
              autoFocus
            />
          </div>
          <ul className="max-h-60 overflow-auto py-1">
            {filteredOptions.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-500">Nenhum resultado</li>
            ) : (
              filteredOptions.map((opt) => (
                <li key={opt.value}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(opt.value)
                      setIsOpen(false)
                      setSearch("")
                    }}
                    className={cn(
                      "w-full px-3 py-2 text-left text-sm hover:bg-blue-50 transition-colors",
                      value === opt.value && "bg-blue-100 text-blue-700 font-medium"
                    )}
                  >
                    {opt.label}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

export function Header() {
  const { user, signOut } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const isMobile = useIsMobile()
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false)

  // Estados dos filtros da URL
  const currentUF = searchParams.get("uf") || ""
  const currentCidade = searchParams.get("cidade") || ""
  const currentBusca = searchParams.get("busca") || ""
  const currentValorMin = searchParams.get("valor_min") || ""
  const currentValorMax = searchParams.get("valor_max") || ""
  const currentTemporalidade = searchParams.get("temporalidade") || "futuros"

  // Filtros de data
  const urlDataPublicacaoDe = searchParams.get("data_publicacao_de") || ""
  const urlDataPublicacaoAte = searchParams.get("data_publicacao_ate") || ""
  const urlDataLeilaoDe = searchParams.get("data_leilao_de") || ""
  const urlDataLeilaoAte = searchParams.get("data_leilao_ate") || ""

  // Estado local para campos de input
  const [localBusca, setLocalBusca] = useState(currentBusca)
  const [localValorMin, setLocalValorMin] = useState(currentValorMin)
  const [localValorMax, setLocalValorMax] = useState(currentValorMax)
  const [localDataPublicacaoDe, setLocalDataPublicacaoDe] = useState(urlDataPublicacaoDe)
  const [localDataPublicacaoAte, setLocalDataPublicacaoAte] = useState(urlDataPublicacaoAte)
  const [localDataLeilaoDe, setLocalDataLeilaoDe] = useState(urlDataLeilaoDe)
  const [localDataLeilaoAte, setLocalDataLeilaoAte] = useState(urlDataLeilaoAte)

  // Hooks para buscar UFs e Cidades
  const { data: ufs, isLoading: loadingUFs } = useAvailableUFs()
  const { data: cidades, isLoading: loadingCidades } = useCitiesByUF(currentUF || undefined)

  // Sincronizar estado local quando URL mudar
  useEffect(() => {
    setLocalBusca(currentBusca)
    setLocalValorMin(currentValorMin)
    setLocalValorMax(currentValorMax)
    setLocalDataPublicacaoDe(urlDataPublicacaoDe)
    setLocalDataPublicacaoAte(urlDataPublicacaoAte)
    setLocalDataLeilaoDe(urlDataLeilaoDe)
    setLocalDataLeilaoAte(urlDataLeilaoAte)
  }, [currentBusca, currentValorMin, currentValorMax, urlDataPublicacaoDe, urlDataPublicacaoAte, urlDataLeilaoDe, urlDataLeilaoAte])

  // Função para atualizar filtros na URL
  const updateFilter = (key: string, value: string, additionalUpdates?: Record<string, string>) => {
    const newParams = new URLSearchParams(searchParams)
    if (value) {
      newParams.set(key, value)
    } else {
      newParams.delete(key)
    }
    if (additionalUpdates) {
      for (const [k, v] of Object.entries(additionalUpdates)) {
        if (v) {
          newParams.set(k, v)
        } else {
          newParams.delete(k)
        }
      }
    }
    newParams.delete("page")
    setSearchParams(newParams)
  }

  // Handler de busca
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    updateFilter("busca", localBusca)
  }

  // Limpar todos os filtros
  const clearFilters = () => {
    setSearchParams(new URLSearchParams())
    setLocalBusca("")
    setLocalValorMin("")
    setLocalValorMax("")
    setLocalDataPublicacaoDe("")
    setLocalDataPublicacaoAte("")
    setLocalDataLeilaoDe("")
    setLocalDataLeilaoAte("")
  }

  // Verificar se há filtros ativos
  const hasFilters = currentUF || currentCidade || currentBusca || currentValorMin || currentValorMax ||
    urlDataPublicacaoDe || urlDataPublicacaoAte || urlDataLeilaoDe || urlDataLeilaoAte

  // Contar filtros ativos (para badge do mobile)
  const activeFiltersCount = [
    currentValorMin,
    currentValorMax,
    urlDataPublicacaoDe,
    urlDataPublicacaoAte,
    urlDataLeilaoDe,
    urlDataLeilaoAte,
    currentTemporalidade !== "futuros" ? currentTemporalidade : "", // só conta se não for o default
  ].filter(Boolean).length

  // Callback para aplicar filtros do mobile sheet
  const handleMobileApplyFilters = (filters: {
    valor_min: string
    valor_max: string
    data_publicacao_de: string
    data_publicacao_ate: string
    data_leilao_de: string
    data_leilao_ate: string
    temporalidade: string
  }) => {
    const newParams = new URLSearchParams(searchParams)

    // Atualizar cada filtro
    const filterKeys = [
      "valor_min", "valor_max",
      "data_publicacao_de", "data_publicacao_ate",
      "data_leilao_de", "data_leilao_ate",
      "temporalidade"
    ] as const

    for (const key of filterKeys) {
      if (filters[key]) {
        newParams.set(key, filters[key])
      } else {
        newParams.delete(key)
      }
    }

    newParams.delete("page") // Reset pagination
    setSearchParams(newParams)
  }

  // Opções para dropdowns
  const ufOptions = [
    { value: "", label: "Todos os Estados" },
    ...(ufs?.map((uf) => ({
      value: uf.uf,
      label: `${uf.uf} (${uf.count})`,
    })) || ESTADOS_BR.map(uf => ({ value: uf, label: uf }))),
  ]

  const cidadeOptions = [
    { value: "", label: "Todas as Cidades" },
    ...(cidades?.map((c) => ({
      value: c.cidade,
      label: `${c.cidade} (${c.count})`,
    })) || []),
  ]

  // Extrair nome do usuário do email
  const userName = user?.email?.split("@")[0] || "Usuário"

  return (
    <header className="sticky top-0 z-50 overflow-x-hidden">
      {/* ========== LINHA 1 - TOP BAR ========== */}
      <div
        className="flex items-center justify-between px-3 md:px-5 gap-2 md:gap-4"
        style={{ backgroundColor: "#0C83D6", height: "60px" }}
      >
        {/* Logo + Nome (estilo Mercado Livre) */}
        <Link to="/dashboard" className="flex items-center gap-2 flex-shrink-0">
          <img
            src="/logotipo-ache-sucatas-leilao-sucatas.jpg"
            alt="Ache Sucatas"
            className="w-auto cursor-pointer"
            style={{
              height: '40px'
            }}
          />
          <div
            className="hidden sm:flex flex-col justify-center text-white"
            style={{ fontFamily: "'Bebas Neue', sans-serif", lineHeight: '1', height: '40px' }}
          >
            <span style={{ fontSize: '20px', letterSpacing: '0.18em' }}>
              ACHE
            </span>
            <span style={{ fontSize: '20px', letterSpacing: '0.01em' }}>
              SUCATAS
            </span>
          </div>
        </Link>

        {/* Search Container - DESKTOP ONLY */}
        {!isMobile && (
          <form onSubmit={handleSearch} className="flex-1 flex items-center max-w-3xl mx-4">
            <div className="flex items-stretch w-full">
              {/* Input de Busca */}
              <input
                type="text"
                placeholder="Buscar veículos, modelos, marcas..."
                value={localBusca}
                onChange={(e) => setLocalBusca(e.target.value)}
                className="header-search-input rounded-l"
              />

              {/* Dropdown Estado */}
              <SearchableDropdown
                id="header-estado"
                label="Estado"
                value={currentUF}
                options={ufOptions}
                onChange={(value) => updateFilter("uf", value, { cidade: "" })}
                placeholder="Estado"
                disabled={loadingUFs}
              />

              {/* Dropdown Cidade */}
              <SearchableDropdown
                id="header-cidade"
                label="Cidade"
                value={currentCidade}
                options={cidadeOptions}
                onChange={(value) => updateFilter("cidade", value)}
                placeholder="Cidade"
                disabled={!currentUF || loadingCidades}
              />

              {/* Botão de Busca */}
              <button
                type="submit"
                className="header-search-btn rounded-r"
                aria-label="Buscar"
              >
                <Search className="h-5 w-5" />
              </button>
            </div>
          </form>
        )}

        {/* User Actions */}
        <div className="flex items-center gap-3 md:gap-5 text-white flex-shrink-0">
          {/* Notification Bell */}
          <NotificationBell />

          {/* User Name - Desktop only */}
          <span className="text-sm font-medium hidden md:block">
            Olá, {userName}
          </span>

          {/* Pipeline Health (Admin) - Desktop only */}
          <Link
            to="/pipeline-health"
            className="hidden md:block p-1 hover:bg-white/10 rounded transition-colors"
            title="Pipeline Health"
          >
            <Activity className="h-5 w-5" />
          </Link>

          {/* Profile Icon */}
          <Link
            to="/perfil"
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-white/10 rounded transition-colors"
            title="Meu Perfil"
          >
            <User className="h-5 w-5" />
          </Link>

          {/* Logout Icon */}
          <button
            onClick={() => signOut()}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-white/10 rounded transition-colors"
            title="Sair"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* ========== LINHA 2 - FILTER BAR (Desktop) / FILTER BUTTON (Mobile) ========== */}
      <div
        className="flex flex-col md:flex-row items-stretch md:items-center justify-center gap-2 px-3 border-b border-gray-200"
        style={{ backgroundColor: "#E8F4FC", minHeight: "44px" }}
      >
        {/* Mobile: Busca + UF/Cidade + Filtros */}
        {isMobile && (
          <div className="flex flex-col gap-2 w-full py-2">
            {/* Linha 1: Campo de busca */}
            <form onSubmit={handleSearch} className="flex items-stretch w-full">
              <input
                type="text"
                placeholder="Buscar veículos, modelos..."
                value={localBusca}
                onChange={(e) => setLocalBusca(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-l-lg focus:outline-none focus:border-blue-500 min-h-[44px]"
              />
              <button
                type="submit"
                className="px-4 bg-blue-600 text-white rounded-r-lg min-h-[44px] min-w-[44px] flex items-center justify-center"
                aria-label="Buscar"
              >
                <Search className="h-5 w-5" />
              </button>
            </form>

            {/* Linha 2: UF + Cidade */}
            <div className="flex gap-2">
              <select
                value={currentUF}
                onChange={(e) => updateFilter("uf", e.target.value, { cidade: "" })}
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white min-h-[44px]"
                disabled={loadingUFs}
              >
                <option value="">Estado</option>
                {(ufs || ESTADOS_BR.map(uf => ({ uf, count: 0 }))).map((item) => (
                  <option key={typeof item === 'string' ? item : item.uf} value={typeof item === 'string' ? item : item.uf}>
                    {typeof item === 'string' ? item : `${item.uf} (${item.count})`}
                  </option>
                ))}
              </select>
              <select
                value={currentCidade}
                onChange={(e) => updateFilter("cidade", e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white min-h-[44px]"
                disabled={!currentUF || loadingCidades}
              >
                <option value="">Cidade</option>
                {cidades?.map((c) => (
                  <option key={c.cidade} value={c.cidade}>
                    {c.cidade} ({c.count})
                  </option>
                ))}
              </select>
            </div>

            {/* Linha 3: Botão de Filtros + Limpar */}
            <div className="flex items-center justify-between">
              <MobileFilterButton
                onClick={() => setMobileFilterOpen(true)}
                activeFiltersCount={activeFiltersCount}
              />
              {hasFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="flex items-center gap-1 px-3 py-2 text-xs text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors min-h-[44px]"
                >
                  <X className="h-4 w-4" />
                  Limpar
                </button>
              )}
            </div>
          </div>
        )}

        {/* Desktop: Filtros inline */}
        {!isMobile && (
          <>
        {/* Valor Mínimo */}
        <div className="flex items-center gap-1">
          <label htmlFor="valor_min" className="text-[11px] text-gray-600 whitespace-nowrap">
            Valor Mín.
          </label>
          <input
            id="valor_min"
            type="number"
            placeholder="R$ 0,00"
            value={localValorMin}
            onChange={(e) => setLocalValorMin(e.target.value)}
            onBlur={() => updateFilter("valor_min", localValorMin)}
            className="filter-input w-20 text-xs"
            min={0}
          />
        </div>

        {/* Valor Máximo */}
        <div className="flex items-center gap-1">
          <label htmlFor="valor_max" className="text-[11px] text-gray-600 whitespace-nowrap">
            Valor Máx.
          </label>
          <input
            id="valor_max"
            type="number"
            placeholder="R$ 999.999"
            value={localValorMax}
            onChange={(e) => setLocalValorMax(e.target.value)}
            onBlur={() => updateFilter("valor_max", localValorMax)}
            className="filter-input w-24 text-xs"
            min={0}
          />
        </div>

        {/* Separador */}
        <div className="h-5 w-px bg-gray-300" />

        {/* Data Publicação */}
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-gray-600">Publicação:</span>
          <input
            type="date"
            value={localDataPublicacaoDe}
            onChange={(e) => {
              setLocalDataPublicacaoDe(e.target.value)
              if (e.target.value.match(/^\d{4}-\d{2}-\d{2}$/)) {
                updateFilter("data_publicacao_de", e.target.value)
              }
            }}
            className="filter-input w-[115px] text-[11px]"
          />
          <span className="text-[11px] text-gray-400">-</span>
          <input
            type="date"
            value={localDataPublicacaoAte}
            onChange={(e) => {
              setLocalDataPublicacaoAte(e.target.value)
              if (e.target.value.match(/^\d{4}-\d{2}-\d{2}$/)) {
                updateFilter("data_publicacao_ate", e.target.value)
              }
            }}
            className="filter-input w-[115px] text-[11px]"
          />
        </div>

        {/* Separador */}
        <div className="h-5 w-px bg-gray-300" />

        {/* Data Leilão */}
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-gray-600">Leilão:</span>
          <input
            type="date"
            value={localDataLeilaoDe}
            onChange={(e) => {
              setLocalDataLeilaoDe(e.target.value)
              if (e.target.value.match(/^\d{4}-\d{2}-\d{2}$/)) {
                updateFilter("data_leilao_de", e.target.value)
              }
            }}
            className="filter-input w-[115px] text-[11px]"
          />
          <span className="text-[11px] text-gray-400">-</span>
          <input
            type="date"
            value={localDataLeilaoAte}
            onChange={(e) => {
              setLocalDataLeilaoAte(e.target.value)
              if (e.target.value.match(/^\d{4}-\d{2}-\d{2}$/)) {
                updateFilter("data_leilao_ate", e.target.value)
              }
            }}
            className="filter-input w-[115px] text-[11px]"
          />
        </div>

        {/* Separador */}
        <div className="h-5 w-px bg-gray-300" />

        {/* Filtro Exibir (Temporalidade) - Menu Suspenso */}
        <div className="flex items-center gap-1">
          <span className="text-[11px] text-gray-600">Exibir:</span>
          <select
            value={currentTemporalidade}
            onChange={(e) => updateFilter("temporalidade", e.target.value)}
            className="filter-select text-[11px]"
          >
            <option value="futuros">Próximos</option>
            <option value="passados">Encerrados</option>
            <option value="todos">Todos</option>
          </select>
        </div>

        {/* Botão Limpar Filtros (Desktop) */}
        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="ml-auto flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
          >
            <X className="h-3 w-3" />
            Limpar
          </button>
        )}
        </>
        )}
      </div>

      {/* Mobile Filter Sheet */}
      <MobileFilterSheet
        open={mobileFilterOpen}
        onOpenChange={setMobileFilterOpen}
        valorMin={currentValorMin}
        valorMax={currentValorMax}
        dataPublicacaoDe={urlDataPublicacaoDe}
        dataPublicacaoAte={urlDataPublicacaoAte}
        dataLeilaoDe={urlDataLeilaoDe}
        dataLeilaoAte={urlDataLeilaoAte}
        temporalidade={currentTemporalidade}
        onApplyFilters={handleMobileApplyFilters}
        onClearFilters={clearFilters}
        activeFiltersCount={activeFiltersCount}
      />
    </header>
  )
}
