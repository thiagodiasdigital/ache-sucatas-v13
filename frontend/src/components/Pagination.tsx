import { useSearchParams } from "react-router-dom"
import { Button } from "./ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface PaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
}

/**
 * Componente de Paginação.
 * Controla navegação entre páginas usando URL Search Params.
 */
export function Pagination({ currentPage, totalPages, totalItems }: PaginationProps) {
  const [searchParams, setSearchParams] = useSearchParams()

  const goToPage = (page: number) => {
    const newParams = new URLSearchParams(searchParams)
    if (page === 1) {
      newParams.delete("page")
    } else {
      newParams.set("page", page.toString())
    }
    setSearchParams(newParams)
  }

  const goToPrevious = () => {
    if (currentPage > 1) {
      goToPage(currentPage - 1)
    }
  }

  const goToNext = () => {
    if (currentPage < totalPages) {
      goToPage(currentPage + 1)
    }
  }

  // Não exibir se não houver páginas
  if (totalPages <= 1) {
    return (
      <div className="flex justify-center py-4">
        <span className="text-sm text-muted-foreground">
          {totalItems} registro{totalItems !== 1 ? "s" : ""} encontrado{totalItems !== 1 ? "s" : ""}
        </span>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between py-4 border-t">
      {/* Info de registros */}
      <span className="text-sm text-muted-foreground">
        {totalItems} registro{totalItems !== 1 ? "s" : ""} encontrado{totalItems !== 1 ? "s" : ""}
      </span>

      {/* Controles de navegação */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={goToPrevious}
          disabled={currentPage <= 1}
          className="gap-1"
        >
          <ChevronLeft className="h-4 w-4" />
          Anterior
        </Button>

        <span className="text-sm font-medium px-4">
          Página {currentPage} de {totalPages}
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={goToNext}
          disabled={currentPage >= totalPages}
          className="gap-1"
        >
          Próxima
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
