import { useState, useEffect } from "react"

/**
 * Hook SSR-safe para detectar se o viewport é mobile.
 * Usa matchMedia para reagir a mudanças de tamanho de tela.
 *
 * @param breakpoint - Largura máxima em pixels para considerar mobile (default: 768)
 * @returns true se a largura da tela for menor que o breakpoint
 *
 * @example
 * const isMobile = useIsMobile() // < 768px
 * const isTablet = useIsMobile(1024) // < 1024px
 */
export function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    // Verificar se window está disponível (SSR-safe)
    if (typeof window === "undefined") return

    const mediaQuery = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)

    // Set initial value
    setIsMobile(mediaQuery.matches)

    // Handler para mudanças
    const handler = (event: MediaQueryListEvent) => {
      setIsMobile(event.matches)
    }

    // Adicionar listener
    mediaQuery.addEventListener("change", handler)

    // Cleanup
    return () => {
      mediaQuery.removeEventListener("change", handler)
    }
  }, [breakpoint])

  return isMobile
}
