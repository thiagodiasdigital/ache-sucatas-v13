#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ache Sucatas DaaS - Patch de Validação de URL para Miner V14
============================================================

Este módulo contém as funções de validação de URL que devem ser
integradas ao Miner V14 para aplicar o mesmo gate do Auditor V19.

Uso:
    1. Importe as funções deste módulo no Miner V14
    2. Substitua a lógica das linhas 857-860 pelo código indicado

Versão: 1.0
Data: 2026-01-21
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


# ============================================================
# WHITELIST DE DOMÍNIOS VÁLIDOS
# ============================================================

WHITELIST_DOMINIOS = {
    "lfranca.com.br",
    "bidgo.com.br",
    "sodresantoro.com.br",
    "superbid.net",
    "superbid.com.br",
    "vipleiloes.com.br",
    "frfranca.com.br",
    "lancenoleilao.com.br",
    "leilomaster.com.br",
    "lut.com.br",
    "zfrancaleiloes.com.br",
    "amaralleiloes.com.br",
    "bfranca.com.br",
    "cronos.com.br",
    "confederacaoleiloes.com.br",
    "megaleiloes.com.br",
    "leilaoseg.com.br",
    "cfrancaleiloes.com.br",
    "estreladaleiloes.com.br",
    "sold.com.br",
    "mitroleiloes.com.br",
    "alifrancaleiloes.com.br",
    "hastavip.com.br",
    "klfrancaleiloes.com.br",
    "centraldosleiloes.com.br",
    "dfranca.com.br",
    "rfrancaleiloes.com.br",
    "sfranca.com.br",
    "clickleiloes.com.br",
    "petroleiloes.com.br",
    "pfranca.com.br",
    "clfranca.com.br",
    "tfleiloes.com.br",
    "kfranca.com.br",
    "lanceja.com.br",
    "portalleiloes.com.br",
    "wfrancaleiloes.com.br",
    "rafaelfrancaleiloes.com.br",
    "alfrancaleiloes.com.br",
    "jfrancaleiloes.com.br",
    "mfranca.com.br",
    "msfranca.com.br",
    "stfrancaleiloes.com.br",
    "ofrancaleiloes.com.br",
    "hmfrancaleiloes.com.br",
    "abataleiloes.com.br",
    "webleilao.com.br",
    "gfrancaleiloes.com.br",
    "lleiloes.com.br",
    "lanceleiloes.com.br",
    "lopesleiloes.net.br",
    "lopesleiloes.com.br",
}


# ============================================================
# REGEX PARA DETECÇÃO DE TLD COLADO
# ============================================================

# Detecta TLD colado em palavra (falso positivo)
# Exemplo: "ED.COMEMORA" - TLD .COM colado com "EMORA"
REGEX_TLD_COLADO = re.compile(
    r'[A-Za-z0-9]\.(?:com|net|org|br|gov|edu|io|co)[A-Za-z]',
    re.IGNORECASE
)


# ============================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================

def validar_url_link_leiloeiro(url: str) -> Tuple[bool, int, Optional[str]]:
    """
    Valida se uma URL pode ser usada como link_leiloeiro.
    
    Aplica o mesmo gate do Auditor V19:
    1. Deve começar com http(s):// ou www.
    2. Ou pertencer à whitelist de domínios conhecidos
    3. Não pode ter TLD colado em palavra (verificado apenas para candidatos sem prefixo)
    
    Args:
        url: URL candidata para validação
        
    Returns:
        Tupla (valido, confianca, motivo_rejeicao)
        - valido: True se passou no gate
        - confianca: 100=whitelist, 80=http(s), 60=www, 0=rejeitado
        - motivo_rejeicao: Motivo se rejeitado, None caso contrário
    """
    if not url:
        return False, 0, "url_vazia"
    
    url_limpa = url.strip()
    url_lower = url_limpa.lower()
    
    # Gate 1: Prefixo http(s) - URLs estruturadas são válidas
    if url_lower.startswith(("http://", "https://")):
        if _esta_na_whitelist(url_limpa):
            return True, 100, None
        return True, 80, None
    
    # Gate 2: Prefixo www - URLs estruturadas são válidas
    if url_lower.startswith("www."):
        if _esta_na_whitelist(url_limpa):
            return True, 100, None
        return True, 60, None
    
    # Gate 3: Whitelist (sem prefixo)
    if _esta_na_whitelist(url_limpa):
        return True, 100, None
    
    # Para candidatos SEM prefixo estruturado e FORA da whitelist:
    # Verificar se é TLD colado em palavra (falso positivo)
    if REGEX_TLD_COLADO.search(url_limpa):
        return False, 0, "tld_colado_em_palavra"
    
    # Não passou em nenhum gate
    return False, 0, "sem_prefixo_ou_whitelist"


