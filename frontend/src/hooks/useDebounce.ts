import { useRef, useCallback, useEffect } from "react"

/**
 * Hook para debounce de funções.
 * Evita chamadas excessivas durante operações frequentes (ex: pan do mapa).
 *
 * @param callback Função a ser executada após o debounce
 * @param delay Tempo de espera em ms (default: 300ms)
 */
export function useDebounce<T extends (...args: never[]) => void>(
  callback: T,
  delay: number = 300
): T {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const callbackRef = useRef(callback)

  // Manter referência atualizada do callback
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  // Limpar timeout no unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  const debouncedCallback = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args)
      }, delay)
    },
    [delay]
  ) as T

  return debouncedCallback
}
