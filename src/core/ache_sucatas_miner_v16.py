from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from validators.dataset_validator import (
        QualityReport,
        RecordStatus,
        ValidationResult,
        build_rejection_row,
        new_run_id,
        validate_record,
    )
except Exception:
    from dataclasses import dataclass as _dc
    from enum import Enum as _Enum

    class RecordStatus(str, _Enum):
        VALID = "valid"
        NOT_SELLABLE = "not_sellable"
        REJECTED = "rejected"

    @_dc
    class ValidationResult:
        status: RecordStatus
        normalized_record: Dict[str, Any]
        errors: List[str]
        warnings: List[str]

    class QualityReport:
        def __init__(self) -> None:
            self.results: List[ValidationResult] = []

        def register(self, result: ValidationResult) -> None:
            self.results.append(result)

    def new_run_id() -> str:
        return datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")

    def build_rejection_row(*, run_id: str, raw_record: Dict[str, Any], result: ValidationResult) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "status": result.status.value,
            "errors": result.errors,
            "warnings": result.warnings,
            "raw_record": raw_record,
            "normalized_record": result.normalized_record,
        }

    def validate_record(record: Dict[str, Any]) -> ValidationResult:
        required = [
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
            "data_publicacao",
        ]

        errors: List[str] = []
        warnings: List[str] = []
        normalized = dict(record)

        for k in required:
            if not normalized.get(k):
                errors.append(f"missing_required:{k}")

        def _is_dd_mm_yyyy(v: str) -> bool:
            return bool(re.match(r"^\d{2}-\d{2}-\d{4}$", v or ""))

        for dk in ["data_atualizacao", "data_publicacao", "data_leilao"]:
            if normalized.get(dk) and not _is_dd_mm_yyyy(str(normalized[dk])):
                errors.append(f"invalid_date_format:{dk}")

        for uk in ["pncp_url", "leiloeiro_url"]:
            if normalized.get(uk):
                u = str(normalized[uk]).strip()
                if u and not re.match(r"^https?://", u, re.IGNORECASE):
                    errors.append(f"url_missing_protocol:{uk}")
                if re.search(r"\bCOMEMORA\b", u, re.IGNORECASE):
                    errors.append(f"url_is_word_not_url:{uk}")

        if errors:
            if any(e == "missing_required:data_leilao" for e in errors):
                status = RecordStatus.NOT_SELLABLE
            else:
                status = RecordStatus.REJECTED
        else:
            status = RecordStatus.VALID

        return ValidationResult(status=status, normalized_record=normalized, errors=errors, warnings=warnings)


load_dotenv()


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra") and isinstance(getattr(record, "extra"), dict):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


