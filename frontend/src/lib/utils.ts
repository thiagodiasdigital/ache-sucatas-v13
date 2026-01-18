import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Formata valor monetário para Real brasileiro
 */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) {
    return ""
  }
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value)
}

/**
 * Formata data para formato brasileiro
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return ""
  const date = new Date(dateString)
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date)
}

/**
 * Formata data e hora para formato brasileiro
 */
export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return ""
  const date = new Date(dateString)
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}
