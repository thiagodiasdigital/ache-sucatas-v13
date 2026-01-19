#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de Cobertura de Geocoding

Analisa quantos leilões têm geocoding (latitude/longitude) disponível
e identifica gaps de matching entre cidade do leilão e ref_municipios.

Uso:
    python diagnostico_geocoding.py
"""

import os
import sys
from collections import defaultdict
from dotenv import load_dotenv

# Adicionar src/core ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

load_dotenv()


def get_supabase_client():
    """Cria cliente Supabase."""
    try:
        from supabase import create_client
    except ImportError:
        print("ERRO: supabase não instalado. Execute: pip install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY necessários no .env")
        sys.exit(1)

    return create_client(url, key)


def load_municipios_from_sql():
    """Carrega municípios do arquivo SQL local."""
    import re
    sql_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'frontend', 'supabase', 'insert_municipios.sql'
    )
    municipios = []
    pattern = re.compile(
        r"VALUES\s*\((\d+),\s*'([^']+)',\s*'([^']+)',\s*([\d.-]+),\s*([\d.-]+)\)"
    )
    with open(sql_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                municipios.append({
                    "codigo_ibge": int(match.group(1)),
                    "nome_municipio": match.group(2).replace("''", "'"),
                    "uf": match.group(3),
                    "latitude": float(match.group(4)),
                    "longitude": float(match.group(5)),
                })
    return municipios


def normalize_cidade(nome: str) -> str:
    """Normaliza nome de cidade para comparação."""
    import unicodedata
    if not nome:
        return ""
    # Remove acentos
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    # Uppercase e trim
    return nome.upper().strip()


def main():
    print("=" * 70)
    print("DIAGNÓSTICO DE COBERTURA DE GEOCODING")
    print("=" * 70)
    print()

    supabase = get_supabase_client()

    # 1. Buscar todos os leilões publicados
    print("[1/4] Buscando leilões publicados...")
    # Tentar primeiro editais_leilao (public), fallback para usar RPC
    try:
        leiloes_resp = supabase.table("editais_leilao").select(
            "id, cidade, uf"
        ).execute()
        leiloes = leiloes_resp.data or []
    except Exception as e:
        print(f"      Nota: tabela editais_leilao não acessível ({e})")
        print("      Usando view v_auction_discovery via RPC...")
        # Usar a view de produção que já faz o join
        leiloes_resp = supabase.rpc("fetch_auctions_audit", {"filter_params": {"limit": 10000}}).execute()
        leiloes = leiloes_resp.data or []
    print(f"      Total de leilões: {len(leiloes)}")

    # 2. Buscar todos os municípios de referência
    print("[2/4] Buscando municípios de referência...")
    # ref_municipios pode estar em pub schema - tentar RPC get_available_ufs para verificar
    try:
        municipios_resp = supabase.table("ref_municipios").select(
            "codigo_ibge, nome_municipio, uf, latitude, longitude"
        ).execute()
        municipios = municipios_resp.data or []
    except Exception:
        # Se não encontrar, carregar do arquivo SQL local
        print("      Carregando municípios do arquivo SQL local...")
        municipios = load_municipios_from_sql()
    print(f"      Total de municípios IBGE: {len(municipios)}")

    # 3. Criar índice de municípios (normalizado)
    print("[3/4] Criando índice de municípios...")
    municipios_index = {}
    for m in municipios:
        key = (normalize_cidade(m["nome_municipio"]), m["uf"])
        municipios_index[key] = m

    # 4. Verificar cobertura
    print("[4/4] Verificando cobertura de geocoding...")
    print()

    com_geocoding = 0
    sem_geocoding = 0
    cidades_sem_match = defaultdict(int)  # {(cidade, uf): count}

    for leilao in leiloes:
        cidade = leilao.get("cidade") or ""
        uf = leilao.get("uf") or ""

        key = (normalize_cidade(cidade), uf)

        if key in municipios_index:
            com_geocoding += 1
        else:
            sem_geocoding += 1
            cidades_sem_match[(cidade, uf)] += 1

    # Resultados
    print("=" * 70)
    print("RESULTADOS")
    print("=" * 70)
    print()

    total = len(leiloes)
    pct_com = (com_geocoding / total * 100) if total > 0 else 0
    pct_sem = (sem_geocoding / total * 100) if total > 0 else 0

    print(f"Total de leilões analisados: {total}")
    print(f"  [OK] Com geocoding:    {com_geocoding:>5} ({pct_com:.1f}%)")
    print(f"  [!!] Sem geocoding:    {sem_geocoding:>5} ({pct_sem:.1f}%)")
    print()

    if cidades_sem_match:
        print("=" * 70)
        print("CIDADES SEM MATCH (Top 20)")
        print("=" * 70)
        print()
        print(f"{'Cidade':<40} {'UF':<4} {'Qtd':>6}")
        print("-" * 54)

        # Ordenar por quantidade (maior primeiro)
        sorted_cidades = sorted(
            cidades_sem_match.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        for (cidade, uf), count in sorted_cidades:
            print(f"{cidade:<40} {uf:<4} {count:>6}")

        print()
        print(f"Total de cidades únicas sem match: {len(cidades_sem_match)}")

        # Sugestões de correção
        print()
        print("=" * 70)
        print("POSSÍVEIS CAUSAS E SUGESTÕES")
        print("=" * 70)
        print()
        print("1. Diferença de acentuação:")
        print("   - 'São Paulo' vs 'Sao Paulo'")
        print("   - Solução: Usar UNACCENT() no PostgreSQL ou normalizar no Python")
        print()
        print("2. Abreviações ou variantes:")
        print("   - 'S. Paulo' vs 'São Paulo'")
        print("   - Solução: Tabela de aliases ou fuzzy matching")
        print()
        print("3. Nomes compostos com apóstrofo:")
        print("   - \"D'Oeste\" vs \"D'oeste\" vs \"D`Oeste\"")
        print("   - Solução: Normalizar apóstrofos")
        print()

    else:
        print("[OK] EXCELENTE! Todos os leiloes tem geocoding disponivel.")

    print("=" * 70)
    print("FIM DO DIAGNÓSTICO")
    print("=" * 70)

    return 0 if sem_geocoding == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
