import { useAuth } from "../contexts/AuthContext"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { User, Mail, Calendar, LogOut } from "lucide-react"

/**
 * Página de perfil do usuário.
 */
export function PerfilPage() {
  const { user, signOut } = useAuth()

  const createdAt = user?.created_at
    ? new Date(user.created_at).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : "N/A"

  return (
    <div className="container py-8">
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                <User className="h-8 w-8 text-primary" />
              </div>
              <div>
                <CardTitle>Meu Perfil</CardTitle>
                <CardDescription>
                  Informações da sua conta no Ache Sucatas
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Email */}
            <div className="flex items-start gap-4 p-4 rounded-lg bg-muted/50">
              <Mail className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Email
                </p>
                <p className="text-base">{user?.email}</p>
              </div>
            </div>

            {/* Data de criação */}
            <div className="flex items-start gap-4 p-4 rounded-lg bg-muted/50">
              <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Membro desde
                </p>
                <p className="text-base">{createdAt}</p>
              </div>
            </div>

            {/* User ID */}
            <div className="flex items-start gap-4 p-4 rounded-lg bg-muted/50">
              <User className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  ID do Usuário
                </p>
                <p className="text-sm font-mono text-muted-foreground">
                  {user?.id}
                </p>
              </div>
            </div>

            {/* Sair */}
            <div className="pt-4 border-t">
              <Button
                variant="outline"
                onClick={() => signOut()}
                className="w-full gap-2"
              >
                <LogOut className="h-4 w-4" />
                Sair da conta
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