def _extrair_dominio(url: str) -> Optional[str]:
    """Extrai domínio de uma URL."""
    try:
        url_normalizada = url
        if not url_normalizada.startswith("http"):
            url_normalizada = "https://" + url_normalizada
        
        parsed = urlparse(url_normalizada)
        dominio = parsed.netloc.lower()
        return dominio.replace("www.", "")
    except Exception:
        return None


def _esta_na_whitelist(url: str) -> bool:
    """Verifica se o domínio da URL está na whitelist."""
    dominio = _extrair_dominio(url)
    if not dominio:
        return False
    
    for dominio_valido in WHITELIST_DOMINIOS:
        if dominio == dominio_valido or dominio.endswith("." + dominio_valido):
            return True
    
    return False


def processar_link_pncp(
    link_sistema: Optional[str],
    link_edital: Optional[str],
    pncp_id: str
) -> dict:
    """
    Processa links da API PNCP aplicando validação V19.
    
    Substitui a lógica original das linhas 857-860 do Miner V14.
    
    Args:
        link_sistema: Valor de detalhes.get("linkSistema")
        link_edital: Valor de detalhes.get("linkEdital")
        pncp_id: ID do edital para logging
        
    Returns:
        Dict com campos para o edital:
        {
            "link_leiloeiro": URL validada ou None,
            "link_leiloeiro_raw": URL candidata original,
            "link_leiloeiro_valido": bool,
            "link_leiloeiro_origem_tipo": "pncp_api",
            "link_leiloeiro_origem_ref": "pncp_api:linkSistema" ou "pncp_api:linkEdital",
            "link_leiloeiro_confianca": int,
        }
    """
    resultado = {
        "link_leiloeiro": None,
        "link_leiloeiro_raw": None,
        "link_leiloeiro_valido": None,
        "link_leiloeiro_origem_tipo": None,
        "link_leiloeiro_origem_ref": None,
        "link_leiloeiro_confianca": None,
    }
    
    # Escolher link disponível (linkSistema tem prioridade)
    link_candidato = link_sistema or link_edital
    campo_origem = "linkSistema" if link_sistema else "linkEdital"
    
    if not link_candidato:
        return resultado
    
    # Filtrar links do próprio PNCP
    if "pncp.gov" in link_candidato.lower():
        return resultado
    
    # Aplicar validação V19
    valido, confianca, motivo = validar_url_link_leiloeiro(link_candidato)
    
    resultado["link_leiloeiro_raw"] = link_candidato
    resultado["link_leiloeiro_valido"] = valido
    resultado["link_leiloeiro_origem_tipo"] = "pncp_api"
    resultado["link_leiloeiro_origem_ref"] = f"pncp_api:{campo_origem}"
    resultado["link_leiloeiro_confianca"] = confianca
    
    if valido:
        resultado["link_leiloeiro"] = link_candidato
    
    return resultado


# ============================================================
# INSTRUÇÕES DE INTEGRAÇÃO NO MINER V14
# ============================================================

