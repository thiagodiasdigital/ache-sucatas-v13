#!/usr/bin/env python3
"""
Pipeline de Ingestão via API - leiloesjudiciais.com.br

Pipeline em 2 fases:
1. FETCH: Busca dados da API e persiste no raw (staging)
2. NORMALIZE: Normaliza dados e persiste lotes válidos / quarentena

Uso:
    # Dry run (não persiste no banco)
    python -m connectors.leiloesjudiciais.run_api_pipeline --dry-run --max-pages 5

    # Execução completa com persistência
    python -m connectors.leiloesjudiciais.run_api_pipeline --persist

    # Apenas tipo 1 (presencial)
    python -m connectors.leiloesjudiciais.run_api_pipeline --tipo 1 --max-pages 10

Saídas:
    - out/leiloesjudiciais/valid_{run_id}.jsonl - Lotes válidos
    - out/leiloesjudiciais/quarantine_{run_id}.jsonl - Lotes rejeitados
    - out/leiloesjudiciais/report_{run_id}.json - Relatório de execução
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from connectors.leiloesjudiciais.api_client import LeiloeiroAPIClient, FetchStats
from connectors.leiloesjudiciais.normalize_api import APILotNormalizer, NormalizedAPILot
from connectors.leiloesjudiciais.validators import (
    LoteValidator,
    ValidationResult,
    RejectionCode,
    REJECTION_DESCRIPTIONS,
    validate_api_item,
    is_vehicle_category
)
from connectors.leiloesjudiciais.config import config

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class PipelineReport:
    """Relatório completo de execução do pipeline."""
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    dry_run: bool = True

    # Fase 1: Fetch
    fetch: Dict[str, Any] = field(default_factory=dict)

    # Fase 2: Normalize
    normalize: Dict[str, Any] = field(default_factory=dict)

    # Fase 3: Validate
    validate: Dict[str, Any] = field(default_factory=dict)

    # Arquivos gerados
    files: Dict[str, str] = field(default_factory=dict)

    # Erros agregados
    top_errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, pretty: bool = True) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================================
# PIPELINE
# ============================================================================

def run_pipeline(
    dry_run: bool = True,
    max_pages: Optional[int] = None,
    persist: bool = False,
    output_dir: str = "out/leiloesjudiciais",
    filter_vehicles: bool = True,
    check_expiration: bool = False,
) -> PipelineReport:
    """
    Executa pipeline de ingestão via API.

    Fluxo:
    1. FETCH: Busca todas as páginas da API
    2. PRE-FILTER: Filtra id_categoria=3 (Imóveis) e categorias fora do escopo
    3. NORMALIZE: Converte para contrato canônico
    4. VALIDATE: Aplica regras de negócio
    5. EMIT: Salva arquivos e (opcionalmente) persiste no banco

    NOTA: A API não suporta filtro por categoria server-side.
    Categorias retornadas (id_categoria):
    - 1: Veículos (escopo do projeto)
    - 2: Bens Diversos
    - 3: Imóveis (excluir)

    Args:
        dry_run: Se True, não persiste no banco
        max_pages: Limite de páginas a buscar
        persist: Se True, persiste no Supabase
        output_dir: Diretório de saída
        filter_vehicles: Se True, filtra apenas veículos (id_categoria=1)
        check_expiration: Se True, rejeita leilões passados

    Returns:
        PipelineReport com métricas completas
    """
    # Gera run_id único
    run_id = datetime.now(tz=None).strftime("leiloeiro_api_%Y%m%dT%H%M%SZ")
    started_at = datetime.now(tz=None)

    logger.info("=" * 60)
    logger.info(f"PIPELINE INICIADO: {run_id}")
    logger.info("=" * 60)
    logger.info(f"Configuração: dry_run={dry_run}, max_pages={max_pages}")
    logger.info(f"Filtros: filter_vehicles={filter_vehicles}, check_expiration={check_expiration}")

    # Inicializa componentes
    client = LeiloeiroAPIClient(
        requests_per_second=config.REQUESTS_PER_SECOND,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        max_retries=config.MAX_RETRIES
    )
    normalizer = APILotNormalizer()
    validator = LoteValidator(check_expiration=check_expiration)

    # ========================================================================
    # FASE 1: FETCH
    # ========================================================================
    logger.info("")
    logger.info("--- FASE 1: FETCH ---")

    # Busca tipo=1 (Veículos) + tipo=2 (Bens Diversos para sucatas)
    # Tipo=3 (Imóveis) é excluído
    logger.info("Buscando lotes da API (tipos 1 e 2)...")
    all_items, stats = client.fetch_all_tipos(
        tipos=[1, 2],  # Veículos + Bens Diversos
        max_pages_per_tipo=max_pages,
        progress_callback=lambda t, p, total, items: logger.debug(f"  Tipo {t} - Página {p}/{total}")
    )

    fetch_stats = {
        "total_requests": client.stats.total_requests,
        "successful": client.stats.successful,
        "failed": client.stats.failed,
        "rate_limited": client.stats.rate_limited,
        "pages_fetched": client.stats.pages_fetched,
        "items_fetched": len(all_items),
        "avg_response_time_ms": round(client.stats.avg_response_time_ms, 2),
    }

    logger.info(f"Total bruto: {len(all_items)} lotes")

    # ========================================================================
    # FASE 2: PRE-FILTER
    # ========================================================================
    logger.info("")
    logger.info("--- FASE 2: PRE-FILTER ---")

    filtered_items: List[Dict] = []
    pre_rejected: List[Tuple[Dict, str]] = []

    # Contadores por tipo de busca e categoria
    tipo_counts: Dict[int, int] = {}
    cat_counts: Dict[int, int] = {}
    sucata_accepted = 0

    # Palavras-chave para identificar veículos em sucatas
    VEHICLE_KEYWORDS = [
        "veículo", "veiculo", "carro", "moto", "motocicleta",
        "caminhão", "caminhao", "ônibus", "onibus", "automóvel",
        "automovel", "chassi", "placa", "renavam", "trator",
        "reboque", "carreta", "van", "utilitário", "pickup",
        # Marcas comuns
        "fiat", "volkswagen", "vw", "chevrolet", "gm", "ford",
        "honda", "yamaha", "toyota", "hyundai", "jeep", "nissan",
        "mercedes", "bmw", "audi", "peugeot", "citroen", "renault",
        "scania", "volvo", "iveco", "man", "daf", "kia", "mitsubishi",
    ]

    def is_sucata_veiculo(item: Dict) -> bool:
        """Verifica se item é sucata de veículo."""
        titulo = (item.get("nm_titulo_lote") or "").lower()
        descricao = (item.get("nm_descricao") or "").lower()
        texto = f"{titulo} {descricao}"

        # Deve ter "sucata" no texto
        if "sucata" not in texto:
            return False

        # E deve ter alguma palavra-chave de veículo
        return any(kw in texto for kw in VEHICLE_KEYWORDS)

    for item in all_items:
        tipo_busca = item.get("_tipo_busca", 1)
        id_categoria = item.get("id_categoria")

        tipo_counts[tipo_busca] = tipo_counts.get(tipo_busca, 0) + 1
        cat_counts[id_categoria] = cat_counts.get(id_categoria, 0) + 1

        if filter_vehicles:
            # Tipo 1 (Veículos): aceita todos
            if tipo_busca == 1:
                filtered_items.append(item)
                continue

            # Tipo 2 (Bens Diversos): aceita apenas sucata + veículo
            if tipo_busca == 2:
                if is_sucata_veiculo(item):
                    filtered_items.append(item)
                    sucata_accepted += 1
                else:
                    pre_rejected.append((item, RejectionCode.CATEGORY_EXCLUDED))
                continue

            # Tipo 3 (Imóveis): rejeita
            if tipo_busca == 3:
                pre_rejected.append((item, RejectionCode.TIPO_3))
                continue

            # Outros tipos: rejeita
            pre_rejected.append((item, RejectionCode.CATEGORY_EXCLUDED))
        else:
            # Modo permissivo: aceita todas as categorias
            filtered_items.append(item)

    # Log dos tipos buscados
    logger.info("Tipos buscados:")
    tipo_names = {1: "Veículos", 2: "Bens Diversos", 3: "Imóveis"}
    for tipo_id, count in sorted(tipo_counts.items()):
        tipo_name = tipo_names.get(tipo_id, f"Tipo {tipo_id}")
        logger.info(f"  - {tipo_name} (tipo={tipo_id}): {count} lotes")

    # Log das categorias encontradas
    logger.info("Categorias encontradas:")
    for cat_id, count in sorted(cat_counts.items()):
        cat_name = {1: "Veículos", 2: "Bens Diversos", 3: "Imóveis"}.get(cat_id, f"Cat {cat_id}")
        logger.info(f"  - {cat_name} (id={cat_id}): {count} lotes")

    logger.info(f"Sucatas de veículos aceitas do tipo 2: {sucata_accepted}")
    logger.info(f"Após pré-filtro: {len(filtered_items)} lotes (rejeitados: {len(pre_rejected)})")

    # ========================================================================
    # FASE 3: NORMALIZE
    # ========================================================================
    logger.info("")
    logger.info("--- FASE 3: NORMALIZE ---")

    normalized: List[NormalizedAPILot] = []
    normalize_errors: List[Tuple[Dict, str]] = []

    for item in filtered_items:
        try:
            lot = normalizer.normalize(item)
            normalized.append(lot)
        except Exception as e:
            logger.warning(f"Erro normalizando lote {item.get('id')}: {e}")
            normalize_errors.append((item, f"NORMALIZE_ERROR: {e}"))

    normalize_stats = {
        "total_input": len(filtered_items),
        "normalized_ok": len(normalized),
        "normalize_errors": len(normalize_errors),
    }

    logger.info(f"Normalizados: {len(normalized)} lotes")

    # ========================================================================
    # FASE 4: VALIDATE
    # ========================================================================
    logger.info("")
    logger.info("--- FASE 4: VALIDATE ---")

    valid_lots, quarantine_lots = validator.filter_valid(normalized)

    validate_stats = {
        "total_input": len(normalized),
        "valid": len(valid_lots),
        "quarantine": len(quarantine_lots),
        "valid_rate": round(validator.stats.valid_rate, 2),
        "errors_by_code": dict(validator.stats.errors_by_code),
    }

    logger.info(f"Válidos: {len(valid_lots)}, Quarentena: {len(quarantine_lots)}")

    # ========================================================================
    # FASE 5: EMIT
    # ========================================================================
    logger.info("")
    logger.info("--- FASE 5: EMIT ---")

    # Cria diretório de saída
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files_created = {}

    # Salva lotes válidos
    valid_file = output_path / f"valid_{run_id}.jsonl"
    with open(valid_file, 'w', encoding='utf-8') as f:
        for lot in valid_lots:
            record = _lot_to_dict(lot)
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    files_created["valid"] = str(valid_file)
    logger.info(f"Salvos {len(valid_lots)} lotes válidos em {valid_file}")

    # Salva quarentena (lotes rejeitados na validação)
    quarantine_file = output_path / f"quarantine_{run_id}.jsonl"
    with open(quarantine_file, 'w', encoding='utf-8') as f:
        # Adiciona rejeitados no pré-filtro
        for item, reason in pre_rejected:
            record = {
                "lote_id_original": str(item.get("id", "")),
                "rejection_code": reason,
                "rejection_reason": REJECTION_DESCRIPTIONS.get(reason, reason),
                "payload_original": item,
                "stage": "pre_filter",
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        # Adiciona erros de normalização
        for item, error in normalize_errors:
            record = {
                "lote_id_original": str(item.get("id", "")),
                "rejection_code": "NORMALIZE_ERROR",
                "rejection_reason": error,
                "payload_original": item,
                "stage": "normalize",
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        # Adiciona rejeitados na validação
        for lot, result in quarantine_lots:
            record = {
                "id_interno": lot.id_interno,
                "lote_id_original": lot.lote_id_original,
                "rejection_code": result.primary_error or "UNKNOWN",
                "rejection_reason": result.error_description,
                "validation_errors": result.errors,
                "normalized_data": _lot_to_dict(lot),
                "stage": "validation",
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    total_quarantine = len(pre_rejected) + len(normalize_errors) + len(quarantine_lots)
    files_created["quarantine"] = str(quarantine_file)
    logger.info(f"Salvos {total_quarantine} lotes em quarentena em {quarantine_file}")

    # ========================================================================
    # PERSISTÊNCIA (opcional)
    # ========================================================================
    if persist and not dry_run:
        logger.info("")
        logger.info("--- PERSISTÊNCIA SUPABASE ---")
        try:
            inserted, errors = _persist_to_supabase(valid_lots, run_id)
            logger.info(f"Supabase: {inserted} inseridos, {errors} erros")
            validate_stats["persisted"] = inserted
            validate_stats["persist_errors"] = errors
        except Exception as e:
            logger.error(f"Erro na persistência: {e}")
            validate_stats["persist_error"] = str(e)
    else:
        logger.info("Persistência desabilitada (dry_run=True ou persist=False)")

    # ========================================================================
    # RELATÓRIO
    # ========================================================================
    finished_at = datetime.now(tz=None)
    duration = (finished_at - started_at).total_seconds()

    # Agrega top errors
    top_errors = []
    for code, count in validator.stats.top_errors[:10]:
        top_errors.append({
            "code": code,
            "count": count,
            "description": REJECTION_DESCRIPTIONS.get(code, code)
        })

    # Adiciona erros de pré-filtro
    pre_filter_counts: Dict[str, int] = {}
    for _, reason in pre_rejected:
        pre_filter_counts[reason] = pre_filter_counts.get(reason, 0) + 1
    for code, count in pre_filter_counts.items():
        top_errors.append({
            "code": code,
            "count": count,
            "description": REJECTION_DESCRIPTIONS.get(code, code),
            "stage": "pre_filter"
        })

    # Ordena por count
    top_errors.sort(key=lambda x: x["count"], reverse=True)

    report = PipelineReport(
        run_id=run_id,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_seconds=round(duration, 2),
        dry_run=dry_run,
        fetch=fetch_stats,
        normalize=normalize_stats,
        validate=validate_stats,
        files=files_created,
        top_errors=top_errors[:10],
    )

    # Salva relatório
    report_file = output_path / f"report_{run_id}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report.to_json(pretty=True))
    files_created["report"] = str(report_file)

    logger.info(f"Relatório salvo em {report_file}")

    # ========================================================================
    # SUMÁRIO FINAL
    # ========================================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE CONCLUÍDO")
    logger.info("=" * 60)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Duração: {duration:.2f}s")
    logger.info(f"Total bruto: {len(all_items)}")
    logger.info(f"Após filtros: {len(filtered_items)}")
    logger.info(f"Válidos: {len(valid_lots)}")
    logger.info(f"Quarentena: {total_quarantine}")
    logger.info(f"Taxa de aprovação: {validator.stats.valid_rate:.1f}%")
    logger.info("=" * 60)

    return report


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def _lot_to_dict(lot: NormalizedAPILot) -> Dict[str, Any]:
    """Converte NormalizedAPILot para dicionário serializável."""
    return {
        "id_interno": lot.id_interno,
        "lote_id_original": lot.lote_id_original,
        "leilao_id_original": lot.leilao_id_original,
        "titulo": lot.titulo,
        "descricao": lot.descricao,
        "objeto_resumido": lot.objeto_resumido,
        "cidade": lot.cidade,
        "uf": lot.uf,
        "data_leilao": lot.data_leilao,
        "data_publicacao": lot.data_publicacao,
        "valor_avaliacao": lot.valor_avaliacao,
        "valor_lance_inicial": lot.valor_lance_inicial,
        "valor_incremento": lot.valor_incremento,
        "link_leiloeiro": lot.link_leiloeiro,
        "link_edital": lot.link_edital,
        "tags": lot.tags,
        "categoria": lot.categoria,
        "tipo_leilao": lot.tipo_leilao,
        "nome_leiloeiro": lot.nome_leiloeiro,
        "imagens": lot.imagens,
        "metadata": lot.metadata,
        "confidence_score": lot.confidence_score,
        "source_type": "leiloeiro",
        "source_name": "Leiloes Judiciais",
    }


def _persist_to_supabase(
    lots: List[NormalizedAPILot],
    run_id: str
) -> Tuple[int, int]:
    """
    Persiste lotes no Supabase.

    TODO: Implementar quando as migrations estiverem aplicadas.
    """
    # Verifica se Supabase está configurado
    if not config.supabase_enabled:
        logger.warning("Supabase não configurado (SUPABASE_URL/SUPABASE_SERVICE_KEY ausentes)")
        return 0, 0

    # Usa httpx diretamente (compatível com novas API keys)
    import httpx

    headers = {
        "apikey": config.supabase_key,
        "Authorization": f"Bearer {config.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # Upsert behavior
    }

    base_url = f"{config.supabase_url}/rest/v1/leiloeiro_lotes"

    inserted = 0
    errors = 0

    with httpx.Client(timeout=30) as client:
        for lot in lots:
            try:
                data = {
                    "id_interno": lot.id_interno,
                    "lote_id_original": lot.lote_id_original,
                    "leilao_id_original": lot.leilao_id_original,
                    "titulo": lot.titulo,
                    "descricao": lot.descricao,
                    "objeto_resumido": lot.objeto_resumido,
                    "cidade": lot.cidade,
                    "uf": lot.uf,
                    "data_leilao": lot.data_leilao,
                    "data_publicacao": lot.data_publicacao,
                    "valor_avaliacao": lot.valor_avaliacao,
                    "link_leiloeiro": lot.link_leiloeiro,
                    "link_edital": lot.link_edital,
                    "tags": lot.tags,
                    "categoria": lot.categoria,
                    "tipo_leilao": lot.tipo_leilao,
                    "nome_leiloeiro": lot.nome_leiloeiro,
                    "imagens": lot.imagens,
                    "metadata": lot.metadata,
                    "confidence_score": lot.confidence_score,
                }

                # Upsert via POST com on_conflict
                response = client.post(
                    base_url,
                    headers=headers,
                    json=data,
                    params={"on_conflict": "id_interno"}
                )

                if response.status_code in (200, 201):
                    inserted += 1
                else:
                    logger.error(f"Erro ao persistir {lot.id_interno}: HTTP {response.status_code} - {response.text[:100]}")
                    errors += 1

            except Exception as e:
                logger.error(f"Erro ao persistir {lot.id_interno}: {e}")
                errors += 1

    return inserted, errors


# ============================================================================
# CLI
# ============================================================================

def main():
    """Ponto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Pipeline de ingestão via API - leiloesjudiciais.com.br",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
    # Dry run com 5 páginas
    python -m connectors.leiloesjudiciais.run_api_pipeline --dry-run --max-pages 5

    # Execução completa com persistência
    python -m connectors.leiloesjudiciais.run_api_pipeline --persist

    # Apenas tipo 1 (presencial)
    python -m connectors.leiloesjudiciais.run_api_pipeline --tipo 1 --max-pages 10
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não persiste no banco (padrão: True se --persist não for passado)"
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persiste no Supabase"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limite de páginas a buscar (None = sem limite)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="out/leiloesjudiciais",
        help="Diretório de saída"
    )
    parser.add_argument(
        "--no-filter-vehicles",
        action="store_true",
        help="Não filtra por categoria de veículos"
    )
    parser.add_argument(
        "--check-expiration",
        action="store_true",
        help="Rejeita leilões já encerrados"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo verbose (debug)"
    )

    args = parser.parse_args()

    # Configura logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determina dry_run
    dry_run = not args.persist

    # Executa pipeline
    report = run_pipeline(
        dry_run=dry_run,
        max_pages=args.max_pages,
        persist=args.persist,
        output_dir=args.output_dir,
        filter_vehicles=not args.no_filter_vehicles,
        check_expiration=args.check_expiration,
    )

    # Retorna código de saída
    if report.validate.get("valid", 0) > 0:
        sys.exit(0)
    else:
        logger.error("Nenhum lote válido processado")
        sys.exit(1)


if __name__ == "__main__":
    main()
