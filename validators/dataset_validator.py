from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================
# CONTRATO CANÔNICO (dataset_contract_v1.md) - CONFIG
# ============================================================
# Campos do registro (obrigatórios SIM / NÃO) :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}
REQUIRED_FIELDS: Tuple[str, ...] = (
    "id_interno",
    "municipio",
    "uf",
    "data_leilao",
    "pncp_url",
    "data_atualizacao",
    "titulo",
    "descricao",
    "orgao",
    "n_edital",
    "objeto_resumido",
    "tags",
    "valor_estimado",
    "tipo_leilao",
)

OPTIONAL_FIELDS: Tuple[str, ...] = (
    "leiloeiro_url",  # NÃO obrigatório :contentReference[oaicite:4]{index=4}
)

# Regra de vendabilidade (campos que precisam existir para vender) :contentReference[oaicite:5]{index=5}
SELLABLE_REQUIRED_FIELDS: Tuple[str, ...] = (
    "data_leilao",
    "pncp_url",
    "municipio",
    "uf",
    "id_interno",
    "titulo",
    "descricao",
    "orgao",
    "n_edital",
    "tags",
    "valor_estimado",
    "data_publicacao",  # aparece na regra de vendabilidade, mesmo não listado na tabela de campos :contentReference[oaicite:6]{index=6}
)

# Datas devem ser DD-MM-YYYY (com hífen) e NÃO pode ter barra. :contentReference[oaicite:7]{index=7}
DATE_FORMAT = "%d-%m-%Y"
PROHIBITED_DATE_SEPARATORS: Tuple[str, ...] = ("/",)

# URLs: devem começar com https:// OU http:// e www. vira https://www. :contentReference[oaicite:8]{index=8}
ALLOWED_URL_SCHEMES: Tuple[str, ...] = ("https://", "http://")
ALLOW_WWW_WITHOUT_SCHEME: bool = True

# domínios .net.br válidos; "COMEMORA" NÃO é URL :contentReference[oaicite:9]{index=9}
ALLOW_NET_BR: bool = True
NON_URL_TOKENS: Tuple[str, ...] = ("COMEMORA",)

# Campos que são URLs (no contrato: pncp_url SIM, leiloeiro_url NÃO obrigatório)
URL_FIELDS: Tuple[str, ...] = ("pncp_url", "leiloeiro_url")

# Regra do tags: "SEM CLASSIFICAÇÃO -> (NESSE SE = RETIRE)" :contentReference[oaicite:10]{index=10}
TAG_FORBIDDEN_TOKEN = "SEM CLASSIFICAÇÃO"


_HOST_RE = re.compile(
    r"^([a-z0-9-]+\.)+[a-z]{2,}$",
    flags=re.IGNORECASE,
)


# ============================================================
# MODELOS: status, erros, resultado padrão
# ============================================================

class RecordStatus(str, Enum):
    DRAFT = "draft"            # extraído mas incompleto :contentReference[oaicite:11]{index=11}
    VALID = "valid"            # pronto para uso :contentReference[oaicite:12]{index=12}
    NOT_SELLABLE = "not_sellable"  # sem data ou regra crítica :contentReference[oaicite:13]{index=13}
    REJECTED = "rejected"      # lixo :contentReference[oaicite:14]{index=14}


class ErrorCode(str, Enum):
    # Campos obrigatórios
    MISSING_REQUIRED_FIELD = "missing_required_field"

    # Formato de data
    INVALID_DATE_FORMAT = "invalid_date_format"

    # URLs
    INVALID_URL = "invalid_url"
    TEXT_AS_URL = "text_as_url"
    URL_NORMALIZED = "url_normalized"  # Info, não erro

    # Tags
    TAGS_NORMALIZED = "tags_normalized"  # Info, não erro
    TAGS_EMPTY_AFTER_NORMALIZATION = "tags_empty_after_normalization"

    # Brief 1.2: Códigos adicionais para quarentena
    INVALID_UF = "invalid_uf"
    BELOW_MINIMUM_SCORE = "below_minimum_score"
    REJECTED_CATEGORY = "rejected_category"  # ex: imóvel sem veículo
    DUPLICATE_RECORD = "duplicate_record"
    EXTRACTION_ERROR = "extraction_error"  # PDF quebrado, etc
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ValidationError:
    code: ErrorCode
    field: str
    message: str


