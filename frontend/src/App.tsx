import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider } from "./contexts/AuthContext"
import { NotificationProvider } from "./contexts/NotificationContext"
import { AuctionMapProvider } from "./contexts/AuctionMapContext"
import { ProtectedRoute } from "./components/ProtectedRoute"
import { Layout } from "./components/Layout"
import { LoginPage } from "./pages/Login"
import { DashboardPage } from "./pages/Dashboard"
import { PerfilPage } from "./pages/Perfil"
import { PipelineHealthPage } from "./pages/PipelineHealth"

// Criar cliente do React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <NotificationProvider>
            <Routes>
              {/* Rota pública */}
              <Route path="/login" element={<LoginPage />} />

              {/* Rotas protegidas */}
              <Route element={<ProtectedRoute />}>
                <Route
                  element={
                    <AuctionMapProvider>
                      <Layout />
                    </AuctionMapProvider>
                  }
                >
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/perfil" element={<PerfilPage />} />
                  <Route path="/pipeline-health" element={<PipelineHealthPage />} />
                </Route>
              </Route>

              {/* Redirecionar raiz para dashboard */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* 404 - Redirecionar para dashboard */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </NotificationProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
