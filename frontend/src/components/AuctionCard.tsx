import type { Auction } from "../types/database"
import { Card, CardContent, CardFooter, CardHeader } from "./ui/card"
import { Badge } from "./ui/badge"
import { buttonVariants } from "./ui/button"
import { formatCurrency, formatDateTime, formatDate, cn } from "../lib/utils"
import { getEditalUrl } from "../utils/edital"
import { Calendar, MapPin, ExternalLink, Gavel, FileText, Hash, Building2, Monitor } from "lucide-react"

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
 * Card de exibição de leilão - VERSÃO COMPLETA COM 17 CAMPOS
 *
 * Campos exibidos:
 * 01- id_interno (referência)
 * 02- orgao
 * 03- uf
 * 04- cidade
 * 05- n_edital
 * 06- n_pncp (pncp_id)
 * 07- data_publicacao
 * 08- data_atualizacao (updated_at)
 * 09- data_leilao
 * 10- titulo
 * 11- descricao
 * 12- objeto_resumido
 * 13- tags
 * 14- link_edital (storage interno ou fallback)
 * 15- link_leiloeiro
 * 16- valor_estimado
 * 17- tipo_leilao (modalidade_leilao)
 */
export function AuctionCard({ auction }: AuctionCardProps) {
  const {
    id_interno,
    titulo,
    orgao,
    uf,
    cidade,
    n_edital,
    pncp_id,
    data_publicacao,
    data_leilao,
    descricao,
    objeto_resumido,
    valor_estimado,
    tags,
    link_leiloeiro,
    modalidade_leilao,
    status_temporal,
    storage_path,
    link_edital: auctionLinkEdital,
  } = auction

  const isEncerrado = status_temporal === 'passado'

  // Link do edital: prioriza storage interno > link_edital da view > fallback PNCP
  const link_edital = getEditalUrl(storage_path, pncp_id, auctionLinkEdital)

  const showValue = valor_estimado !== null && valor_estimado > 0

  return (
    <Card className={cn(
      "flex flex-col h-full hover:shadow-lg transition-shadow relative",
      isEncerrado && "opacity-70"
    )}>
      <CardHeader className="pb-2">
        {/* Badge ENCERRADO para leilões passados */}
        {isEncerrado && (
          <div className="absolute top-2 right-2">
            <Badge variant="secondary" className="bg-gray-500 text-white">
              ENCERRADO
            </Badge>
          </div>
        )}

        {/* Linha 1: Tags + Tipo de Leilão */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          {tags?.map((tag, index) => (
            <Badge key={index} variant={getTagVariant(tag)}>
              {tag.toUpperCase()}
            </Badge>
          ))}
          {modalidade_leilao && (
            <Badge variant="outline" className="gap-1">
              <Monitor className="h-3 w-3" />
              {modalidade_leilao}
            </Badge>
          )}
        </div>

        {/* Título */}
        <h3 className="font-semibold text-base line-clamp-2 leading-tight">
          {titulo || objeto_resumido || "Sem título"}
        </h3>

        {/* Órgão */}
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Building2 className="h-3.5 w-3.5 shrink-0" />
          <span className="line-clamp-1">{orgao || "Órgão não informado"}</span>
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-2 text-sm">
        {/* Localização: Cidade, UF */}
        <div className="flex items-center gap-2 text-muted-foreground">
          <MapPin className="h-4 w-4 shrink-0" />
          <span className="truncate">
            {cidade && uf ? `${cidade}, ${uf}` : uf || "Local não informado"}
          </span>
        </div>

        {/* Data do Leilão - DESTAQUE */}
        {data_leilao ? (
          <div className="flex items-center gap-2 text-foreground font-medium">
            <Calendar className="h-4 w-4 shrink-0 text-primary" />
            <span>Leilão: {formatDateTime(data_leilao)}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4 shrink-0" />
            <span className="italic">Data do leilão não informada</span>
          </div>
        )}

        {/* Data de Publicação */}
        {data_publicacao && (
          <div className="flex items-center gap-2 text-muted-foreground text-xs">
            <FileText className="h-3.5 w-3.5 shrink-0" />
            <span>Publicado: {formatDate(data_publicacao)}</span>
          </div>
        )}

        {/* Descrição - até 3 linhas */}
        {descricao && (
          <p className="text-muted-foreground line-clamp-3 text-xs leading-relaxed border-l-2 border-muted pl-2">
            {descricao}
          </p>
        )}

        {/* Objeto Resumido */}
        {objeto_resumido && (
          <div className="text-xs">
            <span className="font-medium">Itens: </span>
            <span className="text-muted-foreground">{objeto_resumido}</span>
          </div>
        )}

        {/* Valor Estimado - Destaque se existir */}
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

        {/* Referências: ID Interno, Nº Edital, PNCP */}
        <div className="pt-2 border-t space-y-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Hash className="h-3 w-3 shrink-0" />
            <span className="truncate" title={id_interno || undefined}>
              Ref: {id_interno || "N/A"}
            </span>
          </div>
          {n_edital && (
            <div className="flex items-center gap-1.5">
              <FileText className="h-3 w-3 shrink-0" />
              <span className="truncate">Edital: {n_edital}</span>
            </div>
          )}
        </div>
      </CardContent>

      <CardFooter className="pt-2 gap-2">
        {/* Botão Ver Edital - PDF interno ou fallback */}
        {link_edital && (
          <a
            href={link_edital}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex-1 gap-1")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Ver Edital
          </a>
        )}

        {/* Botão Dar Lance - só aparece se tem link válido E não está encerrado */}
        {link_leiloeiro && link_leiloeiro !== 'N/D' && link_leiloeiro !== '' && !isEncerrado && (
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

        {/* Indicador de leilão encerrado */}
        {isEncerrado && (
          <span className="flex-1 text-center text-sm text-muted-foreground py-2">
            Leilão encerrado
          </span>
        )}
      </CardFooter>
    </Card>
  )
}