@dataclass
class ValidationResult:
    status: RecordStatus
    errors: List[ValidationError] = field(default_factory=list)
    normalized_record: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        # “válido” = pronto para uso no dashboard/dataset principal :contentReference[oaicite:15]{index=15}
        return self.status == RecordStatus.VALID


# ============================================================
# RELATÓRIO DE QUALIDADE POR EXECUÇÃO - BRIEF 1.3
# ============================================================

@dataclass
class QualityReport:
    """
    Relatório de qualidade por execução (run_id).

    BRIEF 1.3: Contém métricas agregadas, taxas e top 10 motivos de rejeição.
    """
    run_id: str

    # Timestamps (Brief 1.3)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0

    # Contagens
    executed_total: int = 0
    valid_count: int = 0
    draft_count: int = 0
    not_sellable_count: int = 0
    rejected_count: int = 0

    # Contagem de erros por código
    error_counts: Dict[str, int] = field(default_factory=dict)

    # Metadados extras
    municipio_incomplete_count: int = 0

    # Tempos por etapa (opcional, Brief 1.3)
    tempo_extracao_seconds: float = 0.0
    tempo_validacao_seconds: float = 0.0
    tempo_persistencia_seconds: float = 0.0

    def __post_init__(self):
        """Registra timestamp de início automaticamente."""
        if self.started_at is None:
            self.started_at = datetime.utcnow().isoformat() + "Z"

    def bump_error(self, code: ErrorCode) -> None:
        """Incrementa contador de um código de erro."""
        k = code.value
        self.error_counts[k] = self.error_counts.get(k, 0) + 1

    def register(self, result: ValidationResult) -> None:
        """Registra resultado de validação no relatório."""
        self.executed_total += 1

        if result.status == RecordStatus.VALID:
            self.valid_count += 1
        elif result.status == RecordStatus.DRAFT:
            self.draft_count += 1
        elif result.status == RecordStatus.NOT_SELLABLE:
            self.not_sellable_count += 1
        else:
            self.rejected_count += 1

        for err in result.errors:
            self.bump_error(err.code)

    def finalize(self) -> None:
        """Finaliza o relatório com timestamp de fim e duração."""
        self.finished_at = datetime.utcnow().isoformat() + "Z"
        if self.started_at:
            try:
                start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(self.finished_at.replace("Z", "+00:00"))
                self.duration_seconds = (end - start).total_seconds()
            except (ValueError, TypeError):
                pass

    # ========== Propriedades calculadas (Brief 1.3) ==========

    @property
    def total_quarentena(self) -> int:
        """Total de registros em quarentena (não válidos)."""
        return self.draft_count + self.not_sellable_count + self.rejected_count

    @property
    def taxa_validos_percent(self) -> float:
        """Percentual de registros válidos."""
        if self.executed_total == 0:
            return 0.0
        return round(self.valid_count / self.executed_total * 100, 2)

    @property
    def taxa_quarentena_percent(self) -> float:
        """Percentual de registros em quarentena."""
        if self.executed_total == 0:
            return 0.0
        return round(self.total_quarentena / self.executed_total * 100, 2)

    @property
    def top_reason_codes(self) -> List[Dict[str, Any]]:
        """Top 10 códigos de erro ordenados por frequência."""
        sorted_errors = sorted(
            self.error_counts.items(),
            key=lambda x: (-x[1], x[0])
        )
        return [{"code": code, "count": count} for code, count in sorted_errors[:10]]

    # ========== Serialização ==========

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário com todos os campos do Brief 1.3."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,

            # Contagens
            "total_processados": self.executed_total,
            "total_validos": self.valid_count,
            "total_quarentena": self.total_quarentena,
            "total_draft": self.draft_count,
            "total_not_sellable": self.not_sellable_count,
            "total_rejected": self.rejected_count,

            # Taxas
            "taxa_validos_percent": self.taxa_validos_percent,
            "taxa_quarentena_percent": self.taxa_quarentena_percent,

            # Top motivos
            "top_reason_codes": self.top_reason_codes,

            # Detalhes completos
            "error_counts": self.error_counts,

            # Tempos por etapa
            "tempo_extracao_seconds": self.tempo_extracao_seconds,
            "tempo_validacao_seconds": self.tempo_validacao_seconds,
            "tempo_persistencia_seconds": self.tempo_persistencia_seconds,

            # Extras
            "municipio_incomplete_count": self.municipio_incomplete_count,
        }

    def to_json(self) -> str:
        """Serializa para JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def print_summary(self) -> None:
        """Imprime resumo no console."""
        print("=" * 60)
        print(f"RELATORIO DE QUALIDADE - {self.run_id}")
        print("=" * 60)
        print(f"Processados:  {self.executed_total}")
        print(f"Validos:      {self.valid_count} ({self.taxa_validos_percent}%)")
        print(f"Quarentena:   {self.total_quarentena} ({self.taxa_quarentena_percent}%)")
        print(f"  - Draft:        {self.draft_count}")
        print(f"  - Not sellable: {self.not_sellable_count}")
        print(f"  - Rejected:     {self.rejected_count}")
        print("-" * 60)
        if self.duration_seconds > 0:
            print(f"Duracao:      {self.duration_seconds:.2f}s")
        if self.top_reason_codes:
            print("Top motivos de quarentena:")
            for item in self.top_reason_codes[:5]:
                print(f"  - {item['code']}: {item['count']}")
        print("=" * 60)


def new_run_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}_{uuid.uuid4().hex[:12]}"


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def validate_record(record: Dict[str, Any]) -> ValidationResult:
    """
    Implementa o contrato:
    - Datas DD-MM-YYYY (barra é proibido) :contentReference[oaicite:16]{index=16}
    - URLs http(s)://; www. vira https://www. :contentReference[oaicite:17]{index=17}
    - .net.br válido; "COMEMORA" NÃO é URL :contentReference[oaicite:18]{index=18}
    - Estados: draft/valid/not_sellable/rejected :contentReference[oaicite:19]{index=19}
    """
    raw = record or {}
    normalized = dict(raw)
    errors: List[ValidationError] = []

    _normalize_and_validate_tags(normalized, errors)
    _normalize_and_validate_dates(normalized, errors)
    _normalize_and_validate_urls(normalized, errors)
    _validate_required_fields(normalized, errors)

    status = _decide_final_status(normalized, errors)
    return ValidationResult(status=status, errors=errors, normalized_record=normalized)


# ============================================================
# VALIDAÇÕES PEQUENAS (uma responsabilidade por vez)
# ============================================================

def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _validate_required_fields(record: Dict[str, Any], errors: List[ValidationError]) -> None:
    # “Obrigatório? SIM” na tabela de campos :contentReference[oaicite:20]{index=20} :contentReference[oaicite:21]{index=21}
    for field_name in REQUIRED_FIELDS:
        if _is_missing(record.get(field_name)):
            errors.append(
                ValidationError(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    field=field_name,
                    message=f"Campo obrigatório ausente: {field_name}",
                )
            )

    # data_publicacao aparece na regra de vendabilidade (não na tabela de campos)
    # então: não marca como “obrigatório do schema”, mas vai pesar em vendabilidade.
    # :contentReference[oaicite:22]{index=22}


def _normalize_and_validate_dates(record: Dict[str, Any], errors: List[ValidationError]) -> None:
    # Campos de data que aparecem no contrato: data_leilao, data_atualizacao (+ data_publicacao pela vendabilidade)
    for field_name in ("data_leilao", "data_atualizacao", "data_publicacao"):
        if field_name not in record:
            continue

        v = record.get(field_name)
        if _is_missing(v):
            continue

        if isinstance(v, datetime):
            v = v.date()
        if isinstance(v, date) and not isinstance(v, datetime):
            record[field_name] = v.strftime(DATE_FORMAT)
            continue

        if not isinstance(v, str):
            errors.append(
                ValidationError(
                    code=ErrorCode.INVALID_DATE_FORMAT,
                    field=field_name,
                    message=f"{field_name} deve ser string DD-MM-YYYY",
                )
            )
            continue

        s = v.strip()

        # barra é proibida, não “normaliza”, reprova. :contentReference[oaicite:23]{index=23}
        if any(sep in s for sep in PROHIBITED_DATE_SEPARATORS):
            errors.append(
                ValidationError(
                    code=ErrorCode.INVALID_DATE_FORMAT,
                    field=field_name,
                    message=f"{field_name} usa separador proibido (use DD-MM-YYYY)",
                )
            )
            continue

        try:
            parsed = datetime.strptime(s, DATE_FORMAT).date()
            record[field_name] = parsed.strftime(DATE_FORMAT)
        except ValueError:
            errors.append(
                ValidationError(
                    code=ErrorCode.INVALID_DATE_FORMAT,
                    field=field_name,
                    message=f"{field_name} inválida (esperado DD-MM-YYYY)",
                )
            )


def _normalize_and_validate_urls(record: Dict[str, Any], errors: List[ValidationError]) -> None:
    for field_name in URL_FIELDS:
        if field_name not in record:
            continue

        v = record.get(field_name)

        # pncp_url é obrigatório; leiloeiro_url não. :contentReference[oaicite:24]{index=24}
        if _is_missing(v):
            continue

        if not isinstance(v, str):
            errors.append(
                ValidationError(
                    code=ErrorCode.INVALID_URL,
                    field=field_name,
                    message=f"{field_name} não é string",
                )
            )
            continue

        s = v.strip()

        if s.upper() in NON_URL_TOKENS:
            errors.append(
                ValidationError(
                    code=ErrorCode.TEXT_AS_URL,
                    field=field_name,
                    message=f"{field_name} parece texto, não URL: {s}",
                )
            )
            continue

        normalized, changed = _normalize_url(s)
        record[field_name] = normalized

        if changed:
            errors.append(
                ValidationError(
                    code=ErrorCode.URL_NORMALIZED,
                    field=field_name,
                    message=f"{field_name} normalizada (www. -> https://www. ou http->https não aplicado aqui)",
                )
            )

        if not _is_valid_contract_url(normalized):
            errors.append(
                ValidationError(
                    code=ErrorCode.INVALID_URL,
                    field=field_name,
                    message=f"{field_name} inválida pelo contrato: {normalized}",
                )
            )


def _normalize_url(s: str) -> Tuple[str, bool]:
    if ALLOW_WWW_WITHOUT_SCHEME and s.lower().startswith("www."):
        # contrato: www. vira https://www. :contentReference[oaicite:25]{index=25}
        return f"https://{s}", True
    return s, False


def _is_valid_contract_url(s: str) -> bool:
    sl = s.lower()
    if not any(sl.startswith(p) for p in ALLOWED_URL_SCHEMES):
        return False

    # extrai host
    try:
        after_scheme = s.split("://", 1)[1]
    except IndexError:
        return False

    host = after_scheme.split("/", 1)[0].strip()
    if not host or "." not in host:
        return False

    if not _HOST_RE.match(host):
        return False

    # .net.br explicitamente permitido (e não pode ser rejeitado por regex ruim) :contentReference[oaicite:26]{index=26}
    if ALLOW_NET_BR and host.lower().endswith(".net.br"):
        return True

    return True


def _normalize_and_validate_tags(record: Dict[str, Any], errors: List[ValidationError]) -> None:
    if "tags" not in record:
        return

    v = record.get("tags")
    if _is_missing(v):
        return

    if not isinstance(v, str):
        # não “repara” tag não-string; só marca e deixa decisão final cuidar
        errors.append(
            ValidationError(
                code=ErrorCode.MISSING_REQUIRED_FIELD,
                field="tags",
                message="tags existe mas não é string",
            )
        )
        return

    original = v
    parts = [p.strip() for p in v.split(",")]
    cleaned = [p for p in parts if p and p.upper() != TAG_FORBIDDEN_TOKEN.upper()]

    if cleaned != parts:
        record["tags"] = ", ".join(cleaned)
        errors.append(
            ValidationError(
                code=ErrorCode.TAGS_NORMALIZED,
                field="tags",
                message='Token "SEM CLASSIFICAÇÃO" removido das tags',
            )
        )

    if _is_missing(record.get("tags")):
        errors.append(
            ValidationError(
                code=ErrorCode.TAGS_EMPTY_AFTER_NORMALIZATION,
                field="tags",
                message="tags ficou vazia após normalização",
            )
        )


# ============================================================
# DECISÃO FINAL (status)
# ============================================================

def _decide_final_status(record: Dict[str, Any], errors: List[ValidationError]) -> RecordStatus:
    """
    Política alinhada ao contrato:
    - rejected = lixo (formato inválido crítico, URL inválida em campo crítico, etc.)
    - not_sellable = sem data OU regra crítica (vendabilidade falhou) :contentReference[oaicite:27]{index=27}
    - draft = extraído mas incompleto (faltou obrigatório “SIM” mas não é regra crítica de vendabilidade)
    - valid = pronto para uso (dashboard só usa valid) :contentReference[oaicite:28]{index=28}
    """

    # 1) rejected: falhas críticas de formato (datas inválidas / URL inválida em pncp_url)
    if any(e.code == ErrorCode.INVALID_DATE_FORMAT for e in errors):
        return RecordStatus.REJECTED

    # URL inválida em pncp_url (que é obrigatório SIM) => rejected :contentReference[oaicite:29]{index=29}
    if any(e.code == ErrorCode.INVALID_URL and e.field == "pncp_url" for e in errors):
        return RecordStatus.REJECTED

    # Texto como URL em pncp_url => rejected
    if any(e.code == ErrorCode.TEXT_AS_URL and e.field == "pncp_url" for e in errors):
        return RecordStatus.REJECTED

    # 2) not_sellable: falhou vendabilidade (campos listados na regra) :contentReference[oaicite:30]{index=30}
    missing_sellable = [
        f for f in SELLABLE_REQUIRED_FIELDS if _is_missing(record.get(f))
    ]
    if missing_sellable:
        return RecordStatus.NOT_SELLABLE

    # 3) draft: faltou algum campo “SIM” do schema (mas não caiu em not_sellable/rejected)
    missing_required = [
        f for f in REQUIRED_FIELDS if _is_missing(record.get(f))
    ]
    if missing_required:
        return RecordStatus.DRAFT

    # 4) valid: tudo certo
    return RecordStatus.VALID


# ============================================================
# QUARENTENA (payload para dataset_rejections)
# ============================================================

def build_rejection_row(
    run_id: str,
    raw_record: Dict[str, Any],
    result: ValidationResult,
) -> Dict[str, Any]:
    """
    Para inserir no Supabase (tabela dataset_rejections).
    Entram aqui: draft / not_sellable / rejected. valid NÃO entra.
    """
    return {
        "run_id": run_id,
        "id_interno": (str(raw_record.get("id_interno") or "")[:255]) or None,
        "status": result.status.value,
        "errors": [asdict(e) for e in result.errors],
        "raw_record": raw_record,
        "normalized_record": result.normalized_record,
    }


# ============================================================
# EXECUÇÃO EM LOTE (gera relatório)
# ============================================================

def validate_records_with_report(
    records: Iterable[Dict[str, Any]],
    run_id: Optional[str] = None,
) -> Tuple[str, QualityReport, List[Tuple[Dict[str, Any], ValidationResult]]]:
    rid = run_id or new_run_id()
    report = QualityReport(run_id=rid)
    out: List[Tuple[Dict[str, Any], ValidationResult]] = []

    for rec in records:
        res = validate_record(rec)
        report.register(res)
        out.append((rec, res))

    return rid, report, out