def _logger() -> logging.Logger:
    logger = logging.getLogger("AcheSucatasMiner")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def normalize_text(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return value.strip()


def normalize_upper(value: str) -> str:
    return normalize_text(value).upper()


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(tz=None).replace(tzinfo=None)
    except Exception:
        return None


def format_dd_mm_yyyy(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.strftime("%d-%m-%Y")


def stable_id_interno(municipio: str, processo: str, data_leilao_ddmmyyyy: str) -> str:
    base = f"{normalize_upper(municipio)}|{normalize_text(processo)}|{data_leilao_ddmmyyyy}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def looks_like_word_not_url(value: str) -> bool:
    if not value:
        return True
    if re.fullmatch(r"[A-Za-zÀ-ÿ]+", value.strip()) and len(value.strip()) >= 6:
        return True
    if re.search(r"\bCOMEMORA\b", value, re.IGNORECASE):
        return True
    return False


def normalize_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = value.strip()
    if not raw or looks_like_word_not_url(raw):
        return None
    if raw.lower().startswith("www."):
        raw = "https://" + raw
    if re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(\.[A-Za-z]{2})?(/|$)", raw) and not re.match(
        r"^https?://", raw, re.IGNORECASE
    ):
        raw = "https://" + raw
    raw = re.sub(r"\s+", "", raw)
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        return None
    return raw


def extract_first_pdf_url(text: str) -> Optional[str]:
    if not text:
        return None
    candidates = re.findall(r"(https?://[^\s)>\]]+|www\.[^\s)>\]]+)", text, flags=re.IGNORECASE)
    for c in candidates:
        u = normalize_url(c)
        if u:
            return u
    return None


def parse_brl_money(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(
        r"(?:VALOR\s+TOTAL\s+ESTIMADO(?:\s+DO\s+LEIL[AÃ]O)?\s*)?(R\$\s*[\d\.\u00A0]+,\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(r"(R\$\s*[\d\.\u00A0]+,\d{2})", text, flags=re.IGNORECASE)
    if not m:
        return None
    return normalize_text(m.group(1)).replace("\u00A0", " ")


def infer_tipo_leilao(text: str) -> Optional[str]:
    if not text:
        return None
    t = normalize_upper(text)
    presencial = bool(re.search(r"\bPRESENCIAL\b", t))
    online = bool(re.search(r"\b(ONLINE|ELETRONICO|ELETRÔNICO|VIRTUAL)\b", t))
    if presencial and online:
        return "1+2"
    if presencial:
        return "1"
    if online:
        return "2"
    return None


def extract_descricao_3_linhas(text: str) -> Optional[str]:
    if not text:
        return None
    lines = [normalize_text(l) for l in text.splitlines()]
    lines = [l for l in lines if l]
    if not lines:
        return None
    return "\n".join(lines[:3])


def extract_objeto_resumido(text: str) -> Optional[str]:
    if not text:
        return None
    t = normalize_upper(text)
    brands = [
        "FIAT",
        "FORD",
        "CHEVROLET",
        "VOLKSWAGEN",
        "VW",
        "RENAULT",
        "HYUNDAI",
        "TOYOTA",
        "HONDA",
        "NISSAN",
        "YAMAHA",
        "SUZUKI",
        "IVECO",
        "MERCEDES",
        "SCANIA",
        "VOLVO",
        "AGRALE",
        "MARCOPOLO",
    ]
    found: List[str] = []
    for b in brands:
        if re.search(rf"\b{re.escape(b)}\b", t):
            found.append(b)
    if not found:
        return None
    return ", ".join(sorted(set(found)))


def extract_tags(text: str) -> Optional[str]:
    if not text:
        return None
    t = normalize_upper(text)
    tags: List[str] = []
    if re.search(r"\bSUCATA\b", t):
        tags.append("SUCATA")
    if re.search(r"\bDOCUMENTAD[OA]\b", t):
        tags.append("DOCUMENTADO")
    if re.search(r"\bSEM\s+DOCUMENT", t):
        tags.append("SEM DOCUMENTO")
    if re.search(r"\bVE[IÍ]CUL", t):
        tags.append("VEICULOS")
    if not tags:
        return None
    return ", ".join(tags)


def build_pncp_public_url(numero_controle_pncp: Optional[str]) -> Optional[str]:
    if not numero_controle_pncp:
        return None
    numero = normalize_text(numero_controle_pncp)
    if not numero:
        return None
    return f"https://pncp.gov.br/app/editais/{numero}"


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int, reset_timeout_seconds: int) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._reset_timeout_seconds = max(1, reset_timeout_seconds)
        self._failures = 0
        self._opened_at: Optional[float] = None

    def allow_request(self) -> bool:
        if self._opened_at is None:
            return True
        if (time.time() - self._opened_at) >= self._reset_timeout_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._opened_at = time.time()


def backoff_sleep_seconds(attempt: int, base: float, cap: float) -> float:
    exp = min(cap, base * (2**attempt))
    jitter = random.uniform(0.85, 1.15)
    return max(0.1, exp * jitter)


@dataclass
class MinerConfig:
    search_endpoint: str = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    details_endpoint_template: str = "https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"
    files_endpoint_template: str = "https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"

    user_agent: str = "AcheSucatasMiner/16.4"
    timeout_seconds: float = 30.0

    rate_limit_seconds: float = 0.6
    max_retries: int = 5
    backoff_base: float = 0.5
    backoff_cap: float = 15.0

    breaker_failure_threshold: int = 8
    breaker_reset_timeout_seconds: int = 60

    dias_lookback: int = 30
    paginas_por_termo: int = 3
    tamanho_pagina: int = 20
    sleep_entre_paginas: float = 0.4
    run_limit: int = 0

    search_terms: List[str] = field(default_factory=list)

    enable_supabase: bool = True
    supabase_url: str = ""
    supabase_key: str = ""


class PNCPClient:
    _singleton: Optional["PNCPClient"] = None

    def __init__(self, cfg: MinerConfig, logger: logging.Logger) -> None:
        self._cfg = cfg
        self._logger = logger
        self._client = httpx.Client(
            timeout=httpx.Timeout(cfg.timeout_seconds),
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
        )
        self._last_request_ts = 0.0
        self._breaker = CircuitBreaker(
            failure_threshold=cfg.breaker_failure_threshold,
            reset_timeout_seconds=cfg.breaker_reset_timeout_seconds,
        )

    @classmethod
    def get(cls, cfg: MinerConfig, logger: logging.Logger) -> "PNCPClient":
        if cls._singleton is None:
            cls._singleton = PNCPClient(cfg, logger)
        return cls._singleton

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._cfg.rate_limit_seconds:
            time.sleep(self._cfg.rate_limit_seconds - elapsed)

    def _request_json(self, method: str, url: str, *, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        if not self._breaker.allow_request():
            self._logger.warning("pncp_circuit_open", extra={"extra": {"url": url}})
            return None

        for attempt in range(self._cfg.max_retries + 1):
            self._throttle()
            self._last_request_ts = time.time()
            try:
                resp = self._client.request(method, url, params=params)
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate_limited", request=resp.request, response=resp)
                resp.raise_for_status()
                self._breaker.record_success()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                self._breaker.record_failure()
                if attempt >= self._cfg.max_retries:
                    self._logger.error("pncp_network_error", extra={"extra": {"url": url, "err": str(e)}})
                    return None
                time.sleep(backoff_sleep_seconds(attempt, self._cfg.backoff_base, self._cfg.backoff_cap))
            except httpx.HTTPStatusError as e:
                self._breaker.record_failure()
                status = getattr(e.response, "status_code", None)
                if attempt >= self._cfg.max_retries or (status is not None and 400 <= status < 500 and status != 429):
                    self._logger.error("pncp_http_error", extra={"extra": {"url": url, "status": status}})
                    return None
                time.sleep(backoff_sleep_seconds(attempt, self._cfg.backoff_base, self._cfg.backoff_cap))
            except Exception as e:
                self._breaker.record_failure()
                self._logger.error("pncp_unexpected_error", extra={"extra": {"url": url, "err": str(e)}})
                return None

        return None

    def _request_bytes(self, url: str) -> Optional[bytes]:
        if not self._breaker.allow_request():
            self._logger.warning("pncp_circuit_open", extra={"extra": {"url": url}})
            return None

        for attempt in range(self._cfg.max_retries + 1):
            self._throttle()
            self._last_request_ts = time.time()
            try:
                resp = self._client.get(url)
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate_limited", request=resp.request, response=resp)
                resp.raise_for_status()
                self._breaker.record_success()
                return resp.content
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                self._breaker.record_failure()
                if attempt >= self._cfg.max_retries:
                    self._logger.error("pncp_network_error", extra={"extra": {"url": url, "err": str(e)}})
                    return None
                time.sleep(backoff_sleep_seconds(attempt, self._cfg.backoff_base, self._cfg.backoff_cap))
            except httpx.HTTPStatusError as e:
                self._breaker.record_failure()
                status = getattr(e.response, "status_code", None)
                if attempt >= self._cfg.max_retries or (status is not None and 400 <= status < 500 and status != 429):
                    self._logger.error("pncp_http_error", extra={"extra": {"url": url, "status": status}})
                    return None
                time.sleep(backoff_sleep_seconds(attempt, self._cfg.backoff_base, self._cfg.backoff_cap))
            except Exception as e:
                self._breaker.record_failure()
                self._logger.error("pncp_unexpected_error", extra={"extra": {"url": url, "err": str(e)}})
                return None

        return None

    def search_publicacoes(self, *, termo: str, pagina: int, data_inicial: str, data_final: str, tamanho: int) -> List[Dict[str, Any]]:
        params = {
            "pagina": pagina,
            "tamanhoPagina": tamanho,
            "termo": termo,
            "dataInicial": data_inicial,
            "dataFinal": data_final,
        }
        data = self._request_json("GET", self._cfg.search_endpoint, params=params)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return [x for x in data["data"] if isinstance(x, dict)]
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []

    def details(self, *, cnpj: str, ano: int, sequencial: int) -> Optional[Dict[str, Any]]:
        url = self._cfg.details_endpoint_template.format(cnpj=cnpj, ano=ano, sequencial=sequencial)
        data = self._request_json("GET", url)
        return data if isinstance(data, dict) else None

    def arquivos(self, *, cnpj: str, ano: int, sequencial: int) -> List[Dict[str, Any]]:
        url = self._cfg.files_endpoint_template.format(cnpj=cnpj, ano=ano, sequencial=sequencial)
        data = self._request_json("GET", url)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return [x for x in data["data"] if isinstance(x, dict)]
        return []

    def download(self, url: str) -> Optional[bytes]:
        return self._request_bytes(url)


def extract_pdf_text(pdf_bytes: bytes, logger: logging.Logger) -> str:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception:
        logger.warning("pdf_extract_disabled_missing_pypdfium2")
        return ""
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        out: List[str] = []
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            out.append(textpage.get_text_range())
        return "\n".join(out)
    except Exception as e:
        logger.error("pdf_extract_failed", extra={"extra": {"err": str(e)}})
        return ""


class SupabaseRepository:
    def __init__(self, cfg: MinerConfig, logger: logging.Logger) -> None:
        self._logger = logger
        self._enabled = False
        self._client: Any = None

        if not cfg.enable_supabase:
            return
        if not cfg.supabase_url or not cfg.supabase_key:
            self._logger.warning("supabase_disabled_missing_env")
            return
        try:
            from supabase import create_client  # type: ignore

            self._client = create_client(cfg.supabase_url, cfg.supabase_key)
            self._enabled = True
        except Exception as e:
            self._logger.error("supabase_init_failed", extra={"extra": {"err": str(e)}})
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def upsert_edital(self, edital_db: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        try:
            res = self._client.table("editais_leilao").upsert(edital_db).execute()
            return bool(getattr(res, "data", None) is not None)
        except Exception as e:
            self._logger.error("supabase_upsert_failed", extra={"extra": {"err": str(e)}})
            return False

    def inserir_quarentena(self, rejection_row: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        try:
            res = self._client.table("editais_quarentena").insert(rejection_row).execute()
            return bool(getattr(res, "data", None) is not None)
        except Exception as e:
            self._logger.error("supabase_quarantine_insert_failed", extra={"extra": {"err": str(e)}})
            return False

    def iniciar_execucao(self, cfg: MinerConfig) -> Optional[int]:
        if not self.enabled:
            return None
        try:
            payload = {
                "started_at": datetime.utcnow().isoformat(),
                "config": {
                    "dias_lookback": cfg.dias_lookback,
                    "paginas_por_termo": cfg.paginas_por_termo,
                    "tamanho_pagina": cfg.tamanho_pagina,
                },
            }
            res = self._client.table("miner_execucoes").insert(payload).execute()
            if getattr(res, "data", None):
                return res.data[0].get("id")
            return None
        except Exception as e:
            self._logger.error("supabase_exec_start_failed", extra={"extra": {"err": str(e)}})
            return None

    def finalizar_execucao(self, exec_id: Optional[int], stats: Dict[str, Any]) -> None:
        if not self.enabled or not exec_id:
            return
        try:
            payload = {"finished_at": datetime.utcnow().isoformat(), "stats": stats}
            self._client.table("miner_execucoes").update(payload).eq("id", exec_id).execute()
        except Exception as e:
            self._logger.error("supabase_exec_finish_failed", extra={"extra": {"err": str(e)}})


def pncp_keys(item: Dict[str, Any]) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    orgao = item.get("orgaoEntidade") if isinstance(item.get("orgaoEntidade"), dict) else {}
    cnpj = normalize_text(str(orgao.get("cnpj") or "")).replace(".", "").replace("/", "").replace("-", "")
    ano = item.get("anoCompra")
    sequencial = item.get("sequencialCompra")
    numero_controle = item.get("numeroControlePNCP") or item.get("numeroControlePncp")
    cnpj_out = cnpj if cnpj else None
    ano_out = int(ano) if isinstance(ano, int) or (isinstance(ano, str) and ano.isdigit()) else None
    seq_out = int(sequencial) if isinstance(sequencial, int) or (isinstance(sequencial, str) and str(sequencial).isdigit()) else None
    return cnpj_out, ano_out, seq_out, normalize_text(str(numero_controle or "")) or None


def pick_n_edital(item: Dict[str, Any]) -> Optional[str]:
    v = normalize_text(str(item.get("numeroCompra") or "")).strip()
    if v:
        return v
    v = normalize_text(str(item.get("numeroControlePNCP") or item.get("numeroControlePncp") or "")).strip()
    if v:
        return v
    v = normalize_text(str(item.get("processo") or "")).strip()
    return v or None


def pick_valor_estimado(item: Dict[str, Any]) -> Optional[str]:
    v = item.get("valorTotalEstimado")
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return f"{v:.2f}"
    s = normalize_text(str(v)).strip()
    return s or None


class Miner:
    def __init__(self, cfg: MinerConfig) -> None:
        self._cfg = cfg
        self._log = _logger()
        self._pncp = PNCPClient.get(cfg, self._log)
        self._repo = SupabaseRepository(cfg, self._log)
        self._run_id = new_run_id()
        self._quality = QualityReport()
        self._stats: Dict[str, Any] = {
            "editais_encontrados": 0,
            "editais_processados": 0,
            "editais_validos": 0,
            "editais_quarentena": 0,
            "pdf_baixados": 0,
            "pdf_extraidos": 0,
            "erros": 0,
            "details_calls": 0,
        }

    def _periodo(self) -> Tuple[str, str]:
        end = datetime.utcnow().date()
        start = (datetime.utcnow() - timedelta(days=self._cfg.dias_lookback)).date()
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _enrich_with_details_if_needed(self, base: Dict[str, Any], cnpj: Optional[str], ano: Optional[int], seq: Optional[int]) -> Dict[str, Any]:
        need = any(
            base.get(k) in (None, "", 0)
            for k in ["dataAberturaProposta", "valorTotalEstimado", "dataAtualizacao", "dataPublicacaoPncp", "numeroCompra"]
        )
        if not need or not (cnpj and ano and seq):
            return base
        details = self._pncp.details(cnpj=cnpj, ano=ano, sequencial=seq)
        self._stats["details_calls"] += 1
        if not details:
            return base
        merged = dict(base)
        for k, v in details.items():
            if merged.get(k) in (None, "", 0) and v not in (None, "", 0):
                merged[k] = v
        return merged

    def _download_pdf_text(self, cnpj: str, ano: int, seq: int) -> Tuple[str, Optional[str]]:
        arquivos = self._pncp.arquivos(cnpj=cnpj, ano=ano, sequencial=seq)
        if not arquivos:
            return "", None

        pdf_url: Optional[str] = None
        pdf_text: str = ""

        for a in arquivos:
            url = normalize_url(a.get("url") if isinstance(a.get("url"), str) else None)
            if not url:
                continue
            if pdf_url:
                break
            content = self._pncp.download(url)
            if not content:
                continue
            if not content.startswith(b"%PDF"):
                continue
            self._stats["pdf_baixados"] += 1
            pdf_url = url
            pdf_text = extract_pdf_text(content, self._log)
            if pdf_text:
                self._stats["pdf_extraidos"] += 1

        return pdf_text, pdf_url

    def _build_edital_db(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cnpj, ano, seq, numero_controle = pncp_keys(item)
        enriched = self._enrich_with_details_if_needed(item, cnpj, ano, seq)

        municipio = normalize_text(
            str(
                (enriched.get("unidadeOrgao") or {}).get("municipioNome")
                if isinstance(enriched.get("unidadeOrgao"), dict)
                else enriched.get("municipio")
                or ""
            )
        )
        uf = normalize_text(
            str(
                (enriched.get("unidadeOrgao") or {}).get("ufSigla")
                if isinstance(enriched.get("unidadeOrgao"), dict)
                else enriched.get("uf")
                or ""
            )
        ).upper()

        processo = normalize_text(str(enriched.get("processo") or ""))

        data_leilao = format_dd_mm_yyyy(parse_iso_datetime(enriched.get("dataAberturaProposta")))
        data_publicacao = format_dd_mm_yyyy(parse_iso_datetime(enriched.get("dataPublicacaoPncp")))
        data_atualizacao = format_dd_mm_yyyy(parse_iso_datetime(enriched.get("dataAtualizacao")))

        n_edital = pick_n_edital(enriched)
        valor_estimado = pick_valor_estimado(enriched)

        pncp_url = build_pncp_public_url(numero_controle) or normalize_url(str(enriched.get("linkPncp") or enriched.get("url") or ""))  # type: ignore[arg-type]
        titulo = normalize_text(str(enriched.get("objetoCompra") or enriched.get("titulo") or "")).strip()

        pdf_text = ""
        pdf_url = None
        if cnpj and ano and seq:
            pdf_text, pdf_url = self._download_pdf_text(cnpj, ano, seq)

        leiloeiro_url = normalize_url(extract_first_pdf_url(pdf_text))
        descricao = extract_descricao_3_linhas(pdf_text)
        objeto_resumido = extract_objeto_resumido(pdf_text)
        tags = extract_tags(pdf_text)
        tipo_leilao = infer_tipo_leilao(pdf_text)

        if not data_leilao:
            inferred_dt = None
            if pdf_text:
                m = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", pdf_text)
                if m:
                    try:
                        inferred_dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    except Exception:
                        inferred_dt = None
            data_leilao = format_dd_mm_yyyy(inferred_dt)

        if not valor_estimado and pdf_text:
            valor_estimado = parse_brl_money(pdf_text)

        if not (municipio and uf and processo):
            return None

        id_interno = stable_id_interno(municipio, processo, data_leilao or "00-00-0000")

        modalidade_nome = normalize_text(str(enriched.get("modalidadeNome") or ""))
        edital_db = {
            "id_interno": id_interno,
            "municipio": municipio,
            "uf": uf,
            "processo": processo,
            "data_leilao": data_leilao,
            "data_publicacao": data_publicacao,
            "data_atualizacao": data_atualizacao,
            "n_edital": n_edital,
            "valor_estimado": valor_estimado,
            "titulo": titulo,
            "orgao_nome": normalize_text(str((enriched.get("orgaoEntidade") or {}).get("razaoSocial") if isinstance(enriched.get("orgaoEntidade"), dict) else enriched.get("orgao") or "")),
            "link_pncp": pncp_url,
            "link_leiloeiro": leiloeiro_url,
            "descricao_pdf": descricao,
            "objeto_resumido": objeto_resumido,
            "tags": tags,
            "tipo_leilao": tipo_leilao,
            "modalidade_pncp": modalidade_nome,
            "numero_controle_pncp": numero_controle,
            "pdf_url": pdf_url,
        }
        return edital_db

    def _validate_and_route(self, edital_db: Dict[str, Any]) -> None:
        record = {
            "id_interno": edital_db.get("id_interno"),
            "municipio": edital_db.get("municipio"),
            "uf": edital_db.get("uf"),
            "data_leilao": edital_db.get("data_leilao"),
            "pncp_url": edital_db.get("link_pncp"),
            "leiloeiro_url": edital_db.get("link_leiloeiro"),
            "data_atualizacao": edital_db.get("data_atualizacao"),
            "titulo": edital_db.get("titulo"),
            "descricao": edital_db.get("descricao_pdf"),
            "orgao": edital_db.get("orgao_nome"),
            "n_edital": edital_db.get("n_edital"),
            "objeto_resumido": edital_db.get("objeto_resumido"),
            "tags": edital_db.get("tags"),
            "valor_estimado": edital_db.get("valor_estimado"),
            "tipo_leilao": edital_db.get("tipo_leilao"),
            "data_publicacao": edital_db.get("data_publicacao"),
        }

        result = validate_record(record)
        self._quality.register(result)

        if not self._repo.enabled:
            return

        if result.status == RecordStatus.VALID:
            ok = self._repo.upsert_edital(edital_db)
            if ok:
                self._stats["editais_validos"] += 1
            else:
                self._stats["erros"] += 1
        else:
            rejection = build_rejection_row(run_id=self._run_id, raw_record=record, result=result)
            ok = self._repo.inserir_quarentena(rejection)
            if ok:
                self._stats["editais_quarentena"] += 1
            else:
                self._stats["erros"] += 1

    def run(self) -> None:
        data_inicial, data_final = self._periodo()
        exec_id = self._repo.iniciar_execucao(self._cfg) if self._repo.enabled else None

        try:
            for termo in self._cfg.search_terms:
                for pagina in range(1, self._cfg.paginas_por_termo + 1):
                    items = self._pncp.search_publicacoes(
                        termo=termo,
                        pagina=pagina,
                        data_inicial=data_inicial,
                        data_final=data_final,
                        tamanho=self._cfg.tamanho_pagina,
                    )
                    if not items:
                        time.sleep(self._cfg.sleep_entre_paginas)
                        continue

                    for item in items:
                        if self._cfg.run_limit > 0 and self._stats["editais_encontrados"] >= self._cfg.run_limit:
                            return

                        self._stats["editais_encontrados"] += 1
                        edital_db = self._build_edital_db(item)
                        if not edital_db:
                            self._stats["erros"] += 1
                            continue

                        edital_db["link_pncp"] = normalize_url(edital_db.get("link_pncp"))
                        edital_db["link_leiloeiro"] = normalize_url(edital_db.get("link_leiloeiro"))

                        self._validate_and_route(edital_db)
                        self._stats["editais_processados"] += 1

                    time.sleep(self._cfg.sleep_entre_paginas)
        finally:
            self._repo.finalizar_execucao(exec_id, self._stats)
            self._log.info("miner_done", extra={"extra": {"stats": self._stats}})


def build_config_from_env() -> MinerConfig:
    cfg = MinerConfig()
    cfg.supabase_url = os.getenv("SUPABASE_URL", "")
    cfg.supabase_key = os.getenv("SUPABASE_KEY", "")
    raw_terms = os.getenv("PNCP_SEARCH_TERMS", "")
    cfg.search_terms = [t.strip() for t in raw_terms.split("|") if t.strip()] or ["leilão", "sucata", "veículo"]
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=30)
    parser.add_argument("--paginas", type=int, default=3)
    parser.add_argument("--tamanho", type=int, default=20)
    parser.add_argument("--run-limit", type=int, default=0)
    args = parser.parse_args()

    cfg = build_config_from_env()
    cfg.dias_lookback = args.dias
    cfg.paginas_por_termo = args.paginas
    cfg.tamanho_pagina = args.tamanho
    cfg.run_limit = args.run_limit

    Miner(cfg).run()


if __name__ == "__main__":
    main()
