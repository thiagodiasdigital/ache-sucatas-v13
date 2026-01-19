import type { Auction } from "../types/database"
import { Card, CardContent, CardFooter, CardHeader } from "./ui/card"
import { Badge } from "./ui/badge"
import { buttonVariants } from "./ui/button"
import { formatCurrency, formatDateTime, cn } from "../lib/utils"
import { getPncpLinkFromId } from "../utils/pncp"
import { Calendar, MapPin, ExternalLink, Gavel } from "lucide-react"

interface AuctionCardProps {
  auction: Auction
}

/**
 * Determina a variante do badge baseado no nome da tag
 */
function getTagVariant(tag: string): "sucata" | "documentado" | "secondary" {
  const tagLower = tag.toLowerCase()
  if (tagLower.includes("sucata")) return "sucata"
  if (tagLower.includes("documentado")) return "documentado"
  return "secondary"
}

/**
 * Card de exibição de leilão.
 * Regras de Ouro:
 * - Tag SUCATA: Verde (#10B981)
 * - Tag DOCUMENTADO: Azul (#3B82F6)
 * - Valor inicial null/0: não renderiza
 */
export function AuctionCard({ auction }: AuctionCardProps) {
  const {
    titulo,
    orgao,
    uf,
    cidade,
    data_leilao,
    valor_estimado,
    tags,
    pncp_id,
    link_leiloeiro,
    nome_leiloeiro,
  } = auction

  // CORRECAO: Gerar link PNCP correto a partir do pncp_id
  // Formato correto: /CNPJ/ANO/SEQUENCIAL (nunca /CNPJ/1/SEQUENCIAL/ANO)
  const link_pncp = pncp_id ? getPncpLinkFromId(pncp_id) : null

  const showValue = valor_estimado !== null && valor_estimado > 0

  return (
    <Card className="flex flex-col h-full hover:shadow-lg transition-shadow">
      <CardHeader className="pb-2">
        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-2">
          {tags?.map((tag, index) => (
            <Badge key={index} variant={getTagVariant(tag)}>
              {tag.toUpperCase()}
            </Badge>
          ))}
        </div>

        {/* Título */}
        <h3 className="font-semibold text-base line-clamp-2 leading-tight">
          {titulo || "Sem título"}
        </h3>

        {/* Órgão */}
        <p className="text-sm text-muted-foreground line-clamp-1">{orgao}</p>
      </CardHeader>

      <CardContent className="flex-1 space-y-3">
        {/* Localização */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <MapPin className="h-4 w-4 shrink-0" />
          <span className="truncate">
            {cidade && uf ? `${cidade}, ${uf}` : uf || "Local não informado"}
          </span>
        </div>

        {/* Data do Leilão */}
        {data_leilao && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4 shrink-0" />
            <span>{formatDateTime(data_leilao)}</span>
          </div>
        )}

        {/* Leiloeiro */}
        {nome_leiloeiro && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Gavel className="h-4 w-4 shrink-0" />
            <span className="truncate">{nome_leiloeiro}</span>
          </div>
        )}

        {/* Valor Estimado - Só renderiza se > 0 */}
        {showValue && (
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              Valor Estimado
            </p>
            <p className="text-xl font-bold text-primary">
              {formatCurrency(valor_estimado)}
            </p>
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-2 gap-2">
        {/* Botão Ver Edital (PNCP) */}
        {link_pncp && (
          <a
            href={link_pncp}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex-1 gap-1")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Ver Edital
          </a>
        )}

        {/* Botão Dar Lance (Leiloeiro) */}
        {link_leiloeiro && (
          <a
            href={link_leiloeiro}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "default", size: "sm" }), "flex-1 gap-1")}
          >
            <Gavel className="h-3.5 w-3.5" />
            Dar Lance
          </a>
        )}
      </CardFooter>
    </Card>
  )
}
