#!/usr/bin/env python3
"""
Runner Principal - Conector Leilões Judiciais.

Este script orquestra todo o pipeline de scraping:
1. Descoberta de URLs via sitemap
2. Fetch com rate limiting
3. Parsing do HTML
4. Normalização para o Contrato Canônico
5. Emissão (JSONL + Supabase)
6. Relatório e quarentena

Uso:
    python run_scraper.py --mode incremental --max-lots 100
    python run_scraper.py --mode full --category vehicles --persist
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Adiciona diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from connectors.leiloesjudiciais.config import config, Config
from connectors.leiloesjudiciais.discover import LeilaoDiscovery, DiscoveredLot
from connectors.leiloesjudiciais.fetch import LeilaoFetcher, FetchStatus
from connectors.leiloesjudiciais.parse import LeilaoParser
from connectors.leiloesjudiciais.parser_v2 import ParserV2  # New improved parser
from connectors.leiloesjudiciais.normalize import LeilaoNormalizer
from connectors.leiloesjudiciais.emit import LeilaoEmitter, RunReport


# Cria diretório de logs se não existir
Path("logs").mkdir(exist_ok=True)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/leiloesjudiciais_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


class LeiloesjudiciaisScraper:
    """
    Scraper principal para leiloesjudiciais.com.br.

    Orquestra o pipeline completo de coleta de dados.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        max_lots: int = 100,
        persist_to_supabase: bool = False,
        dry_run: bool = False
    ):
        self.config = cfg or config
        self.max_lots = max_lots
        self.persist_to_supabase = persist_to_supabase
        self.dry_run = dry_run

        # Componentes
        self.discovery = LeilaoDiscovery(self.config)
        self.fetcher = LeilaoFetcher(self.config)
        self.parser = ParserV2()  # Use V2 parser with improved extraction
        self.normalizer = LeilaoNormalizer(self.config)
        self.emitter = LeilaoEmitter(self.config)

        # Timestamp de início
        self.started_at = datetime.utcnow().isoformat()

    def run(self) -> RunReport:
        """
        Executa o pipeline completo.

        Returns:
            RunReport com estatísticas da execução
        """
        logger.info("=" * 60)
        logger.info(f"INICIANDO SCRAPER: {self.config.CONNECTOR_NAME}")
        logger.info(f"Run ID: {self.emitter.run_id}")
        logger.info(f"Max lots: {self.max_lots}")
        logger.info(f"Persist: {self.persist_to_supabase}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        # 1. DESCOBERTA
        logger.info("[1/5] Descobrindo URLs via sitemap...")
        lots, discovery_report = self.discovery.discover_from_sitemap(
            filter_vehicles_only=True,
            max_lots=self.max_lots,
            save_report=not self.dry_run
        )
        logger.info(f"  - URLs no sitemap: {discovery_report.total_urls_found}")
        logger.info(f"  - Lotes encontrados: {discovery_report.lot_urls_found}")
        logger.info(f"  - Lotes filtrados: {len(lots)}")
        if discovery_report.top_seeds:
            logger.info(f"  - Top leilão: {discovery_report.top_seeds[0]['leilao_id']} ({discovery_report.top_seeds[0]['lot_count']} lotes)")

        if not lots:
            logger.warning("Nenhum lote encontrado!")
            return self._finalize_report({}, {})

        # 2. FETCH
        logger.info(f"[2/5] Buscando {len(lots)} páginas...")
        fetch_results = []
        for i, lot in enumerate(lots):
            if self.dry_run:
                logger.info(f"  [DRY RUN] Pulando fetch de {lot.url}")
                continue

            result = self.fetcher.fetch(lot.url)
            fetch_results.append((lot, result))

            if (i + 1) % 10 == 0:
                logger.info(f"  Progresso: {i + 1}/{len(lots)}")

        fetch_stats = self.fetcher.get_stats_dict()
        logger.info(f"  - Sucesso: {fetch_stats['successful']}")
        logger.info(f"  - Tombstone: {fetch_stats['tombstones']}")
        logger.info(f"  - Erros: {fetch_stats['errors']}")

        # 3. PARSE
        logger.info("[3/5] Fazendo parsing do HTML (V2 parser)...")
        parsed_lots = []
        valid_pages = 0
        invalid_pages = 0
        for lot, fetch_result in fetch_results:
            if fetch_result.status != FetchStatus.SUCCESS:
                continue

            # ParserV2.parse(url, html, save_html=False)
            parsed = self.parser.parse(fetch_result.url, fetch_result.content, save_html=True)
            parsed_lots.append(parsed)

            if parsed.is_valid_page:
                valid_pages += 1
            else:
                invalid_pages += 1

        logger.info(f"  - Lotes parseados: {len(parsed_lots)}")
        logger.info(f"  - Páginas válidas: {valid_pages}")
        logger.info(f"  - Páginas inválidas (undefined): {invalid_pages}")

        # Log parser stats
        parser_stats = self.parser.get_stats()
        logger.info(f"  - Títulos de H2: {parser_stats.get('title_from_h2', 0)}")
        logger.info(f"  - Títulos de title: {parser_stats.get('title_from_title_tag', 0)}")
        logger.info(f"  - Títulos de meta: {parser_stats.get('title_from_meta', 0)}")
        logger.info(f"  - Títulos gerados: {parser_stats.get('title_generated', 0)}")

        # 4. NORMALIZAÇÃO
        logger.info("[4/5] Normalizando dados...")
        normalized_lots = []
        for parsed in parsed_lots:
            normalized = self.normalizer.normalize(parsed)
            normalized_lots.append(normalized)

            # Log de validação
            if not normalized.is_valid:
                logger.debug(f"  - Inválido: {normalized.id_interno}: {normalized.validation_errors}")

        valid_count = sum(1 for n in normalized_lots if n.is_valid)
        logger.info(f"  - Lotes válidos: {valid_count}")
        logger.info(f"  - Lotes inválidos: {len(normalized_lots) - valid_count}")

        # 5. EMISSÃO
        logger.info("[5/5] Emitindo dados...")
        emitted, quarantined = self.emitter.emit_many(normalized_lots)
        logger.info(f"  - Emitidos: {emitted}")
        logger.info(f"  - Quarentena: {quarantined}")

        # Salvar arquivos
        if not self.dry_run:
            output_file = self.emitter.save_to_jsonl()
            logger.info(f"  - Arquivo: {output_file}")

            quarantine_file = self.emitter.save_quarantine()
            if quarantine_file:
                logger.info(f"  - Quarentena: {quarantine_file}")

            # Persistir no Supabase
            if self.persist_to_supabase:
                logger.info("  - Persistindo no Supabase...")
                inserted, errors = self.emitter.persist_to_supabase()
                logger.info(f"    - Inseridos: {inserted}, Erros: {errors}")

        # PHASE 5: Salvar category stats
        if not self.dry_run:
            category_stats_file = self.emitter.save_category_stats()
            logger.info(f"  - Category stats: {category_stats_file}")

        # Gerar relatório
        return self._finalize_report(
            {"total_found": discovery_report.lot_urls_found, "filtered_count": len(lots)},
            fetch_stats
        )

    def _finalize_report(
        self,
        discovery_stats: dict,
        fetch_stats: dict
    ) -> RunReport:
        """Gera e salva relatório final."""
        report = self.emitter.generate_report(
            discovery_stats=discovery_stats,
            fetch_stats=fetch_stats,
            started_at=self.started_at
        )

        if not self.dry_run:
            report_file = self.emitter.save_report(report)
            logger.info(f"Relatório salvo: {report_file}")

        # Log resumo
        logger.info("=" * 60)
        logger.info("RESUMO DA EXECUÇÃO")
        logger.info("=" * 60)
        logger.info(f"Run ID: {report.run_id}")
        logger.info(f"Duração: {report.duration_seconds:.2f}s")
        logger.info(f"URLs descobertas: {report.urls_discovered}")
        logger.info(f"Fetch sucesso: {report.fetch_success}")
        logger.info(f"Itens emitidos: {report.items_emitted}")
        logger.info(f"Itens quarentena: {report.items_quarantine}")
        logger.info("=" * 60)

        return report


def main():
    """Entry point do script."""
    parser = argparse.ArgumentParser(
        description="Scraper de leilões judiciais para Ache Sucatas"
    )

    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="Modo de execução (incremental=novos lotes, full=todos)"
    )

    parser.add_argument(
        "--max-lots",
        type=int,
        default=100,
        help="Máximo de lotes a processar (default: 100)"
    )

    parser.add_argument(
        "--category",
        choices=["vehicles", "all"],
        default="vehicles",
        help="Categoria a filtrar (default: vehicles)"
    )

    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persistir no Supabase"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo simulação (não faz fetch nem salva)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Arquivo de saída personalizado"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo verboso (debug)"
    )

    args = parser.parse_args()

    # Configura logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Executa scraper
    try:
        scraper = LeiloesjudiciaisScraper(
            max_lots=args.max_lots,
            persist_to_supabase=args.persist,
            dry_run=args.dry_run
        )

        report = scraper.run()

        # Código de saída baseado no resultado
        if report.items_emitted > 0:
            logger.info("Execução concluída com sucesso!")
            sys.exit(0)
        elif report.items_quarantine > 0:
            logger.warning("Execução concluída com itens em quarentena")
            sys.exit(0)
        else:
            logger.error("Nenhum item processado")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuário")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
