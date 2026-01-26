import { useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { useAuth } from "../contexts/AuthContext"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card"
import { Search, LoaderCircle, Mail, CheckCircle2 } from "lucide-react"

export function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isSignUp, setIsSignUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [signUpSuccess, setSignUpSuccess] = useState(false)

  const { user, signIn, signUp } = useAuth()
  const navigate = useNavigate()

  // Se já está logado, redireciona para o dashboard
  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const { error } = isSignUp
        ? await signUp(email, password)
        : await signIn(email, password)

      if (error) {
        // Traduzir mensagens de erro comuns
        if (error.message.includes("Invalid login credentials")) {
          setError("Credenciais de login inválidas")
        } else if (error.message.includes("Email not confirmed")) {
          setError("Email não confirmado. Verifique sua caixa de entrada.")
        } else {
          setError(error.message)
        }
      } else if (isSignUp) {
        // Cadastro bem-sucedido - mostrar mensagem de confirmação
        setSignUpSuccess(true)
      } else {
        // Login bem-sucedido - redirecionar
        navigate("/dashboard")
      }
    } catch {
      setError("Ocorreu um erro. Tente novamente.")
    } finally {
      setLoading(false)
    }
  }

  // Tela de sucesso após cadastro
  if (signUpSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <div className="flex items-center justify-center h-16 w-16 rounded-full bg-green-100">
                <Mail className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <CardTitle className="text-2xl text-green-600">
              <CheckCircle2 className="inline-block h-6 w-6 mr-2" />
              Conta criada com sucesso!
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-blue-800 font-medium mb-2">
                Verifique seu email
              </p>
              <p className="text-blue-700 text-sm">
                Enviamos um link de confirmação para:
              </p>
              <p className="text-blue-900 font-semibold mt-1">{email}</p>
            </div>
            <p className="text-muted-foreground text-sm">
              Clique no link do email para ativar sua conta e depois faça login.
            </p>
            <p className="text-muted-foreground text-xs">
              Não recebeu? Verifique a pasta de spam ou lixo eletrônico.
            </p>
            <Button
              variant="outline"
              className="w-full mt-4"
              onClick={() => {
                setSignUpSuccess(false)
                setIsSignUp(false)
                setPassword("")
              }}
            >
              Voltar para o login
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {/* Logo */}
          <div className="flex justify-center mb-4">
            <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-primary">
              <Search className="h-6 w-6 text-primary-foreground" />
            </div>
          </div>
          <CardTitle className="text-2xl">Ache Sucatas</CardTitle>
          <CardDescription>
            {isSignUp
              ? "Crie sua conta para acessar a plataforma"
              : "Entre para acessar os leilões"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password">Senha</Label>
              <Input
                id="password"
                type="password"
                placeholder="********"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                disabled={loading}
              />
            </div>

            {/* Error message */}
            {error && (
              <div className="p-3 text-sm text-white bg-destructive rounded-md">
                {error}
              </div>
            )}

            {/* Submit */}
            <Button type="submit" className="w-full" disabled={loading}>
              <LoaderCircle
                className={`mr-2 h-4 w-4 animate-spin ${loading ? "opacity-100" : "opacity-0 w-0 mr-0"}`}
              />
              {isSignUp ? "Criar conta" : "Entrar"}
            </Button>

            {/* Toggle sign up / sign in */}
            <div className="text-center text-sm">
              {isSignUp ? (
                <p>
                  Já tem conta?{" "}
                  <button
                    type="button"
                    className="text-primary hover:underline"
                    onClick={() => setIsSignUp(false)}
                  >
                    Entrar
                  </button>
                </p>
              ) : (
                <p>
                  Não tem conta?{" "}
                  <button
                    type="button"
                    className="text-primary hover:underline"
                    onClick={() => setIsSignUp(true)}
                  >
                    Criar conta
                  </button>
                </p>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
