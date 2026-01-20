#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCRIPT DE ATUALIZAÇÃO: data_leilao para 294 Editais Existentes
===============================================================

Este script atualiza o campo data_leilao de TODOS os editais existentes
no banco de dados que não possuem essa informação preenchida.

PROBLEMA RESOLVIDO:
- O Minerador V11 coletava editais da API de SEARCH do PNCP
- Essa API NÃO retorna o campo dataAberturaProposta (data do leilão)
- Resultado: 91% dos editais estavam sem data_leilao

SOLUÇÃO:
- Este script faz chamadas à API COMPLETA do PNCP (endpoint /consulta/v1/)
- Essa API retorna o campo dataAberturaProposta
- Atualiza o banco de dados com as datas encontradas

FLUXO:
1. Conecta ao Supabase PostgreSQL
2. Busca todos os editais sem data_leilao
3. Para cada edital:
   a. Extrai CNPJ, ANO, SEQUENCIAL do pncp_id
   b. Chama API PNCP: /api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}
   c. Extrai dataAberturaProposta da resposta
   d. Atualiza o registro no banco
4. Exibe estatísticas ao final

USO:
    # Modo teste (10 editais)
    python atualizar_datas_294_editais.py --test

    # Processar todos os editais sem data_leilao
    python atualizar_datas_294_editais.py

    # Processar com limite específico
    python atualizar_datas_294_editais.py --limit 50

    # Modo verbose (mais logs)
    python atualizar_datas_294_editais.py --verbose

    # Dry-run (sem atualizar banco)
    python atualizar_datas_294_editais.py --dry-run

REQUISITOS:
    - SUPABASE_URL e SUPABASE_SERVICE_KEY no .env
    - requests, python-dotenv

Data: 2026-01-19
Autor: Claude Code (CRAUDIO)
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Adicionar src/core ao path para importar supabase_repository
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

load_dotenv()

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("AtualizarDatas")

# Configurações
API_CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1/orgaos"
API_DELAY_MS = 200  # Delay entre chamadas para evitar rate limiting
API_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ==============================================================================
# MÉTRICAS
# ==============================================================================

@dataclass
class UpdateMetrics:
    """Métricas da atualização."""
    total_editais: int = 0
    sem_data_leilao: int = 0
    processados: int = 0
    atualizados: int = 0
    api_sucesso: int = 0
    api_falha: int = 0
    api_sem_data: int = 0
    erros: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def print_summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        log.info("=" * 70)
        log.info("RESUMO DA ATUALIZAÇÃO")
        log.info("=" * 70)
        log.info(f"Duração: {duration:.1f}s")
        log.info(f"Total editais no banco: {self.total_editais}")
        log.info(f"Editais sem data_leilao: {self.sem_data_leilao}")
        log.info("-" * 70)
        log.info(f"Processados: {self.processados}")
        log.info(f"Atualizados com sucesso: {self.atualizados}")
        log.info("-" * 70)
        log.info("API PNCP:")
        log.info(f"  |- Chamadas com sucesso: {self.api_sucesso}")
        log.info(f"  |- Sem dataAberturaProposta: {self.api_sem_data}")
        log.info(f"  |- Falhas: {self.api_falha}")
        log.info(f"  |- Erros: {self.erros}")
        log.info("-" * 70)
        if self.sem_data_leilao > 0:
            taxa = (self.atualizados / self.sem_data_leilao) * 100
            log.info(f"TAXA DE SUCESSO: {taxa:.1f}%")
        log.info("=" * 70)


# ==============================================================================
# FUNÇÕES DE API
# ==============================================================================

def extrair_componentes_pncp_id(pncp_id: str) -> Optional[Dict[str, str]]:
    """
    Extrai CNPJ, ANO, SEQUENCIAL do pncp_id.

    Formatos aceitos:
    - "12345678901234-1-000123/2025"
    - "12345678901234-1-000123-2025"
    """
    if not pncp_id:
        return None

    # Padrão 1: CNPJ-CODIGO-SEQ/ANO ou CNPJ-CODIGO-SEQ-ANO
    match = re.search(r'(\d{14})\D+\d+\D+(\d+)\D+(\d{4})', pncp_id)
    if match:
        return {
            'cnpj': match.group(1),
            'sequencial': match.group(2).lstrip('0') or '0',
            'ano': match.group(3),
        }

    # Padrão 2: Com formatação de CNPJ
    pncp_limpo = re.sub(r'[.\-/]', '', pncp_id)
    match = re.search(r'(\d{14})(\d)(\d+)(\d{4})$', pncp_limpo)
    if match:
        return {
            'cnpj': match.group(1),
            'sequencial': match.group(3).lstrip('0') or '0',
            'ano': match.group(4),
        }

    return None


