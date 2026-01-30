"""
Módulo de Emissão - Leilões Judiciais.

Responsável por:
1. Emitir itens no formato do Contrato Canônico
2. Gerar arquivos JSONL de saída
3. Persistir no Supabase
4. Gerar relatórios de execução
5. Gerenciar quarentena
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from .config import Config, config
from .normalize import NormalizedLot

logger = logging.getLogger(__name__)


@dataclass
class QuarantineItem:
    """Item em quarentena."""
    id_interno: str
    url: str
    reason_code: str
    reason_message: str
    raw_data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class CategoryStats:
    """PHASE 5: Estatísticas de categorização."""
    veiculo: int = 0
    sucata: int = 0
    imovel: int = 0
    unknown: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "veiculo": self.veiculo,
            "sucata": self.sucata,
            "imovel": self.imovel,
            "unknown": self.unknown,
            "total_vehicle_or_scrap": self.veiculo + self.sucata,
            "total_excluded": self.imovel,
        }


@dataclass
class RunReport:
    """Relatório de execução."""
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0

    # Descoberta
    urls_discovered: int = 0
    urls_filtered: int = 0

    # Fetch
    urls_fetched: int = 0
    fetch_success: int = 0
    fetch_tombstone: int = 0
    fetch_error: int = 0

    # Parse/Normalize
    items_parsed: int = 0
    items_normalized: int = 0
    items_valid: int = 0
    items_quarantine: int = 0

    # Persistência
    items_emitted: int = 0
    items_persisted: int = 0

    # Erros
    top_errors: List[Dict[str, Any]] = field(default_factory=list)

    # PHASE 5: Category stats
    category_stats: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, pretty: bool = True) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class LeilaoEmitter:
    """
    Emissor de dados para o Contrato Canônico.

    Responsabilidades:
    - Salvar itens válidos em JSONL
    - Salvar itens inválidos em quarentena
    - Persistir no Supabase (se configurado)
    - Gerar relatórios de execução
    - Track category stats (Phase 5)
    """

    def __init__(self, cfg: Optional[Config] = None, run_id: Optional[str] = None):
        self.config = cfg or config
        self.run_id = run_id or self._generate_run_id()

        # Contadores
        self._emitted_items: List[Dict] = []
        self._quarantine_items: List[QuarantineItem] = []
        self._errors: Dict[str, int] = {}

        # PHASE 5: Category stats
        self._category_stats = CategoryStats()

        # Supabase client (lazy init)
        self._supabase = None

    def _generate_run_id(self) -> str:
        """Gera ID único para a execução."""
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        return f"leiloesjudiciais_{ts}"

    def emit(self, lot: NormalizedLot) -> bool:
        """
        Emite um lote normalizado.

        Args:
            lot: NormalizedLot para emitir

        Returns:
            True se emitido com sucesso, False se foi para quarentena
        """
        # PHASE 5: Track category stats
        self._track_category(lot)

        # Emit all valid items (not just vehicles/sucatas)
        # MVP: accept all valid items, let dashboard filter by category
        if lot.is_valid:
            item = lot.to_dict()
            self._emitted_items.append(item)
            return True
        else:
            # Vai para quarentena only if invalid
            self._add_to_quarantine(lot)
            return False

    def _track_category(self, lot: NormalizedLot):
        """PHASE 5: Track category statistics."""
        category = lot.category_guess
        if category == "veiculo":
            self._category_stats.veiculo += 1
        elif category == "sucata":
            self._category_stats.sucata += 1
        elif category == "imovel":
            self._category_stats.imovel += 1
        else:
            self._category_stats.unknown += 1

    def emit_many(self, lots: List[NormalizedLot]) -> tuple[int, int]:
        """
        Emite múltiplos lotes.

        Args:
            lots: Lista de NormalizedLot

        Returns:
            Tupla (emitidos, quarentena)
        """
        emitted = 0
        quarantined = 0

        for lot in lots:
            if self.emit(lot):
                emitted += 1
            else:
                quarantined += 1

        return emitted, quarantined

    def _add_to_quarantine(self, lot: NormalizedLot):
        """Adiciona item à quarentena."""
        reason = lot.validation_errors[0] if lot.validation_errors else "unknown"

        item = QuarantineItem(
            id_interno=lot.id_interno,
            url=lot.link_leiloeiro,
            reason_code=reason.replace(" ", "_").upper(),
            reason_message="; ".join(lot.validation_errors),
            raw_data=lot.to_dict()
        )

        self._quarantine_items.append(item)

        # Contabiliza erro
        self._errors[reason] = self._errors.get(reason, 0) + 1

    def save_to_jsonl(self, output_path: Optional[str] = None) -> str:
        """
        Salva itens emitidos em arquivo JSONL.

        Args:
            output_path: Caminho do arquivo (usa config se None)

        Returns:
            Caminho do arquivo salvo
        """
        if output_path is None:
            output_dir = Path(self.config.OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / self.config.OUTPUT_FILE)

        with open(output_path, 'w', encoding='utf-8') as f:
            for item in self._emitted_items:
                line = json.dumps(item, ensure_ascii=False)
                f.write(line + '\n')

        logger.info(f"Salvos {len(self._emitted_items)} itens em {output_path}")
        return output_path

    def save_quarantine(self, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Salva itens em quarentena.

        Args:
            output_dir: Diretório de saída (usa config se None)

        Returns:
            Caminho do arquivo ou None se vazio
        """
        if not self._quarantine_items:
            return None

        if output_dir is None:
            output_dir = self.config.QUARANTINE_DIR

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"quarantine_{self.run_id}.jsonl"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            for item in self._quarantine_items:
                line = json.dumps(asdict(item), ensure_ascii=False)
                f.write(line + '\n')

        logger.info(f"Salvos {len(self._quarantine_items)} itens em quarentena: {filepath}")
        return filepath

    def generate_report(
        self,
        discovery_stats: Optional[Dict] = None,
        fetch_stats: Optional[Dict] = None,
        started_at: Optional[str] = None
    ) -> RunReport:
        """
        Gera relatório de execução.

        Args:
            discovery_stats: Estatísticas de descoberta
            fetch_stats: Estatísticas de fetch
            started_at: Timestamp de início

        Returns:
            RunReport
        """
        finished_at = datetime.utcnow().isoformat()

        # Calcula duração
        duration = 0.0
        if started_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                duration = (end - start).total_seconds()
            except (ValueError, TypeError):
                pass

        # Top erros
        top_errors = [
            {"error": k, "count": v}
            for k, v in sorted(self._errors.items(), key=lambda x: -x[1])
        ][:10]

        report = RunReport(
            run_id=self.run_id,
            started_at=started_at or finished_at,
            finished_at=finished_at,
            duration_seconds=duration,
            urls_discovered=discovery_stats.get("total_found", 0) if discovery_stats else 0,
            urls_filtered=discovery_stats.get("filtered_count", 0) if discovery_stats else 0,
            urls_fetched=fetch_stats.get("total_requests", 0) if fetch_stats else 0,
            fetch_success=fetch_stats.get("successful", 0) if fetch_stats else 0,
            fetch_tombstone=fetch_stats.get("tombstones", 0) if fetch_stats else 0,
            fetch_error=fetch_stats.get("errors", 0) if fetch_stats else 0,
            items_emitted=len(self._emitted_items),
            items_quarantine=len(self._quarantine_items),
            items_valid=len(self._emitted_items),
            top_errors=top_errors,
            category_stats=self._category_stats.to_dict(),
        )

        return report

    def save_category_stats(self, output_dir: Optional[str] = None) -> str:
        """
        PHASE 5: Salva estatísticas de categoria.

        Args:
            output_dir: Diretório de saída

        Returns:
            Caminho do arquivo
        """
        if output_dir is None:
            output_dir = self.config.REPORT_DIR

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = "category_stats.json"
        filepath = os.path.join(output_dir, filename)

        stats = {
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat(),
            **self._category_stats.to_dict()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        logger.info(f"Category stats salvos em {filepath}")
        return filepath

    def save_report(
        self,
        report: RunReport,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Salva relatório em arquivo JSON.

        Args:
            report: RunReport
            output_dir: Diretório de saída

        Returns:
            Caminho do arquivo
        """
        if output_dir is None:
            output_dir = self.config.REPORT_DIR

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"report_{self.run_id}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report.to_json())

        logger.info(f"Relatório salvo em {filepath}")
        return filepath

    def persist_to_supabase(self) -> tuple[int, int]:
        """
        Persiste itens no Supabase usando a tabela raw.leiloes.

        Returns:
            Tupla (inseridos, erros)
        """
        if not self.config.supabase_enabled:
            logger.warning("Supabase não configurado, pulando persistência")
            return 0, 0

        try:
            from supabase import create_client

            if self._supabase is None:
                self._supabase = create_client(
                    self.config.supabase_url,
                    self.config.supabase_key
                )

            inserted = 0
            updated = 0
            errors = 0

            for item in self._emitted_items:
                try:
                    # Map to database schema
                    db_record = self._map_to_db_schema(item)

                    # Upsert baseado no id_interno na tabela raw.leiloes
                    # Note: Supabase client uses schema prefix in table name
                    self._supabase.schema("raw").table("leiloes").upsert(
                        db_record,
                        on_conflict="id_interno"
                    ).execute()
                    inserted += 1
                except Exception as e:
                    error_msg = str(e)
                    if "duplicate" in error_msg.lower():
                        updated += 1
                    else:
                        logger.error(f"Erro ao inserir {item.get('id_interno')}: {e}")
                        errors += 1

            logger.info(f"Supabase: {inserted} inseridos, {updated} atualizados, {errors} erros")
            return inserted + updated, errors

        except ImportError:
            logger.error("Módulo supabase não instalado")
            return 0, len(self._emitted_items)
        except Exception as e:
            logger.error(f"Erro ao conectar Supabase: {e}")
            return 0, len(self._emitted_items)

    def _map_to_db_schema(self, item: Dict) -> Dict:
        """
        Maps emitted item to raw.leiloes database schema.

        Args:
            item: Emitted item dictionary

        Returns:
            Dictionary matching raw.leiloes schema
        """
        # Convert date format from DD-MM-YYYY to YYYY-MM-DD for database
        def convert_date(date_str: Optional[str]) -> Optional[str]:
            if not date_str:
                return None
            try:
                from datetime import datetime
                # Parse DD-MM-YYYY
                parsed = datetime.strptime(date_str, "%d-%m-%Y")
                return parsed.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return date_str  # Return as-is if can't parse

        return {
            "id_interno": item.get("id_interno"),
            "pncp_id": item.get("pncp_id"),  # Will be NULL for leiloeiro source
            "orgao": item.get("orgao", "Leilão Judicial"),
            "uf": item.get("uf", "XX"),
            "cidade": item.get("cidade", ""),
            "n_edital": item.get("n_edital"),
            "data_publicacao": convert_date(item.get("data_publicacao")),
            "data_atualizacao": convert_date(item.get("data_atualizacao")),
            "data_leilao": item.get("data_leilao"),  # Already ISO format or NULL
            "titulo": item.get("titulo", "")[:500],
            "descricao": item.get("descricao", "")[:2000],
            "objeto_resumido": item.get("objeto_resumido", "")[:500] if item.get("objeto_resumido") else None,
            "tags": item.get("tags", []),
            "link_pncp": item.get("link_pncp"),
            "link_leiloeiro": item.get("link_leiloeiro"),
            "modalidade_leilao": item.get("modalidade_leilao", "ONLINE"),
            "valor_estimado": item.get("valor_estimado"),
            "quantidade_itens": item.get("quantidade_itens"),
            "nome_leiloeiro": item.get("nome_leiloeiro", "Leilões Judiciais"),
            "source_type": item.get("source_type", "leiloeiro"),
            "source_name": item.get("source_name", "Leilões Judiciais"),
            "metadata": item.get("metadata", {}),
            "publication_status": item.get("publication_status", "published"),
            "score": item.get("score", 50),
            "versao_auditor": "LEILOESJUDICIAIS_V1",
        }

    @property
    def emitted_count(self) -> int:
        return len(self._emitted_items)

    @property
    def quarantine_count(self) -> int:
        return len(self._quarantine_items)

    @property
    def emitted_items(self) -> List[Dict]:
        return self._emitted_items.copy()
