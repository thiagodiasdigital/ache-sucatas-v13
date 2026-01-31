"""
Normalizador para resposta da API leiloesjudiciais.com.br

Converte dados brutos da API para o contrato canônico do projeto.

Regras canônicas:
- data_leilao = dt_fechamento (ISO 8601 com timezone)
- url_leiloeiro: prefixar https:// se não começar com http
- link_edital: priorizar "EDITAL RETIFICADO" > "EDITAL" > NULL
- tags: geradas a partir do título/descrição

Uso:
    normalizer = APILotNormalizer()
    normalized = normalizer.normalize(api_item)
    if normalized.is_valid:
        # Pronto para persistir
    else:
        # Enviar para quarentena
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

logger = logging.getLogger(__name__)

# Timezone Brasil
BR_TZ = ZoneInfo("America/Sao_Paulo")

# UFs válidas do Brasil
VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}

# Keywords para geração de tags
TAG_KEYWORDS = {
    "CARRO": ["carro", "automovel", "automóvel", "sedan", "hatch", "suv"],
    "MOTO": ["moto", "motocicleta", "motociclo", "scooter"],
    "CAMINHAO": ["caminhao", "caminhão", "truck", "carreta"],
    "ONIBUS": ["onibus", "ônibus", "micro-onibus"],
    "TRATOR": ["trator", "tratores", "colheitadeira"],
    "REBOQUE": ["reboque", "semirreboque", "carretinha"],
    "VEICULO": ["veiculo", "veículo", "placa", "chassi", "renavam"],
    "SUCATA": ["sucata", "sucatas", "inservivel", "inservível", "lote de peças"],
    "DOCUMENTADO": ["documentado", "com documento", "com documentação"],
    "SEM_DOCUMENTO": ["sem documento", "sem documentação", "documentação pendente"],
    "APREENDIDO": ["apreendido", "apreensão"],
}


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class NormalizedAPILot:
    """Lote normalizado da API, pronto para persistência."""

    # === IDENTIFICAÇÃO ===
    id_interno: str
    lote_id_original: str
    leilao_id_original: Optional[str]

    # === DADOS DO LOTE ===
    titulo: str
    descricao: Optional[str]
    objeto_resumido: Optional[str]

    # === LOCALIZAÇÃO ===
    cidade: Optional[str]
    uf: Optional[str]

    # === DATAS ===
    data_leilao: Optional[str]  # ISO 8601 com timezone
    data_publicacao: Optional[str]

    # === VALORES ===
    valor_avaliacao: Optional[float]
    valor_lance_inicial: Optional[float]
    valor_incremento: Optional[float]

    # === LINKS ===
    link_leiloeiro: Optional[str]
    link_edital: Optional[str]

    # === CLASSIFICAÇÃO ===
    tags: List[str]
    categoria: Optional[str]
    tipo_leilao: Optional[str]

    # === ORGANIZAÇÃO ===
    nome_leiloeiro: Optional[str]
    imagens: List[str]

    # === METADATA ===
    metadata: Dict[str, Any]
    confidence_score: int

    # === VALIDAÇÃO ===
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)


# ============================================================================
# NORMALIZADOR
# ============================================================================

class APILotNormalizer:
    """
    Normalizador de lotes da API para contrato canônico.

    Regras aplicadas:
    1. data_leilao = dt_fechamento convertido para ISO 8601 com timezone BR
    2. URLs normalizadas (https:// adicionado se necessário)
    3. link_edital prioriza EDITAL RETIFICADO
    4. Tags geradas a partir do conteúdo
    5. Validações aplicadas

    Exemplo:
        normalizer = APILotNormalizer()
        normalized = normalizer.normalize(api_item)
    """

    def normalize(self, api_item: Dict) -> NormalizedAPILot:
        """
        Normaliza item da API para contrato canônico.

        Campos da API leiloesjudiciais:
        - lote_id, leilao_id: IDs
        - nm_titulo_lote: Título do lote
        - nm_descricao: Descrição HTML
        - nm_cidade, nm_estado: Localização
        - dt_fechamento: Data do leilão (ISO 8601)
        - vl_lanceminimo, vl_lanceinicial, vl_incremento: Valores
        - nm_url_leiloeiro, nm_leiloeiro: Leiloeiro
        - id_categoria: 1=Veículos, 2=Bens Diversos, 3=Imóveis
        - anexos: Lista de arquivos (edital)
        - fotos: Lista de imagens

        Args:
            api_item: Dicionário bruto da API

        Returns:
            NormalizedAPILot com dados normalizados e status de validação
        """
        # Extrai IDs
        lote_id = str(api_item.get("lote_id", api_item.get("id", "")))
        leilao_id = str(api_item.get("leilao_id", "")) if api_item.get("leilao_id") else None

        # Gera id_interno único
        id_interno = self._generate_id_interno(lote_id, leilao_id)

        # Extrai e normaliza campos de texto
        titulo = self._clean_text(api_item.get("nm_titulo_lote", "")) or f"Lote {lote_id}"
        descricao = self._clean_html(api_item.get("nm_descricao", ""))
        objeto_resumido = self._generate_objeto_resumido(titulo, descricao)

        # Localização
        cidade = self._normalize_cidade(api_item.get("nm_cidade"))
        uf = self._normalize_uf(api_item.get("nm_estado"))

        # Data do leilão (dt_fechamento)
        data_leilao = self._normalize_data_leilao(api_item.get("dt_fechamento"))

        # Valores
        valor_avaliacao = self._normalize_valor(api_item.get("vl_lanceminimo") or api_item.get("vl_venda"))
        valor_lance_inicial = self._normalize_valor(api_item.get("vl_lanceinicial"))
        valor_incremento = self._normalize_valor(api_item.get("vl_incremento"))

        # Links - CORREÇÃO: Não concatenar URL hardcoded
        # Usa resolução centralizada para obter URL canônica do lote
        from connectors.common.url_resolution import resolve_lote_url, log_resolution, normalize_base_url

        # Busca URL canônica do lote se disponível na API
        url_lote_api = api_item.get("url_lote") or api_item.get("nm_url_lote") or api_item.get("link")
        url_leiloeiro_raw = api_item.get("nm_url_leiloeiro", "")

        # Normaliza URLs antes de passar para resolver (garante consistência)
        url_leiloeiro_normalized = normalize_base_url(url_leiloeiro_raw)

        # Constrói URL de fallback com padrão correto (se tiver dados suficientes)
        fallback_url = None
        if url_leiloeiro_normalized and leilao_id and lote_id:
            # Padrão correto: /leilao/index/leilao_id/{leilao_id}/lote/{lote_id}
            fallback_url = f"{url_leiloeiro_normalized}/leilao/index/leilao_id/{leilao_id}/lote/{lote_id}"

        # Resolve URL usando estratégia em cascata
        url_result = resolve_lote_url(
            candidate_urls=[url_lote_api, url_leiloeiro_normalized],
            candidate_labels=["api_canonical", "api_canonical"],  # Ambos vêm da API
            fallback_constructed=fallback_url,  # Fallback com padrão correto
            validate_http=False,  # Validação HTTP feita em batch no backfill
        )

        link_leiloeiro = url_result.final_url

        # Armazena metadados de resolução para auditoria
        url_resolution_metadata = url_result.to_dict()

        # Se resolução falhou, determina causa específica para auditoria
        if url_result.resolution_method == "failed":
            # Verifica se url_leiloeiro_normalized é apenas domínio base (sem path)
            is_base_only = bool(url_leiloeiro_normalized) and not self._url_has_path(url_leiloeiro_normalized)

            if not url_lote_api:
                # API não retornou URL canônica - causa mais comum
                url_resolution_metadata["resolution_method"] = "missing_canonical"
                if is_base_only:
                    url_resolution_metadata["error"] = "API não retornou URL canônica do lote (apenas base domain disponível)"
                else:
                    url_resolution_metadata["error"] = "API não retornou URL canônica do lote"
            # link_leiloeiro permanece None - não inventar URL

        # Loga se necessário (constructed=True, redirect, ou erro)
        log_resolution(url_result, context=f"lote:{lote_id}")

        link_edital = self._extract_link_edital(api_item.get("anexos", []))

        # Tags baseadas na categoria e conteúdo
        categoria_nome = api_item.get("nm_categoria", "")
        tags = self._generate_tags(titulo, descricao, categoria_nome)

        # Tipo de leilão (não disponível diretamente, inferir do status)
        tipo_leilao = "online"  # Padrão para leilões judiciais

        # Imagens
        imagens = self._extract_imagens(api_item.get("fotos", []))

        # Nome do leiloeiro
        nome_leiloeiro = api_item.get("nm_leiloeiro", "Leilões Judiciais")

        # Metadata para rastreabilidade
        id_categoria = api_item.get("id_categoria")
        metadata = {
            "api_lote_id": api_item.get("lote_id"),
            "api_leilao_id": leilao_id,
            "id_categoria": id_categoria,
            "nm_categoria": categoria_nome,
            "nm_subcategoria": api_item.get("nm_subcategoria"),
            "statuslote_id": api_item.get("statuslote_id"),
            "nm_statuslote": api_item.get("nm_statuslote"),
            "nu_visitas": api_item.get("nu_visitas"),
            "extraction_timestamp": datetime.now(BR_TZ).isoformat(),
            # AUDITORIA: Metadados de resolução de URL
            "url_resolution": url_resolution_metadata,
        }

        # Calcula confidence score
        confidence = self._calculate_confidence(api_item, data_leilao, tags)

        # Cria objeto normalizado
        lot = NormalizedAPILot(
            id_interno=id_interno,
            lote_id_original=lote_id,
            leilao_id_original=leilao_id,
            titulo=titulo,
            descricao=descricao,
            objeto_resumido=objeto_resumido,
            cidade=cidade,
            uf=uf,
            data_leilao=data_leilao,
            data_publicacao=datetime.now(BR_TZ).strftime("%Y-%m-%d"),
            valor_avaliacao=valor_avaliacao,
            valor_lance_inicial=valor_lance_inicial,
            valor_incremento=valor_incremento,
            link_leiloeiro=link_leiloeiro,
            link_edital=link_edital,
            tags=tags,
            categoria=api_item.get("categoria"),
            tipo_leilao=tipo_leilao,
            nome_leiloeiro=nome_leiloeiro,
            imagens=imagens,
            metadata=metadata,
            confidence_score=confidence,
        )

        # Valida o lote
        self._validate(lot, api_item)

        return lot

    # ========================================================================
    # MÉTODOS DE NORMALIZAÇÃO
    # ========================================================================

    def _generate_id_interno(self, lote_id: str, leilao_id: Optional[str]) -> str:
        """
        Gera ID único no formato leiloesjudiciais|{hash}.

        O hash é determinístico baseado nos IDs originais.
        """
        parts = ["leiloesjudiciais", lote_id]
        if leilao_id:
            parts.append(leilao_id)
        combined = "|".join(parts)
        hash_value = hashlib.md5(combined.encode()).hexdigest()[:12].upper()
        return f"leiloesjudiciais|{hash_value}"

    def _normalize_data_leilao(self, dt_fechamento: Optional[str]) -> Optional[str]:
        """
        Normaliza dt_fechamento para ISO 8601 com timezone.

        Input esperado: "2026-02-15T14:00:00" ou "2026-02-15" ou similar
        Output: "2026-02-15T14:00:00-03:00" (ISO 8601 com timezone BR)
        """
        if not dt_fechamento:
            return None

        try:
            # Remove espaços extras
            dt_fechamento = str(dt_fechamento).strip()

            # Tenta diferentes formatos
            dt: Optional[datetime] = None

            # Formato ISO com T
            if "T" in dt_fechamento:
                # Remove timezone se existir
                clean = dt_fechamento.replace("Z", "").split("+")[0].split("-03:00")[0]
                try:
                    dt = datetime.fromisoformat(clean)
                except ValueError:
                    pass

            # Formato data simples YYYY-MM-DD
            if dt is None and len(dt_fechamento) >= 10:
                try:
                    dt = datetime.strptime(dt_fechamento[:10], "%Y-%m-%d")
                except ValueError:
                    pass

            # Formato DD/MM/YYYY
            if dt is None:
                try:
                    dt = datetime.strptime(dt_fechamento[:10], "%d/%m/%Y")
                except ValueError:
                    pass

            if dt is None:
                logger.warning(f"Formato de data não reconhecido: {dt_fechamento}")
                return None

            # Adiciona timezone BR
            dt = dt.replace(tzinfo=BR_TZ)
            return dt.isoformat()

        except Exception as e:
            logger.warning(f"Erro ao normalizar data '{dt_fechamento}': {e}")
            return None

    def _extract_link_edital(self, anexos: List) -> Optional[str]:
        """
        Extrai link do edital dos anexos.

        Formato da API leiloesjudiciais:
        - nm: Nome do arquivo (ex: "EDITAL", "EDITAL RETIFICADO")
        - nm_path_completo: URL completa do arquivo

        Prioridade:
        1. "EDITAL RETIFICADO" ou "RETIFICAÇÃO"
        2. "EDITAL" (genérico)
        3. NULL (se não encontrar)
        """
        if not anexos or not isinstance(anexos, list):
            return None

        edital_retificado: Optional[str] = None
        edital_normal: Optional[str] = None

        for anexo in anexos:
            if not isinstance(anexo, dict):
                continue

            # Nome do arquivo
            nome = (anexo.get("nm") or anexo.get("nome") or "").upper()
            # URL completa
            url = anexo.get("nm_path_completo") or anexo.get("url")

            if not url:
                continue

            # Verifica se é edital
            if "RETIFICADO" in nome or "RETIFICACAO" in nome or "RETIFICAÇÃO" in nome:
                edital_retificado = url
            elif "EDITAL" in nome:
                edital_normal = url

        return edital_retificado or edital_normal

    def _normalize_url(self, url: Optional[str]) -> Optional[str]:
        """Normaliza URL adicionando https:// se necessário."""
        if not url:
            return None

        url = str(url).strip()

        if not url:
            return None

        if url.startswith("www."):
            return f"https://{url}"
        elif not url.startswith(("http://", "https://")):
            return f"https://{url}"

        return url

    def _url_has_path(self, url: Optional[str]) -> bool:
        """
        Verifica se URL tem path além do domínio base.

        Retorna False para URLs como:
        - https://example.com
        - https://example.com/

        Retorna True para URLs como:
        - https://example.com/leilao/123
        """
        if not url:
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            return bool(path)
        except Exception:
            return False

    def _normalize_cidade(self, cidade: Optional[str]) -> Optional[str]:
        """Normaliza nome da cidade."""
        if not cidade:
            return None
        cidade = self._clean_text(cidade)
        if not cidade:
            return None
        return cidade.title()

    def _normalize_uf(self, uf: Optional[str]) -> Optional[str]:
        """Normaliza UF, validando contra lista de UFs válidas."""
        if not uf:
            return None
        uf = str(uf).upper().strip()[:2]
        return uf if uf in VALID_UFS else None

    def _normalize_valor(self, valor: Any) -> Optional[float]:
        """Normaliza valor monetário."""
        if valor is None:
            return None

        try:
            # Remove caracteres não numéricos (exceto . e ,)
            if isinstance(valor, str):
                valor = valor.replace("R$", "").replace(" ", "")
                valor = valor.replace(".", "").replace(",", ".")

            v = float(valor)
            return round(v, 2) if v > 0 else None
        except (ValueError, TypeError):
            return None

    def _generate_tags(
        self,
        titulo: str,
        descricao: Optional[str],
        categoria: Optional[str]
    ) -> List[str]:
        """
        Gera tags baseadas no conteúdo do lote.

        Analisa título, descrição e categoria para identificar keywords.
        """
        tags: set = set()
        text = f"{titulo} {descricao or ''} {categoria or ''}".lower()

        for tag, keywords in TAG_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                tags.add(tag)

        # Se não encontrou nenhuma tag específica
        if not tags:
            tags.add("OUTROS")

        return sorted(list(tags))

    def _generate_objeto_resumido(self, titulo: str, descricao: Optional[str]) -> str:
        """Gera resumo do objeto do lote."""
        # Usa título como base
        resumo = titulo

        # Se descrição tiver mais detalhes, considera
        if descricao and len(descricao) > len(titulo):
            # Pega primeira frase da descrição
            primeira_frase = descricao.split(".")[0].strip()
            if len(primeira_frase) > 20:
                resumo = primeira_frase

        # Limita tamanho
        return resumo[:200] if resumo else titulo[:200]

    def _map_tipo_leilao(self, tipo: Optional[int]) -> Optional[str]:
        """Mapeia tipo numérico para string descritiva."""
        mapping = {
            1: "presencial",
            2: "online",
            3: "hibrido"  # Este será rejeitado na validação
        }
        return mapping.get(tipo)

    def _extract_imagens(self, fotos: List) -> List[str]:
        """
        Extrai URLs de imagens, limitando a 5.

        Formato da API leiloesjudiciais:
        - nm_path_completo: URL completa da imagem (tamanho médio)
        """
        urls = []

        if not fotos or not isinstance(fotos, list):
            return urls

        for foto in fotos[:5]:  # Limita a 5 imagens
            url: Optional[str] = None

            if isinstance(foto, dict):
                # Usa a URL completa (já inclui tamanho)
                url = foto.get("nm_path_completo") or foto.get("url")
            elif isinstance(foto, str):
                url = foto

            if url:
                urls.append(url)

        return urls

    def _calculate_confidence(
        self,
        item: Dict,
        data_leilao: Optional[str],
        tags: List[str]
    ) -> int:
        """
        Calcula score de confiança (0-100).

        Fatores:
        - Presença de data_leilao: +20
        - Localização completa: +15
        - Valor de avaliação: +10
        - Tags relevantes (VEICULO/SUCATA): +5
        - Imagens: +5
        - Link do edital: +5
        """
        score = 40  # Base

        if data_leilao:
            score += 20
        if item.get("cidade") and item.get("estado"):
            score += 15
        if item.get("valor_avaliacao"):
            score += 10
        if "VEICULO" in tags or "SUCATA" in tags:
            score += 5
        if item.get("imagens"):
            score += 5
        if item.get("arquivos"):
            score += 5

        return min(score, 100)

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Limpa texto removendo espaços extras e caracteres inválidos."""
        if not text:
            return None
        text = re.sub(r'\s+', ' ', str(text))
        text = text.strip()
        return text if text else None

    def _clean_html(self, html: Optional[str]) -> Optional[str]:
        """Remove tags HTML e limpa o texto."""
        if not html:
            return None
        # Remove tags HTML
        text = re.sub(r'<[^>]+>', ' ', str(html))
        # Remove entidades HTML
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        # Limpa espaços
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text[:2000] if text else None  # Limita tamanho

    # ========================================================================
    # VALIDAÇÃO
    # ========================================================================

    def _validate(self, lot: NormalizedAPILot, api_item: Dict):
        """
        Valida lote normalizado.

        Erros bloqueantes (is_valid = False):
        - MISSING_DATA_LEILAO: Campo obrigatório ausente
        - MISSING_TAGS: Tags vazias

        NOTA: Validação de id_categoria é feita no pré-filtro do pipeline,
        não aqui, para permitir configuração via flag --no-filter-vehicles.

        Warnings (reduzem confidence_score):
        - Cidade ausente
        - UF ausente
        """
        errors = []

        # === ERROS BLOQUEANTES ===

        # data_leilao é obrigatório
        if not lot.data_leilao:
            errors.append("MISSING_DATA_LEILAO")

        # tags devem existir
        if not lot.tags:
            errors.append("MISSING_TAGS")

        # id_interno deve existir
        if not lot.id_interno:
            errors.append("MISSING_ID_INTERNO")

        # === WARNINGS (penalizam score mas não bloqueiam) ===

        if not lot.cidade:
            lot.confidence_score = max(0, lot.confidence_score - 10)

        if not lot.uf:
            lot.confidence_score = max(0, lot.confidence_score - 5)

        if not lot.link_edital:
            lot.confidence_score = max(0, lot.confidence_score - 5)

        # Atualiza status
        lot.validation_errors = errors
        lot.is_valid = len(errors) == 0
