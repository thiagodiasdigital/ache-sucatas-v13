import { useState } from "react"
import type { Auction } from "../types/database"
import { Badge } from "./ui/badge"
import { formatDate, cn } from "../lib/utils"
import { getPncpLinkFromId } from "../utils/pncp"
import { Calendar, MapPin, ExternalLink, FileText, Building2, Monitor, Hash, Eye, Package } from "lucide-react"
import { useLotes, getLotesPreview } from "../hooks/useLotes"
import { LotesModal } from "./LotesModal"

interface AuctionCardGridProps {
  auction: Auction
}

/**
 * Retorna a imagem apropriada baseada nas tags do leilão
 */
function getCategoryImage(tags: string[] | null): string {
  if (!tags || tags.length === 0) return "/patio_ache_sucatas.png"

  const tagsLower = tags.map(t => t.toLowerCase()).join(' ')

  // Motocicleta tem prioridade sobre veículo (é mais específico)
  if (tagsLower.includes('motocicleta')) return "/motocicleta.png"
  if (tagsLower.includes('veiculo') || tagsLower.includes('veículo')) return "/veiculo.png"
  if (tagsLower.includes('eletronico') || tagsLower.includes('eletrônico')) return "/eletronico.jpg"
  if (tagsLower.includes('imovel') || tagsLower.includes('imóvel')) return "/imovel.jpeg"
  if (tagsLower.includes('sucata')) return "/sucata.png"

  return "/patio_ache_sucatas.png"
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
    id_interno,
    titulo,
    orgao,
    uf,
    cidade,
    pncp_id,
    data_publicacao,
    data_leilao,
    descricao,
    objeto_resumido,
    tags,
    link_leiloeiro,
    modalidade_leilao,
    status_temporal,
  } = auction

  // Estado para controlar o modal de lotes
  const [showLotesModal, setShowLotesModal] = useState(false)

  const isEncerrado = status_temporal === 'passado'
  const link_pncp = pncp_id ? getPncpLinkFromId(pncp_id) : null
  const categoryImage = getCategoryImage(tags)

  // Buscar lotes do edital (usando id_interno - campo único compartilhado)
  const { lotes, isLoading: isLoadingLotes, totalLotes } = useLotes(auction.id_interno)
  const lotesPreview = getLotesPreview(lotes, 80)

  return (
    <div className={cn(
      "bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-all duration-200 flex flex-col h-full",
      isEncerrado && "opacity-60"
    )}>
      {/* Área de Destaque Visual - Imagem da categoria */}
      <div className="relative aspect-[4/1] overflow-hidden bg-gray-100">
        {/* Imagem baseada na categoria do leilão - lazy loaded */}
        <img
          src={categoryImage}
          alt="Imagem do leilão"
          loading="lazy"
          decoding="async"
          className="w-full h-full object-cover"
        />

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
      <div className="px-3 pt-2 pb-1.5">
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
      <div className="px-3 pb-2 flex-1 flex flex-col">
        {/* Título - Destaque Principal */}
        <h3 className="font-semibold text-sm text-gray-900 line-clamp-2 leading-snug mb-1.5">
          {titulo || objeto_resumido || "Leilão sem título"}
        </h3>

        {/* Órgão */}
        <div className="flex items-start gap-1.5 text-xs text-gray-500 mb-1.5">
          <Building2 className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span className="line-clamp-1">{orgao || "Órgão não informado"}</span>
        </div>

        {/* Localização */}
        <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1.5">
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          <span>{cidade && uf ? `${cidade}, ${uf}` : uf || "Local não informado"}</span>
        </div>

        {/* Data do Leilão */}
        <div className="flex items-center gap-1.5 text-xs mb-1.5">
          <Calendar className="h-3.5 w-3.5 shrink-0 text-blue-600" />
          <span className="text-gray-700 font-medium">
            {data_leilao ? formatDate(data_leilao) : "Data não informada"}
          </span>
        </div>

        {/* Data de Publicação */}
        {data_publicacao && (
          <div className="flex items-center gap-1.5 text-[11px] text-gray-400 mb-1.5">
            <FileText className="h-3 w-3 shrink-0" />
            <span>Publicado: {formatDate(data_publicacao)}</span>
          </div>
        )}

        {/* Descrição resumida */}
        {descricao && (
          <p className="text-[11px] text-gray-500 line-clamp-2 mb-1.5">
            {descricao}
          </p>
        )}

        {/* Espaçador flexível */}
        <div className="flex-1" />

        {/* Seção de Lotes */}
        <div className="mb-2 border-t border-gray-100 pt-2">
          <div className="flex items-center gap-1.5 mb-1">
            <Package className="h-3.5 w-3.5 text-gray-400" />
            <p className="text-[10px] text-gray-400 uppercase tracking-wide">
              Lotes {totalLotes > 0 && `(${totalLotes})`}
            </p>
          </div>
          <p className="text-[11px] text-gray-600 line-clamp-1">
            {isLoadingLotes ? "Carregando..." : lotesPreview}
          </p>
        </div>

        {/* Botão VER DETALHES */}
        <button
          onClick={() => setShowLotesModal(true)}
          className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors mb-2"
        >
          <Eye className="h-3.5 w-3.5" />
          VER DETALHES
        </button>
      </div>

      {/* Botões de Ação - Estilo Meli */}
      <div className="px-3 pb-1.5 pt-1.5 border-t border-gray-100 flex gap-2">
        {/* Botão VER PNCP */}
        {link_pncp && (
          <a
            href={link_pncp}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
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
            className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            VER LEILOEIRO
          </a>
        )}

        {/* Indicador de encerrado */}
        {isEncerrado && (
          <span className="flex-1 text-center text-xs text-gray-400 py-1.5">
            Leilão encerrado
          </span>
        )}
      </div>

      {/* Rodapé - ID Interno */}
      {id_interno && (
        <div className="px-3 pb-1.5 flex items-center gap-1 text-[10px] text-gray-400">
          <Hash className="h-3 w-3" />
          <span>Ref: {id_interno}</span>
        </div>
      )}

      {/* Modal de Lotes */}
      <LotesModal
        open={showLotesModal}
        onOpenChange={setShowLotesModal}
        idInterno={auction.id_interno}
        tituloEdital={titulo || objeto_resumido || undefined}
      />
    </div>
  )
}
