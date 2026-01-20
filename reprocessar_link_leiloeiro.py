#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRIPT: Reprocessar Link Leiloeiro e Remover Tag SYNC
=====================================================

Este script corrige dados existentes no banco Supabase:
1. Extrai link_leiloeiro de URLs encontradas na descricao
2. Remove tags proibidas (SYNC, LEILAO, LEILÃO)
3. Normaliza modalidades para valores padrao

COMO EXECUTAR:
    python reprocessar_link_leiloeiro.py

REQUISITOS:
    - .env com SUPABASE_URL e SUPABASE_SERVICE_KEY
    - Biblioteca supabase instalada (pip install supabase)
"""

import os
import re
import sys
from datetime import datetime
from typing import List, Optional, Tuple

# Adicionar src/core ao path para importar modulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'core'))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
except ImportError:
    print("[ERRO] Biblioteca supabase nao instalada.")
    print("Execute: pip install supabase")
    sys.exit(1)


# =============================================================================
# CONFIGURACOES
# =============================================================================

# Tags que devem ser REMOVIDAS
TAGS_PROIBIDAS = {"sync", "leilao", "leilão", "leiloes", "leilões"}

# Dominios governamentais a ignorar para link_leiloeiro
DOMINIOS_GOVERNAMENTAIS = [
    "gov.br", "gov.com", "jus.br", "leg.br", "mil.br",
    "mp.br", "def.br", "receita.fazenda", "pncp.gov"
]

# Dominios de email a ignorar
DOMINIOS_EMAIL = [
    "@gmail", "@hotmail", "@outlook", "@yahoo", "@uol",
    "@bol", "@terra", "@ig.com", "@globo.com", "@live.com",
    "email", "mailto", "@gov.br"
]

# Keywords que indicam site de leiloeiro
KEYWORDS_LEILOEIRO = [
    "leilao", "leilões", "leiloes", "lance", "arremate",
    "superbid", "soldafacil", "zukerman", "megaleiloes",
    "leilomaster", "frfreiloes", "kipleiloes", "vialeiloes",
    "lut-leiloes", "bfreiloes", "leilaovip", "leiloeiros",
    "sodfreiloes", "leiloei", "petroleiloes", "leilobras"
]

# Regex para extrair URLs
REGEX_URL = re.compile(
    r'(?:https?://)?'
    r'(?:www\.)?'
    r'[a-zA-Z0-9][-a-zA-Z0-9]*'
    r'(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+'
    r'(?:\.[a-zA-Z]{2,})'
    r'(?:/[^\s<>"\')\]]*)?',
    re.IGNORECASE
)

# Normalizacao de modalidades
MODALIDADES_NORMALIZACAO = {
    "ONLINE": "Eletrônico",
    "Online": "Eletrônico",
    "online": "Eletrônico",
    "ELETRONICO": "Eletrônico",
    "Eletronico": "Eletrônico",
    "eletronico": "Eletrônico",
    "ELETRÔNICO": "Eletrônico",
    "eletrônico": "Eletrônico",
    "Leilão - Eletrônico": "Eletrônico",
    "Leilao - Eletronico": "Eletrônico",
    "PRESENCIAL": "Presencial",
    "presencial": "Presencial",
    "Leilão - Presencial": "Presencial",
    "Leilao - Presencial": "Presencial",
    "HIBRIDO": "Híbrido",
    "Hibrido": "Híbrido",
    "hibrido": "Híbrido",
    "HÍBRIDO": "Híbrido",
    "híbrido": "Híbrido",
}


# =============================================================================
# FUNCOES DE EXTRACAO (baseadas no cloud_auditor_v17.py)
# =============================================================================

def extrair_urls_de_texto(texto: str) -> List[str]:
    """Extrai todas as URLs de um texto."""
    if not texto:
        return []

    urls = REGEX_URL.findall(texto)
    urls_normalizadas = []

    for url in urls:
        url = url.strip().rstrip('.,;:)')
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        urls_normalizadas.append(url)

    return list(set(urls_normalizadas))


def is_url_governamental(url: str) -> bool:
    """Verifica se URL e de dominio governamental."""
    url_lower = url.lower()
    return any(dominio in url_lower for dominio in DOMINIOS_GOVERNAMENTAIS)


def is_url_email(url: str) -> bool:
    """Verifica se URL e na verdade um email."""
    url_lower = url.lower()
    return any(dominio in url_lower for dominio in DOMINIOS_EMAIL)


def encontrar_link_leiloeiro(urls: List[str]) -> Optional[str]:
    """
    Encontra o melhor link de leiloeiro em uma lista de URLs.
    Prioriza URLs com keywords de leiloeiro.
    """
    urls_validas = []

    for url in urls:
        if url and not is_url_governamental(url) and not is_url_email(url):
            urls_validas.append(url)

    if not urls_validas:
        return None

    # Prioridade 1: URLs com keywords de leiloeiro
    for url in urls_validas:
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in KEYWORDS_LEILOEIRO):
            return url

    # Prioridade 2: URLs comerciais (.com.br, .com, etc)
    for url in urls_validas:
        url_lower = url.lower()
        if any(tld in url_lower for tld in [".com.br", ".com", ".net.br", ".net", ".leilao"]):
            return url

    # Prioridade 3: Primeira URL valida
    return urls_validas[0] if urls_validas else None


def limpar_tags(tags_str: str) -> str:
    """Remove tags proibidas e retorna string limpa."""
    if not tags_str:
        return ""

    # Separar tags (pode ser por virgula ou array)
    if isinstance(tags_str, list):
        tags = tags_str
    else:
        tags = [t.strip() for t in tags_str.replace('{', '').replace('}', '').split(',')]

    # Filtrar tags proibidas
    tags_limpas = [t for t in tags if t.lower() not in TAGS_PROIBIDAS and t]

    return ','.join(tags_limpas) if tags_limpas else "sem_classificacao"


def normalizar_modalidade(modalidade: str) -> Optional[str]:
    """Normaliza modalidade para valor padrao."""
    if not modalidade or modalidade == "N/D":
        return None

    # Usar mapeamento direto
    if modalidade in MODALIDADES_NORMALIZACAO:
        return MODALIDADES_NORMALIZACAO[modalidade]

    # Tentar match parcial
    modalidade_lower = modalidade.lower()
    if "eletron" in modalidade_lower or "eletrôn" in modalidade_lower or "online" in modalidade_lower:
        return "Eletrônico"
    elif "presenc" in modalidade_lower:
        return "Presencial"
    elif "hibrid" in modalidade_lower or "híbrid" in modalidade_lower:
        return "Híbrido"

    return modalidade


# =============================================================================
# FUNCAO PRINCIPAL
# =============================================================================

def main():
    print("=" * 80)
    print("REPROCESSAMENTO DE DADOS - Link Leiloeiro + Tags")
    print("=" * 80)
    print()

    # Conectar ao Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("[ERRO] Variaveis SUPABASE_URL e SUPABASE_SERVICE_KEY nao encontradas.")
        print("Verifique seu arquivo .env")
        sys.exit(1)

    print("[1/5] Conectando ao Supabase...")
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("  [OK] Conectado com sucesso")
    except Exception as e:
        print(f"  [ERRO] Falha na conexao: {e}")
        sys.exit(1)

    # Buscar leiloes que precisam de correcao
    print()
    print("[2/5] Buscando leiloes que precisam de correcao...")

    try:
        # Buscar todos os leiloes da tabela editais_leilao (public schema)
        response = supabase.table("editais_leilao").select("*").execute()
        leiloes = response.data

        print(f"  [OK] {len(leiloes)} leiloes encontrados no total")
    except Exception as e:
        print(f"  [ERRO] Falha ao buscar leiloes: {e}")
        sys.exit(1)

    # Analisar quais precisam de correcao
    print()
    print("[3/5] Analisando dados...")

    leiloes_corrigir = []
    stats = {
        "total": len(leiloes),
        "com_tag_sync": 0,
        "sem_link_leiloeiro": 0,
        "url_na_descricao": 0,
        "modalidade_nao_padrao": 0
    }

    for leilao in leiloes:
        precisa_correcao = False
        correcoes = {}

        # Verificar tag SYNC
        tags = leilao.get("tags", "")
        if tags:
            tags_str = str(tags) if not isinstance(tags, str) else tags
            if any(t in tags_str.lower() for t in TAGS_PROIBIDAS):
                stats["com_tag_sync"] += 1
                correcoes["tags"] = limpar_tags(tags_str)
                precisa_correcao = True

        # Verificar link_leiloeiro
        link_atual = leilao.get("link_leiloeiro")
        descricao = leilao.get("descricao", "") or ""

        if not link_atual or link_atual in ["N/D", "", None]:
            stats["sem_link_leiloeiro"] += 1

            # Tentar extrair da descricao
            urls = extrair_urls_de_texto(descricao)
            if urls:
                stats["url_na_descricao"] += 1
                novo_link = encontrar_link_leiloeiro(urls)
                if novo_link:
                    correcoes["link_leiloeiro"] = novo_link
                    precisa_correcao = True

        # Verificar modalidade
        modalidade = leilao.get("modalidade_leilao")
        if modalidade:
            modalidade_normalizada = normalizar_modalidade(modalidade)
            if modalidade_normalizada and modalidade_normalizada != modalidade:
                stats["modalidade_nao_padrao"] += 1
                correcoes["modalidade_leilao"] = modalidade_normalizada
                precisa_correcao = True

        if precisa_correcao:
            leiloes_corrigir.append({
                "id": leilao.get("id"),
                "id_interno": leilao.get("id_interno"),
                "correcoes": correcoes
            })

    print(f"  Total de leiloes: {stats['total']}")
    print(f"  Com tag SYNC/LEILAO: {stats['com_tag_sync']}")
    print(f"  Sem link_leiloeiro: {stats['sem_link_leiloeiro']}")
    print(f"  Com URL na descricao (recuperaveis): {stats['url_na_descricao']}")
    print(f"  Com modalidade nao padrao: {stats['modalidade_nao_padrao']}")
    print(f"  ---")
    print(f"  TOTAL A CORRIGIR: {len(leiloes_corrigir)}")

    if not leiloes_corrigir:
        print()
        print("=" * 80)
        print("[OK] Nenhum leilao precisa de correcao!")
        print("=" * 80)
        return

    # Confirmar com usuario
    print()
    print("=" * 80)
    print("CONFIRMACAO")
    print("=" * 80)
    print()
    print(f"Serao corrigidos {len(leiloes_corrigir)} leiloes.")
    print()
    resposta = input("Deseja continuar? (s/n): ").strip().lower()

    if resposta != 's':
        print()
        print("[CANCELADO] Operacao cancelada pelo usuario.")
        return

    # Aplicar correcoes
    print()
    print("[4/5] Aplicando correcoes...")

    sucesso = 0
    falha = 0

    for i, item in enumerate(leiloes_corrigir, 1):
        try:
            # Usar id ou id_interno para update na tabela editais_leilao
            if item["id"]:
                supabase.table("editais_leilao").update(item["correcoes"]).eq("id", item["id"]).execute()
            elif item["id_interno"]:
                supabase.table("editais_leilao").update(item["correcoes"]).eq("id_interno", item["id_interno"]).execute()

            sucesso += 1

            # Mostrar progresso a cada 10
            if i % 10 == 0 or i == len(leiloes_corrigir):
                print(f"  Progresso: {i}/{len(leiloes_corrigir)} ({sucesso} ok, {falha} falhas)")

        except Exception as e:
            falha += 1
            if falha <= 5:  # Mostrar apenas primeiros 5 erros
                print(f"  [ERRO] ID {item.get('id') or item.get('id_interno')}: {e}")

    # Resultado final
    print()
    print("=" * 80)
    print("[5/5] RESULTADO FINAL")
    print("=" * 80)
    print()
    print(f"  Leiloes processados: {len(leiloes_corrigir)}")
    print(f"  Sucesso: {sucesso}")
    print(f"  Falhas: {falha}")
    print()

    if sucesso > 0:
        print("  [OK] Atualize a pagina do dashboard (F5) para ver as mudancas!")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
