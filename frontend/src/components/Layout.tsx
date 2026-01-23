import { Outlet } from "react-router-dom"
import { Header } from "./Header"

/**
 * Layout principal da aplicação.
 * Inclui header com navegação e área de conteúdo.
 */
export function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header com duas linhas (Top Bar + Filter Bar) */}
      <Header />

      {/* Main Content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t py-4">
        <div className="container text-center text-sm text-muted-foreground">
          <p>Ache Sucatas &copy; {new Date().getFullYear()} - DaaS Platform</p>
        </div>
      </footer>
    </div>
  )
}
