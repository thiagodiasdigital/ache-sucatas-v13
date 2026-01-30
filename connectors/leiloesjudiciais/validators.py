"""
Validadores para pipeline leiloesjudiciais.

Regras de validação:
- Excluir tipo=3 (híbrido) - fora do escopo
- Garantir data_leilao presente
- Garantir tags não vazias
- Validar UF se presente

Códigos de rejeição padronizados:
- TIPO_3: Leilão tipo 3 (híbrido) não suportado
- MISSING_DATA_LEILAO: Campo obrigatório data_leilao ausente
- MISSING_TAGS: Tags ausentes ou vazias
- INVALID_UF: UF inválida
- MISSING_ID_INTERNO: Falha ao gerar id_interno
- INVALID_TITULO: Título ausente ou inválido

Uso:
    validator = LoteValidator()
    result = validator.validate(normalized_lot)
    if result.is_valid:
        # Pronto para persistir
    else:
        # Enviar para quarentena com result.errors
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .normalize_api import NormalizedAPILot

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES
# ============================================================================

# Códigos de rejeição padronizados
class RejectionCode:
    """Códigos padronizados de rejeição."""
    TIPO_3 = "TIPO_3"
    MISSING_DATA_LEILAO = "MISSING_DATA_LEILAO"
    MISSING_TAGS = "MISSING_TAGS"
    INVALID_UF = "INVALID_UF"
    MISSING_ID_INTERNO = "MISSING_ID_INTERNO"
    INVALID_TITULO = "INVALID_TITULO"
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"
    API_ERROR = "API_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    CATEGORY_EXCLUDED = "CATEGORY_EXCLUDED"
    EXPIRED_AUCTION = "EXPIRED_AUCTION"


# Descrições dos códigos
REJECTION_DESCRIPTIONS: Dict[str, str] = {
    RejectionCode.TIPO_3: "Leilão tipo 3 (híbrido) não suportado pelo escopo",
    RejectionCode.MISSING_DATA_LEILAO: "Campo obrigatório data_leilao ausente",
    RejectionCode.MISSING_TAGS: "Campo obrigatório tags ausente ou vazio",
    RejectionCode.INVALID_UF: "UF inválida ou não reconhecida",
    RejectionCode.MISSING_ID_INTERNO: "Falha ao gerar id_interno",
    RejectionCode.INVALID_TITULO: "Título ausente ou inválido",
    RejectionCode.DUPLICATE_CONTENT: "Conteúdo duplicado (mesmo content_hash)",
    RejectionCode.API_ERROR: "Erro ao buscar dados da API",
    RejectionCode.PARSE_ERROR: "Erro ao parsear resposta da API",
    RejectionCode.CATEGORY_EXCLUDED: "Categoria excluída do escopo (ex: imóveis)",
    RejectionCode.EXPIRED_AUCTION: "Leilão já encerrado",
}

# UFs válidas
VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ValidationResult:
    """Resultado de validação de um lote."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def primary_error(self) -> Optional[str]:
        """Retorna o primeiro erro (código principal de rejeição)."""
        return self.errors[0] if self.errors else None

    @property
    def error_description(self) -> str:
        """Retorna descrição concatenada de todos os erros."""
        descriptions = []
        for code in self.errors:
            desc = REJECTION_DESCRIPTIONS.get(code, code)
            descriptions.append(f"{code}: {desc}")
        return "; ".join(descriptions) if descriptions else ""


@dataclass
class ValidationStats:
    """Estatísticas agregadas de validação."""
    total: int = 0
    valid: int = 0
    invalid: int = 0
    errors_by_code: Dict[str, int] = field(default_factory=dict)

    def record(self, result: ValidationResult):
        """Registra resultado de validação."""
        self.total += 1
        if result.is_valid:
            self.valid += 1
        else:
            self.invalid += 1
            for code in result.errors:
                self.errors_by_code[code] = self.errors_by_code.get(code, 0) + 1

    @property
    def valid_rate(self) -> float:
        """Taxa de validação em porcentagem."""
        if self.total == 0:
            return 0.0
        return (self.valid / self.total) * 100

    @property
    def top_errors(self) -> List[Tuple[str, int]]:
        """Top erros ordenados por frequência."""
        return sorted(
            self.errors_by_code.items(),
            key=lambda x: x[1],
            reverse=True
        )


# ============================================================================
# VALIDADOR
# ============================================================================

