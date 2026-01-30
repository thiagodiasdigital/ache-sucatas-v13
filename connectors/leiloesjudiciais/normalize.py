"""
Módulo de Normalização - Leilões Judiciais.

Responsável por:
1. Converter dados extraídos para o formato do Contrato Canônico
2. Normalizar datas (DD-MM-YYYY)
3. Normalizar valores monetários (Decimal)
4. Normalizar URLs (https://)
5. Normalizar texto (trim, espaços)
6. Gerar tags baseadas no conteúdo
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .config import Config, config
from .parse import ParsedLot
from .parser_v2 import ExtractedLot


# Timezone do Brasil
BR_TZ = ZoneInfo("America/Sao_Paulo")

# Mapeamento de UFs válidas
VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}

# Keywords para classificação de tags
TAG_KEYWORDS = {
    "SUCATA": ["sucata", "sucatas", "lata", "inservível", "inservivel"],
    "DOCUMENTADO": ["documentado", "com documento", "licenciado"],
    "SEM_DOCUMENTO": ["sem documento", "sem documentação", "sem documentacao"],
    "CARRO": ["carro", "automóvel", "automovel", "sedan", "hatch", "suv"],
    "MOTO": ["moto", "motocicleta", "motoneta", "scooter"],
    "CAMINHAO": ["caminhão", "caminhao", "truck", "cavalo mecânico"],
    "ONIBUS": ["ônibus", "onibus", "micro-ônibus", "microonibus"],
    "TRATOR": ["trator", "máquina agrícola", "maquina agricola"],
    "REBOQUE": ["reboque", "carreta", "semirreboque", "semirreboque"],
}

# PHASE 5: Palavras-chave de inclusão (veículos/sucatas)
INCLUDE_KEYWORDS_VEHICLES = [
    "veículo", "veiculo", "carro", "automóvel", "automovel",
    "caminhão", "caminhao", "moto", "motocicleta", "van",
    "ônibus", "onibus", "reboque", "cavalo mecânico",
    "placa", "renavam", "chassi",
]
INCLUDE_KEYWORDS_SUCATA = [
    "sucata", "sucatas", "peças", "pecas", "desmontagem",
    "batido", "sinistrado", "inservível", "inservivel", "carcaça", "carcaca",
]

# PHASE 5: Palavras-chave de exclusão (imóveis e outros)
EXCLUDE_KEYWORDS = [
    "imóvel", "imovel", "apartamento", "casa", "terreno",
    "loteamento", "sala comercial", "prédio", "predio",
    "galpão", "galpao", "fazenda", "sítio", "sitio", "chácara", "chacara",
]


@dataclass
class NormalizedLot:
    """Lote normalizado pronto para emissão."""
    # Identificação
    id_interno: str
    titulo: str
    descricao: str

    # Localização
    municipio: str
    uf: str

    # Datas (formato DD-MM-YYYY)
    data_leilao: Optional[str] = None
    data_publicacao: Optional[str] = None
    data_atualizacao: Optional[str] = None

    # Links
    link_leiloeiro: str = ""
    link_pncp: Optional[str] = None
    pncp_id: Optional[str] = None

    # Valores
    valor_estimado: Optional[float] = None

    # Classificação
    tags: List[str] = field(default_factory=list)
    objeto_resumido: Optional[str] = None
    tipo_leilao: str = "2"  # Online por padrão

    # Organização
    orgao: str = "Leilão Judicial"  # Genérico para leiloeiros
    nome_leiloeiro: str = "Leilões Judiciais"
    n_edital: Optional[str] = None

    # Origem
    source_type: str = "leiloeiro"
    source_name: str = "Leilões Judiciais"

    # Metadados extras
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Qualidade
    confidence_score: float = 0.0
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # PHASE 5: Category classification
    category_guess: str = "unknown"  # veiculo, sucata, imovel, unknown
    is_vehicle_or_scrap: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário do Supabase."""
        # Add category to metadata
        metadata_with_category = dict(self.metadata)
        metadata_with_category["category_guess"] = self.category_guess
        metadata_with_category["is_vehicle_or_scrap"] = self.is_vehicle_or_scrap

        return {
            "id_interno": self.id_interno,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "cidade": self.municipio,
            "uf": self.uf,
            "data_leilao": self.data_leilao,
            "data_publicacao": self.data_publicacao,
            "data_atualizacao": self.data_atualizacao,
            "link_leiloeiro": self.link_leiloeiro,
            "link_pncp": self.link_pncp,
            "pncp_id": self.pncp_id,
            "valor_estimado": self.valor_estimado,
            "tags": self.tags,
            "objeto_resumido": self.objeto_resumido,
            "modalidade_leilao": self.tipo_leilao,
            "orgao": self.orgao,
            "nome_leiloeiro": self.nome_leiloeiro,
            "n_edital": self.n_edital,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "metadata": metadata_with_category,
            "publication_status": "published" if self.is_valid and self.is_vehicle_or_scrap else "draft",
            "score": int(self.confidence_score),
        }