"""
INSTRUÇÕES PARA APLICAR O PATCH NO MINER V14
============================================

1. Adicione este import no início do arquivo ache_sucatas_miner_v14.py:

    from miner_url_validation_patch import processar_link_pncp

2. Localize as linhas 857-860 no método _enriquecer_edital():

    CÓDIGO ATUAL:
    ```python
    # Link do leiloeiro (se disponivel)
    link_sistema = detalhes.get("linkSistema") or detalhes.get("linkEdital")
    if link_sistema and "pncp.gov" not in link_sistema:
        edital["link_leiloeiro"] = link_sistema
    ```

3. Substitua pelo código abaixo:

    CÓDIGO NOVO (V19):
    ```python
    # Link do leiloeiro COM VALIDAÇÃO V19
    link_sistema = detalhes.get("linkSistema")
    link_edital = detalhes.get("linkEdital")
    
    resultado_link = processar_link_pncp(
        link_sistema=link_sistema,
        link_edital=link_edital,
        pncp_id=pncp_id,
    )
    
    # Aplicar resultados ao edital
    edital["link_leiloeiro"] = resultado_link["link_leiloeiro"]
    edital["link_leiloeiro_raw"] = resultado_link["link_leiloeiro_raw"]
    edital["link_leiloeiro_valido"] = resultado_link["link_leiloeiro_valido"]
    edital["link_leiloeiro_origem_tipo"] = resultado_link["link_leiloeiro_origem_tipo"]
    edital["link_leiloeiro_origem_ref"] = resultado_link["link_leiloeiro_origem_ref"]
    edital["link_leiloeiro_confianca"] = resultado_link["link_leiloeiro_confianca"]
    ```

4. Atualize a versão no repositório de persistência para incluir os novos campos.

5. Execute a migration SQL (migration_auditor_v19.sql) antes de usar o Miner atualizado.
"""


# ============================================================
# TESTES UNITÁRIOS
# ============================================================

def _executar_testes():
    """Executa testes básicos de validação."""
    print("=" * 60)
    print("TESTES DE VALIDAÇÃO DE URL V19")
    print("=" * 60)
    
    casos_teste = [
        # (URL, esperado_valido, descricao)
        ("https://lopesleiloes.net.br/leilao/123", True, "URL completa com https"),
        ("www.exemplo.com.br/lances", True, "URL com www"),
        ("https://sub.dominio.com/path?x=1", True, "URL com subdomínio"),
        ("superbid.net", True, "Domínio whitelist sem prefixo"),
        ("VENEZUELANO-ED.COMEMORA", False, "TLD colado em palavra"),
        ("ED.COMEMORA", False, "TLD colado em palavra (curto)"),
        ("ABC.NETAMENTE", False, "TLD .NET colado"),
        ("dominio-aleatorio.com", False, "Domínio sem prefixo e fora whitelist"),
        ("", False, "URL vazia"),
        (None, False, "URL None"),
        ("https://pncp.gov.br/edital/123", True, "URL PNCP (válida mas filtrada)"),
        ("lanceleiloes.com.br", True, "Whitelist sem prefixo"),
    ]
    
    total = len(casos_teste)
    passou = 0
    
    for url, esperado, descricao in casos_teste:
        valido, confianca, motivo = validar_url_link_leiloeiro(url) if url else (False, 0, "url_none")
        
        # Para o teste, tratamos URLs PNCP como válidas no validador
        # (o filtro de PNCP é feito separadamente)
        resultado_ok = valido == esperado
        
        status = "✓" if resultado_ok else "✗"
        passou += 1 if resultado_ok else 0
        
        print(f"{status} {descricao}")
        print(f"   URL: {url}")
        print(f"   Esperado: {esperado} | Obtido: {valido} (conf={confianca})")
        if motivo:
            print(f"   Motivo: {motivo}")
        print()
    
    print("=" * 60)
    print(f"RESULTADO: {passou}/{total} testes passaram")
    print("=" * 60)
    
    return passou == total


if __name__ == "__main__":
    # Executar testes se rodado diretamente
    sucesso = _executar_testes()
    exit(0 if sucesso else 1)