class LoteValidator:
    """
    Validador de lotes normalizados.

    Aplica regras de negócio:
    - Tipo 3 (híbrido) não aceito
    - data_leilao obrigatório
    - tags obrigatórias

    Uso:
        validator = LoteValidator()
        result = validator.validate(normalized_lot)
        valid_lots, quarantine_lots = validator.filter_valid(lots)
    """

    def __init__(self, check_expiration: bool = False):
        """
        Inicializa validador.

        Args:
            check_expiration: Se True, rejeita leilões já encerrados
        """
        self.check_expiration = check_expiration
        self.stats = ValidationStats()

    def validate(self, lot: NormalizedAPILot) -> ValidationResult:
        """
        Valida um lote normalizado.

        Args:
            lot: Lote normalizado

        Returns:
            ValidationResult com status e erros/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []

        # === ERROS BLOQUEANTES ===

        # 1. Erros já detectados na normalização
        if lot.validation_errors:
            errors.extend(lot.validation_errors)

        # 2. id_interno deve existir
        if not lot.id_interno:
            errors.append(RejectionCode.MISSING_ID_INTERNO)

        # 3. Título deve ser válido
        if not lot.titulo or lot.titulo.lower() in ["undefined", "null", "none", ""]:
            errors.append(RejectionCode.INVALID_TITULO)

        # 4. data_leilao obrigatório
        if not lot.data_leilao:
            if RejectionCode.MISSING_DATA_LEILAO not in errors:
                errors.append(RejectionCode.MISSING_DATA_LEILAO)

        # 5. tags obrigatórias
        if not lot.tags:
            if RejectionCode.MISSING_TAGS not in errors:
                errors.append(RejectionCode.MISSING_TAGS)

        # 6. UF válida (se presente)
        if lot.uf and lot.uf not in VALID_UFS:
            errors.append(RejectionCode.INVALID_UF)

        # 7. Leilão expirado (opcional)
        if self.check_expiration and lot.data_leilao:
            try:
                # Parse ISO 8601
                data_str = lot.data_leilao.split("T")[0]
                data_leilao = datetime.strptime(data_str, "%Y-%m-%d")
                if data_leilao.date() < datetime.now().date():
                    errors.append(RejectionCode.EXPIRED_AUCTION)
            except (ValueError, IndexError):
                pass

        # === WARNINGS (não bloqueiam) ===

        if not lot.cidade:
            warnings.append("MISSING_CIDADE")

        if not lot.link_edital:
            warnings.append("MISSING_LINK_EDITAL")

        if not lot.valor_avaliacao:
            warnings.append("MISSING_VALOR")

        # Remove duplicatas
        errors = list(dict.fromkeys(errors))
        warnings = list(dict.fromkeys(warnings))

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

        # Registra estatísticas
        self.stats.record(result)

        return result

    def filter_valid(
        self,
        lots: List[NormalizedAPILot]
    ) -> Tuple[List[NormalizedAPILot], List[Tuple[NormalizedAPILot, ValidationResult]]]:
        """
        Filtra lotes válidos e inválidos.

        Args:
            lots: Lista de lotes normalizados

        Returns:
            Tupla (lotes_validos, lista de (lote, resultado) para quarentena)
        """
        valid: List[NormalizedAPILot] = []
        quarantine: List[Tuple[NormalizedAPILot, ValidationResult]] = []

        for lot in lots:
            result = self.validate(lot)
            if result.is_valid:
                valid.append(lot)
            else:
                quarantine.append((lot, result))

        logger.info(
            f"Validação: {len(valid)} válidos, "
            f"{len(quarantine)} quarentena "
            f"({self.stats.valid_rate:.1f}% taxa de aprovação)"
        )

        if quarantine:
            for code, count in self.stats.top_errors[:5]:
                desc = REJECTION_DESCRIPTIONS.get(code, code)
                logger.info(f"  - {code}: {count} ({desc})")

        return valid, quarantine


# ============================================================================
# VALIDADORES AUXILIARES
# ============================================================================

def validate_api_item(item: Dict) -> ValidationResult:
    """
    Valida item bruto da API antes da normalização.

    Útil para rejeição rápida sem processamento completo.
    """
    errors = []

    # Tipo 3 rejeitado imediatamente
    if item.get("tipo") == 3:
        errors.append(RejectionCode.TIPO_3)

    # Deve ter ID
    if not item.get("id"):
        errors.append(RejectionCode.MISSING_ID_INTERNO)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors
    )


def is_vehicle_category(item: Dict) -> bool:
    """
    Verifica se item é de categoria de veículos.

    Categorias da API leiloesjudiciais:
    - id_categoria=1: Veículos (aceitar)
    - id_categoria=2: Bens Diversos (depende do filtro)
    - id_categoria=3: Imóveis (rejeitar)
    """
    # Verifica pela categoria numérica da API
    id_categoria = item.get("id_categoria")
    if id_categoria is not None:
        # Aceita apenas veículos (1)
        return id_categoria == 1

    # Fallback: verifica pelo texto se id_categoria não disponível
    categoria = (item.get("nm_categoria") or item.get("categoria") or "").lower()
    titulo = (item.get("nm_titulo_lote") or item.get("titulo") or "").lower()

    # Keywords de veículos
    vehicle_keywords = [
        "veiculo", "veículo", "carro", "moto", "caminhao", "caminhão",
        "onibus", "ônibus", "trator", "sucata", "automóvel", "automovel"
    ]

    # Keywords de exclusão
    exclude_keywords = [
        "imovel", "imóvel", "apartamento", "casa", "terreno", "sala",
        "lote urbano", "loja", "galpao", "galpão", "fazenda"
    ]

    # Verifica exclusões
    if any(kw in categoria or kw in titulo for kw in exclude_keywords):
        return False

    # Verifica inclusões
    return any(kw in categoria or kw in titulo for kw in vehicle_keywords)