class LeilaoNormalizer:
    """
    Normalizador de dados de lotes.

    Converte dados brutos do parser para o formato
    do Contrato Canônico do Ache Sucatas.
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.config = cfg or config

    def normalize(self, parsed) -> NormalizedLot:
        """
        Normaliza um lote parseado.

        Args:
            parsed: ParsedLot (v1) ou ExtractedLot (v2)

        Returns:
            NormalizedLot normalizado
        """
        # Handle both ParsedLot (v1) and ExtractedLot (v2)
        if isinstance(parsed, ExtractedLot):
            return self._normalize_v2(parsed)
        else:
            return self._normalize_v1(parsed)

    def _normalize_v2(self, parsed: ExtractedLot) -> NormalizedLot:
        """Normaliza ExtractedLot do parser_v2."""
        # Gera ID interno
        id_interno = self._generate_id_interno(
            parsed.leilao_id,
            parsed.lote_id
        )

        # Normaliza campos - usar diretamente do ExtractedLot
        titulo = parsed.titulo or f"Lote {parsed.lote_id}"
        descricao = parsed.descricao or f"Lote de leilão judicial. URL: {parsed.url}"
        municipio = self._normalize_cidade(parsed.cidade)
        uf = self._normalize_uf(parsed.uf)
        valor = self._normalize_valor(parsed.valor_avaliacao)

        # Generate tags from title/description
        text = f"{titulo} {descricao}".lower()
        tags = self._generate_tags_from_text(text)

        objeto_resumido = titulo[:200] if titulo else "Lote de leilão judicial"

        # Data de hoje como data_publicacao
        hoje = datetime.now(BR_TZ).strftime("%d-%m-%Y")

        # Metadados extras
        metadata = {
            "leilao_id": parsed.leilao_id,
            "lote_id": parsed.lote_id,
            "extraction_timestamp": parsed.extraction_timestamp,
            "extraction_method": parsed.extraction_method,
            "source_url": parsed.url,
            "title_source": parsed.title_source,
            "title_quality": parsed.title_quality,
            "location_quality": parsed.location_quality,
            "is_valid_page": parsed.is_valid_page,
        }
        if parsed.imagens:
            metadata["imagens"] = parsed.imagens[:5]
        if parsed.warnings:
            metadata["warnings"] = parsed.warnings

        # PHASE 5: Category classification from text
        category, is_vehicle_or_scrap = self._classify_category_from_text(text, parsed.url)

        # Calcula confidence score
        confidence = 50.0
        if parsed.title_quality == "real":
            confidence += 30
        elif parsed.title_quality == "generated":
            confidence += 10
        if parsed.location_quality == "real":
            confidence += 20

        # Cria objeto normalizado
        result = NormalizedLot(
            id_interno=id_interno,
            titulo=titulo,
            descricao=descricao,
            municipio=municipio,
            uf=uf,
            data_publicacao=hoje,
            data_atualizacao=hoje,
            data_leilao=parsed.data_leilao,
            link_leiloeiro=self._normalize_url(parsed.url),
            valor_estimado=valor,
            tags=tags,
            objeto_resumido=objeto_resumido,
            metadata=metadata,
            confidence_score=confidence,
            category_guess=category,
            is_vehicle_or_scrap=is_vehicle_or_scrap,
        )

        # Valida - usando validação relaxada
        self._validate_v2(result, parsed)

        return result

    def _validate_v2(self, lot: NormalizedLot, parsed: ExtractedLot):
        """Validação para parser v2 - mais permissiva."""
        errors = []
        warnings = []

        if not lot.id_interno:
            errors.append("id_interno ausente")

        # Aceita títulos gerados, mas não "undefined"
        if not lot.titulo or lot.titulo.lower() == "undefined":
            errors.append("titulo ausente ou undefined")
        elif parsed.title_quality == "generated":
            warnings.append("titulo gerado automaticamente")
            lot.confidence_score = max(0, lot.confidence_score - 10)

        if not lot.link_leiloeiro:
            errors.append("link_leiloeiro ausente")

        # Página inválida (retornou "undefined")
        if not parsed.is_valid_page:
            errors.append("página não renderizou corretamente")

        # Campos desejáveis (warnings)
        if not lot.municipio or lot.municipio == "Não informado":
            warnings.append("municipio não identificado")
            lot.confidence_score = max(0, lot.confidence_score - 20)

        if lot.uf == "XX":
            warnings.append("uf não identificada")
            lot.confidence_score = max(0, lot.confidence_score - 10)

        lot.validation_errors = errors + [f"WARN: {w}" for w in warnings]
        lot.is_valid = len(errors) == 0

    def _classify_category_from_text(self, text: str, url: str) -> tuple[str, bool]:
        """Classifica categoria baseado em texto concatenado."""
        text = text.lower()

        # Verifica exclusão primeiro (imóveis)
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in text:
                return "imovel", False

        # Verifica inclusão de veículos
        for keyword in INCLUDE_KEYWORDS_VEHICLES:
            if keyword in text:
                return "veiculo", True

        # Verifica inclusão de sucatas
        for keyword in INCLUDE_KEYWORDS_SUCATA:
            if keyword in text:
                return "sucata", True

        # Verifica marcas de veículos
        vehicle_brands = [
            "fiat", "volkswagen", "vw", "chevrolet", "gm", "ford",
            "honda", "yamaha", "toyota", "hyundai", "jeep", "nissan",
            "mercedes", "bmw", "audi", "peugeot", "citroen", "renault",
            "scania", "volvo", "iveco", "man", "mitsubishi", "kia",
        ]
        for brand in vehicle_brands:
            if brand in text:
                return "veiculo", True

        return "unknown", False

    def _generate_tags_from_text(self, text: str) -> List[str]:
        """Gera tags baseadas no texto."""
        tags = set()
        text = text.lower()

        for tag, keywords in TAG_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                tags.add(tag)

        if not tags:
            if self.config.contains_vehicle_keyword(text):
                tags.add("VEICULO")
            else:
                tags.add("OUTROS")

        return sorted(list(tags))

    def _normalize_v1(self, parsed: ParsedLot) -> NormalizedLot:
        """Normaliza ParsedLot do parser v1 (legado)."""
        # Gera ID interno
        id_interno = self._generate_id_interno(
            parsed.leilao_id,
            parsed.lote_id
        )

        # Normaliza campos
        titulo = self._normalize_titulo(parsed)
        descricao = self._normalize_descricao(parsed)
        municipio = self._normalize_cidade(parsed.cidade)
        uf = self._normalize_uf(parsed.uf)
        valor = self._normalize_valor(parsed.valor_avaliacao)
        tags = self._generate_tags(parsed)
        objeto_resumido = self._generate_objeto_resumido(parsed)

        # Data de hoje como data_publicacao
        hoje = datetime.now(BR_TZ).strftime("%d-%m-%Y")

        # Metadados extras
        metadata = self._build_metadata(parsed)

        # PHASE 5: Category classification
        category, is_vehicle_or_scrap = self._classify_category(parsed)

        # Cria objeto normalizado
        result = NormalizedLot(
            id_interno=id_interno,
            titulo=titulo,
            descricao=descricao,
            municipio=municipio,
            uf=uf,
            data_publicacao=hoje,
            data_atualizacao=hoje,
            data_leilao=None,  # Não disponível no HTML estático
            link_leiloeiro=self._normalize_url(parsed.url),
            valor_estimado=valor,
            tags=tags,
            objeto_resumido=objeto_resumido,
            metadata=metadata,
            confidence_score=parsed.extraction_confidence,
            category_guess=category,
            is_vehicle_or_scrap=is_vehicle_or_scrap,
        )

        # Valida
        self._validate(result)

        return result

    def _classify_category(self, parsed: ParsedLot) -> tuple[str, bool]:
        """
        PHASE 5: Classifica lote em categoria (veículo, sucata, imóvel, unknown).

        Implementa filtro em 2 etapas:
        - Etapa A: contexto da URL (páginas de veículos prioritárias)
        - Etapa B: análise de conteúdo (título + descrição)

        Args:
            parsed: ParsedLot com dados extraídos

        Returns:
            Tupla (categoria, é_veículo_ou_sucata)
        """
        # Concatena texto para análise
        text = ""
        if parsed.descricao_veiculo:
            text += " " + parsed.descricao_veiculo
        if parsed.og_description:
            text += " " + parsed.og_description
        if parsed.titulo_completo:
            text += " " + parsed.titulo_completo

        text = text.lower()

        # Verifica exclusão primeiro (imóveis)
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in text:
                return "imovel", False

        # Verifica inclusão de veículos
        for keyword in INCLUDE_KEYWORDS_VEHICLES:
            if keyword in text:
                return "veiculo", True

        # Verifica inclusão de sucatas
        for keyword in INCLUDE_KEYWORDS_SUCATA:
            if keyword in text:
                return "sucata", True

        # Se a URL sugere veículo (categorias de veículos)
        if parsed.url and self.config.is_vehicle_url(parsed.url):
            return "veiculo", True

        # Verifica marcas de veículos comuns
        vehicle_brands = [
            "fiat", "volkswagen", "vw", "chevrolet", "gm", "ford",
            "honda", "yamaha", "toyota", "hyundai", "jeep", "nissan",
            "mercedes", "bmw", "audi", "peugeot", "citroen", "renault",
            "scania", "volvo", "iveco", "man", "mitsubishi", "kia",
        ]
        for brand in vehicle_brands:
            if brand in text:
                return "veiculo", True

        # Não identificado claramente
        return "unknown", False

    def _generate_id_interno(self, leilao_id: str, lote_id: str) -> str:
        """
        Gera ID único para o lote.

        Formato: leiloesjudiciais|{hash}
        """
        combined = f"leiloesjudiciais|{leilao_id}|{lote_id}"
        hash_value = hashlib.md5(combined.encode()).hexdigest()[:12].upper()
        return f"leiloesjudiciais|{hash_value}"

    def _normalize_titulo(self, parsed: ParsedLot) -> str:
        """Gera título normalizado."""
        if parsed.descricao_veiculo:
            return self._clean_text(parsed.descricao_veiculo)

        if parsed.og_title:
            # Remove sufixo "- Leilões Judiciais"
            title = re.sub(r'\s*-\s*Leilões Judiciais\s*$', '', parsed.og_title, flags=re.IGNORECASE)
            # Remove cidade/UF se presente
            title = re.sub(r'\s*-\s*[A-Za-zÀ-ÿ\s]+/[A-Z]{2}\s*$', '', title)
            return self._clean_text(title)

        return "Lote de Leilão"

    def _normalize_descricao(self, parsed: ParsedLot) -> str:
        """Gera descrição normalizada."""
        parts = []

        if parsed.descricao_veiculo:
            parts.append(parsed.descricao_veiculo)

        if parsed.og_description:
            parts.append(parsed.og_description)

        if parsed.cidade and parsed.uf:
            parts.append(f"Localização: {parsed.cidade}/{parsed.uf}")

        if not parts:
            parts.append("Lote disponível para leilão judicial.")

        return self._clean_text(". ".join(parts))

    def _normalize_cidade(self, cidade: Optional[str]) -> str:
        """Normaliza nome da cidade."""
        if not cidade:
            return "Não informado"

        # Remove espaços extras e formata
        cidade = self._clean_text(cidade)
        return cidade.title()

    def _normalize_uf(self, uf: Optional[str]) -> str:
        """Normaliza UF."""
        if not uf:
            return "XX"  # Placeholder para UF desconhecida

        uf = uf.upper().strip()

        if uf in VALID_UFS:
            return uf

        return "XX"

    def _normalize_valor(self, valor: Optional[float]) -> Optional[float]:
        """Normaliza valor monetário."""
        if valor is None:
            return None

        # Garante que é positivo
        if valor <= 0:
            return None

        # Arredonda para 2 casas decimais
        return round(valor, 2)

    def _normalize_url(self, url: str) -> str:
        """Normaliza URL."""
        url = url.strip()

        # Garante https://
        if url.startswith("www."):
            url = f"https://{url}"
        elif not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        return url

    def _generate_tags(self, parsed: ParsedLot) -> List[str]:
        """Gera tags baseadas no conteúdo."""
        tags = set()
        text = ""

        if parsed.descricao_veiculo:
            text += " " + parsed.descricao_veiculo
        if parsed.og_description:
            text += " " + parsed.og_description
        if parsed.titulo_completo:
            text += " " + parsed.titulo_completo

        text = text.lower()

        # Verifica keywords
        for tag, keywords in TAG_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                tags.add(tag)

        # Se não encontrou nenhuma tag específica
        if not tags:
            # Verifica se é veículo pelo contexto
            if self.config.contains_vehicle_keyword(text):
                tags.add("VEICULO")
            else:
                tags.add("OUTROS")

        return sorted(list(tags))

    def _generate_objeto_resumido(self, parsed: ParsedLot) -> str:
        """Gera resumo do objeto."""
        if parsed.descricao_veiculo:
            # Limita a 200 caracteres
            resumo = parsed.descricao_veiculo[:200]
            if len(parsed.descricao_veiculo) > 200:
                resumo += "..."
            return resumo

        return "Lote de leilão judicial"

    def _build_metadata(self, parsed: ParsedLot) -> Dict[str, Any]:
        """Constrói metadados extras."""
        metadata = {
            "leilao_id": parsed.leilao_id,
            "lote_id": parsed.lote_id,
            "extraction_timestamp": parsed.extraction_timestamp,
            "extraction_method": parsed.extraction_method,
            "source_url": parsed.url,
        }

        if parsed.imagens:
            metadata["imagens"] = parsed.imagens[:5]  # Limita a 5

        if parsed.og_image:
            metadata["og_image"] = parsed.og_image

        if parsed.json_ld_data:
            metadata["json_ld"] = parsed.json_ld_data

        if parsed.warnings:
            metadata["warnings"] = parsed.warnings

        return metadata

    def _clean_text(self, text: str) -> str:
        """Limpa e normaliza texto."""
        if not text:
            return ""

        # Remove espaços extras
        text = re.sub(r'\s+', ' ', text)
        # Remove espaços no início/fim
        text = text.strip()

        return text

    def _validate(self, lot: NormalizedLot):
        """
        Valida lote normalizado.

        Para source_type='leiloeiro', aplicamos validação mais flexível:
        - Título e link são obrigatórios
        - Cidade/UF são desejáveis mas não bloqueantes
        - Itens sem cidade/UF são aceitos mas com score reduzido
        """
        errors = []
        warnings = []

        # Campos obrigatórios (bloqueantes)
        if not lot.id_interno:
            errors.append("id_interno ausente")

        if not lot.titulo or lot.titulo == "Lote de Leilão" or lot.titulo.lower() == "undefined":
            errors.append("titulo genérico ou ausente")

        if not lot.link_leiloeiro:
            errors.append("link_leiloeiro ausente")

        # Campos desejáveis (warnings, não bloqueantes para leiloeiro)
        if not lot.municipio or lot.municipio == "Não informado":
            warnings.append("municipio não identificado")
            # Reduce confidence score instead of blocking
            lot.confidence_score = max(0, lot.confidence_score - 20)

        if lot.uf == "XX":
            warnings.append("uf não identificada")
            lot.confidence_score = max(0, lot.confidence_score - 10)

        # Store both errors and warnings in validation_errors for reporting
        lot.validation_errors = errors + [f"WARN: {w}" for w in warnings]

        # Item is valid if no blocking errors (city/UF are warnings only)
        lot.is_valid = len(errors) == 0


def normalize_lot(parsed: ParsedLot) -> NormalizedLot:
    """Função de conveniência para normalização."""
    normalizer = LeilaoNormalizer()
    return normalizer.normalize(parsed)