def buscar_data_leilao_api(pncp_id: str, session: requests.Session) -> Optional[str]:
    """
    Busca dataAberturaProposta da API PNCP.

    Returns:
        String ISO datetime se encontrado, None caso contrário
    """
    componentes = extrair_componentes_pncp_id(pncp_id)
    if not componentes:
        log.debug(f"  Não foi possível extrair componentes de: {pncp_id}")
        return None

    cnpj = componentes['cnpj']
    ano = componentes['ano']
    seq = componentes['sequencial']

    url = f"{API_CONSULTA_BASE}/{cnpj}/compras/{ano}/{seq}"

    try:
        # Rate limiting
        time.sleep(API_DELAY_MS / 1000)

        response = session.get(url, timeout=API_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            data_abertura = data.get('dataAberturaProposta')
            return data_abertura
        elif response.status_code == 404:
            log.debug(f"  API 404: {cnpj}/{ano}/{seq}")
        else:
            log.warning(f"  API status {response.status_code}: {url}")

    except requests.Timeout:
        log.warning(f"  Timeout: {url}")
    except requests.RequestException as e:
        log.warning(f"  Erro request: {e}")
    except json.JSONDecodeError:
        log.warning(f"  Erro JSON: {url}")

    return None


# ==============================================================================
# FUNÇÃO PRINCIPAL
# ==============================================================================

def atualizar_editais(
    limit: int = None,
    dry_run: bool = False,
    verbose: bool = False
) -> UpdateMetrics:
    """
    Atualiza data_leilao de todos os editais sem essa informação.

    Args:
        limit: Limitar número de editais a processar
        dry_run: Se True, não atualiza o banco (apenas simula)
        verbose: Se True, mostra mais logs

    Returns:
        UpdateMetrics com estatísticas da execução
    """
    metrics = UpdateMetrics()

    if verbose:
        log.setLevel(logging.DEBUG)

    log.info("=" * 70)
    log.info("ATUALIZAÇÃO DE data_leilao - 294 EDITAIS")
    log.info("=" * 70)
    log.info(f"Modo: {'DRY-RUN (sem atualizar banco)' if dry_run else 'PRODUÇÃO'}")
    log.info(f"Limite: {limit if limit else 'Sem limite'}")
    log.info("=" * 70)

    # Conectar ao Supabase
    try:
        from supabase_repository import SupabaseRepository
        repo = SupabaseRepository(enable_supabase=True)
        if not repo.enable_supabase:
            log.error("Supabase não está habilitado. Verifique SUPABASE_URL e SUPABASE_SERVICE_KEY.")
            return metrics
        log.info("Supabase conectado com sucesso")
    except ImportError:
        log.error("Não foi possível importar supabase_repository.py")
        return metrics
    except Exception as e:
        log.error(f"Erro ao conectar Supabase: {e}")
        return metrics

    # Buscar total de editais
    try:
        total_response = repo.client.table("editais_leilao").select("id", count="exact").execute()
        metrics.total_editais = total_response.count or len(total_response.data)
        log.info(f"Total de editais no banco: {metrics.total_editais}")
    except Exception as e:
        log.error(f"Erro ao contar editais: {e}")

    # Buscar editais sem data_leilao
    try:
        query = (
            repo.client
            .table("editais_leilao")
            .select("id, pncp_id, titulo, uf, cidade")
            .is_("data_leilao", "null")
            .order("created_at", desc=True)
        )

        if limit:
            query = query.limit(limit)

        response = query.execute()
        editais = response.data

        metrics.sem_data_leilao = len(editais)
        log.info(f"Editais sem data_leilao: {metrics.sem_data_leilao}")

    except Exception as e:
        log.error(f"Erro ao buscar editais sem data_leilao: {e}")
        return metrics

    if not editais:
        log.info("Todos os editais já possuem data_leilao!")
        return metrics

    # Criar sessão HTTP com headers
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })

    # Processar cada edital
    log.info(f"\nProcessando {len(editais)} editais...")
    log.info("-" * 70)

    for i, edital in enumerate(editais, 1):
        pncp_id = edital.get("pncp_id")
        titulo = edital.get("titulo", "")[:50]
        uf = edital.get("uf", "??")

        metrics.processados += 1

        log.info(f"[{i}/{len(editais)}] {uf} - {pncp_id}")

        # Buscar data na API
        data_leilao = buscar_data_leilao_api(pncp_id, session)

        if data_leilao:
            metrics.api_sucesso += 1
            log.info(f"  ✓ Data encontrada: {data_leilao}")

            # Atualizar no banco
            if not dry_run:
                try:
                    (
                        repo.client
                        .table("editais_leilao")
                        .update({
                            "data_leilao": data_leilao,
                            "updated_at": datetime.now().isoformat(),
                        })
                        .eq("pncp_id", pncp_id)
                        .execute()
                    )
                    metrics.atualizados += 1
                    log.info(f"  ✓ Banco atualizado")
                except Exception as e:
                    log.error(f"  ✗ Erro ao atualizar banco: {e}")
                    metrics.erros += 1
            else:
                metrics.atualizados += 1
                log.info(f"  [DRY-RUN] Atualizaria com: {data_leilao}")
        else:
            # API retornou mas sem dataAberturaProposta
            componentes = extrair_componentes_pncp_id(pncp_id)
            if componentes:
                metrics.api_sem_data += 1
                log.info(f"  ⚠ API sem dataAberturaProposta")
            else:
                metrics.api_falha += 1
                log.info(f"  ✗ Falha na API ou pncp_id inválido")

        # Log de progresso a cada 10
        if i % 10 == 0:
            log.info(f"\n--- Progresso: {i}/{len(editais)} ({i/len(editais)*100:.0f}%) ---")
            log.info(f"    Atualizados: {metrics.atualizados} | API OK: {metrics.api_sucesso} | Sem data: {metrics.api_sem_data}\n")

    # Resumo final
    metrics.print_summary()

    return metrics


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Atualiza data_leilao dos editais existentes usando API PNCP"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limitar número de editais a processar"
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Modo teste (processa apenas 10 editais)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Simula a atualização sem modificar o banco"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostra logs detalhados"
    )

    args = parser.parse_args()

    limit = args.limit
    if args.test:
        limit = 10
        log.info("Modo TESTE ativado (limite: 10 editais)")

    metrics = atualizar_editais(
        limit=limit,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Exit code baseado no sucesso
    if metrics.atualizados > 0:
        sys.exit(0)
    elif metrics.sem_data_leilao == 0:
        sys.exit(0)  # Não havia nada para atualizar
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
