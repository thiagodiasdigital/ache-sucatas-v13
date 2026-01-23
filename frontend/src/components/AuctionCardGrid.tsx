import type { Auction } from "../types/database"
import { Badge } from "./ui/badge"
import { formatCurrency, formatDate, cn } from "../lib/utils"
import { getPncpLinkFromId } from "../utils/pncp"
import { Calendar, MapPin, ExternalLink, FileText, Building2, Monitor, Package, Car, Cpu, Home, Hammer } from "lucide-react"

interface AuctionCardGridProps {
  auction: Auction
}

/**
 * Retorna o ícone apropriado baseado nas tags do leilão
 */
function getCategoryIcon(tags: string[] | null) {
  if (!tags || tags.length === 0) return Package

  const tagsLower = tags.map(t => t.toLowerCase()).join(' ')

  if (tagsLower.includes('veiculo') || tagsLower.includes('veículo') || tagsLower.includes('motocicleta')) return Car
  if (tagsLower.includes('eletronico') || tagsLower.includes('eletrônico')) return Cpu
  if (tagsLower.includes('imovel') || tagsLower.includes('imóvel')) return Home
  if (tagsLower.includes('sucata')) return Hammer

  return Package
}

/**
 * Determina a cor de fundo da área de categoria baseado na tag principal
 */
function getCategoryBgColor(tags: string[] | null): string {
  if (!tags || tags.length === 0) return "bg-slate-100"

  const tagsLower = tags.map(t => t.toLowerCase()).join(' ')

  if (tagsLower.includes('sucata')) return "bg-amber-50"
  if (tagsLower.includes('veiculo') || tagsLower.includes('veículo')) return "bg-blue-50"
  if (tagsLower.includes('eletronico') || tagsLower.includes('eletrônico')) return "bg-purple-50"
  if (tagsLower.includes('imovel') || tagsLower.includes('imóvel')) return "bg-emerald-50"

  return "bg-slate-50"
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
 * Card de Leilão - Design Mercado Livre
 *
 * Características:
 * - Área de destaque visual no topo (substitui foto)
 * - Alta densidade de dados
 * - Hierarquia: Título > Localização > Valor (menor destaque)
 * - Botões: VER PNCP e VER LEILOEIRO
 */
export function AuctionCardGrid({ auction }: AuctionCardGridProps) {
  const {
    titulo,
    orgao,
    uf,
    cidade,
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
  } = auction

  const isEncerrado = status_temporal === 'passado'
  const link_pncp = pncp_id ? getPncpLinkFromId(pncp_id) : null
  const showValue = valor_estimado !== null && valor_estimado > 0

  const CategoryIcon = getCategoryIcon(tags)
  const categoryBg = getCategoryBgColor(tags)

  return (
    <div className={cn(
      "bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-all duration-200 flex flex-col h-full",
      isEncerrado && "opacity-60"
    )}>
      {/* Área de Destaque Visual - Substitui a foto */}
      <div className={cn(
        "relative p-4 flex items-center justify-center min-h-[100px]",
        categoryBg
      )}>
        {/* Ícone central da categoria */}
        <CategoryIcon className="h-12 w-12 text-gray-400" strokeWidth={1.5} />

        {/* Badge ENCERRADO */}
        {isEncerrado && (
          <div className="absolute top-2 right-2">
            <Badge className="bg-gray-600 text-white text-[10px] px-2">
              ENCERRADO
            </Badge>
          </div>
        )}

        {/* Modalidade do leilão */}
        {modalidade_leilao && (
          <div className="absolute bottom-2 right-2">
            <Badge variant="outline" className="bg-white/90 text-[10px] gap-1">
              <Monitor className="h-3 w-3" />
              {modalidade_leilao}
            </Badge>
          </div>
        )}
      </div>

      {/* Badges de Categoria */}
      <div className="px-3 pt-3 pb-2">
        <div className="flex flex-wrap gap-1">
          {tags?.slice(0, 4).map((tag, index) => (
            <Badge
              key={index}
              variant={getTagVariant(tag)}
              className="text-[10px] px-2 py-0.5"
            >
              {tag.toUpperCase()}
            </Badge>
          ))}
        </div>
      </div>

      {/* Conteúdo Principal */}
      <div className="px-3 pb-3 flex-1 flex flex-col">
        {/* Título - Destaque Principal */}
        <h3 className="font-semibold text-sm text-gray-900 line-clamp-2 leading-snug mb-2">
          {titulo || objeto_resumido || "Leilão sem título"}
        </h3>

        {/* Órgão */}
        <div className="flex items-start gap-1.5 text-xs text-gray-500 mb-2">
          <Building2 className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span className="line-clamp-1">{orgao || "Órgão não informado"}</span>
        </div>

        {/* Localização */}
        <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span>{cidade && uf ? `${cidade}, ${uf}` : uf || "Local não informado"}</span>
        </div>

        {/* Data do Leilão */}
        <div className="flex items-center gap-1.5 text-xs mb-2">
          <Calendar className="h-3.5 w-3.5 shrink-0 text-blue-600" />
          <span className="text-gray-700 font-medium">
            {data_leilao ? formatDate(data_leilao) : "Data não informada"}
          </span>
        </div>

        {/* Data de Publicação */}
        {data_publicacao && (
          <div className="flex items-center gap-1.5 text-[11px] text-gray-400 mb-2">
            <FileText className="h-3 w-3 shrink-0" />
            <span>Publicado: {formatDate(data_publicacao)}</span>
          </div>
        )}

        {/* Descrição resumida */}
        {descricao && (
          <p className="text-[11px] text-gray-500 line-clamp-2 mb-3">
            {descricao}
          </p>
        )}

        {/* Espaçador flexível */}
        <div className="flex-1" />

        {/* Valor Estimado - MENOR destaque que título (estilo Meli) */}
        {showValue && (
          <div className="mb-3">
            <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-0.5">
              Valor Total dos Lotes
            </p>
            <p className="text-base font-semibold text-green-600">
              {formatCurrency(valor_estimado)}
            </p>
          </div>
        )}
      </div>

      {/* Botões de Ação - Estilo Meli */}
      <div className="px-3 pb-3 pt-2 border-t border-gray-100 flex gap-2">
        {/* Botão VER PNCP */}
        {link_pncp && (
          <a
            href={link_pncp}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            VER PNCP
          </a>
        )}

        {/* Botão VER LEILOEIRO */}
        {link_leiloeiro && link_leiloeiro !== 'N/D' && link_leiloeiro !== '' && !isEncerrado && (
          <a
            href={link_leiloeiro}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            VER LEILOEIRO
          </a>
        )}

        {/* Indicador de encerrado */}
        {isEncerrado && (
          <span className="flex-1 text-center text-xs text-gray-400 py-2">
            Leilão encerrado
          </span>
        )}
      </div>
    </div>
  )
}
