#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analisa padrões de link_leiloeiro para extrair nomes de leiloeiros.
"""

import pandas as pd
import re
from urllib.parse import urlparse

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("ANALISE DE PADROES: link_leiloeiro -> nome_leiloeiro")
print("="*80)
print()

# Filtrar apenas links válidos (não N/D, não PRESENCIAL)
links_validos = df[(df['link_leiloeiro'] != 'N/D') & (df['link_leiloeiro'] != 'PRESENCIAL')]

print(f"Links validos para analise: {len(links_validos)}/{len(df)} ({(len(links_validos)/len(df))*100:.1f}%)")
print()

# Pegar links únicos
links_unicos = links_validos['link_leiloeiro'].unique()

print(f"Links unicos: {len(links_unicos)}")
print()

# Analisar padrões de domínio
print("="*80)
print("PADROES DE DOMINIO")
print("="*80)
print()

padroes = {}

for link in links_unicos[:30]:  # Analisar 30 primeiros
    try:
        parsed = urlparse(link)
        dominio = parsed.netloc or parsed.path
        dominio = dominio.replace('www.', '')

        # Extrair possível nome do leiloeiro do domínio
        possivel_nome = None

        # Padrão 1: fernandoleiloeiro.com.br -> Fernando
        match = re.match(r'^([a-z]+)leiloeir[oa]\.', dominio, re.IGNORECASE)
        if match:
            possivel_nome = match.group(1).capitalize()
            padrao = "Padrao 1: [nome]leiloeiro.com"

        # Padrão 2: lopesleiloes.net.br -> Lopes
        if not possivel_nome:
            match = re.match(r'^([a-z]+)leiloes\.', dominio, re.IGNORECASE)
            if match:
                possivel_nome = match.group(1).capitalize()
                padrao = "Padrao 2: [nome]leiloes.com"

        # Padrão 3: leiloes[nome].com.br -> [Nome]
        if not possivel_nome:
            match = re.match(r'^leiloes([a-z]+)\.', dominio, re.IGNORECASE)
            if match:
                possivel_nome = match.group(1).capitalize()
                padrao = "Padrao 3: leiloes[nome].com"

        # Padrão 4: [nome]lances.com.br -> [Nome]
        if not possivel_nome:
            match = re.match(r'^([a-z]+)lances\.', dominio, re.IGNORECASE)
            if match:
                possivel_nome = match.group(1).capitalize()
                padrao = "Padrao 4: [nome]lances.com"

        # Padrão 5: Siglas (2-5 letras) + leiloes -> Sigla em maiúsculas
        if not possivel_nome:
            match = re.match(r'^([a-z]{2,5})leiloes\.', dominio, re.IGNORECASE)
            if match:
                possivel_nome = match.group(1).upper() + " Leilões"
                padrao = "Padrao 5: [sigla]leiloes.com (ex: KC)"

        # Padrão 6: gestaodeleiloes.com.br -> Gestão de Leilões
        if not possivel_nome:
            if 'gestao' in dominio.lower():
                possivel_nome = "Gestão de Leilões"
                padrao = "Padrao 6: gestaodeleiloes.com"

        # Padrão 7: Nomes compostos: serpaleiloes -> SERPA
        if not possivel_nome:
            match = re.match(r'^([a-z]+?)(?:leiloes|leiloeiro|lances)', dominio, re.IGNORECASE)
            if match:
                possivel_nome = match.group(1).upper()
                padrao = "Padrao 7: nome generico"

        if possivel_nome:
            print(f"{link[:50]:50s}")
            print(f"  Dominio: {dominio}")
            print(f"  Nome extraido: {possivel_nome}")
            print(f"  {padrao}")
            print()

            if padrao not in padroes:
                padroes[padrao] = []
            padroes[padrao].append((dominio, possivel_nome))

    except Exception as e:
        continue

print("="*80)
print("RESUMO DOS PADROES IDENTIFICADOS")
print("="*80)
print()

for padrao, exemplos in padroes.items():
    print(f"{padrao}: {len(exemplos)} ocorrencias")
    for dominio, nome in exemplos[:3]:
        print(f"  - {dominio} -> {nome}")
    print()

print("="*80)
print("FUNCAO PROPOSTA: extrair_nome_do_link()")
print("="*80)
print()

print("""
def extrair_nome_do_link(link: str) -> str:
    \"\"\"
    Extrai o nome do leiloeiro a partir do link.

    Exemplos:
    - www.fernandoleiloeiro.com.br -> Fernando Leiloeiro
    - www.lopesleiloes.net.br -> Lopes Leilões
    - www.kcleiloes.com.br -> KC Leilões
    - www.gestaodeleiloes.com.br -> Gestão de Leilões
    \"\"\"
    if not link or link in ['N/D', 'PRESENCIAL']:
        return "N/D"

    try:
        from urllib.parse import urlparse
        import re

        parsed = urlparse(link)
        dominio = (parsed.netloc or parsed.path).replace('www.', '')

        # Padrão 1: [nome]leiloeiro.com
        match = re.match(r'^([a-z]+)leiloeir[oa]\\\.', dominio, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() + " Leiloeiro"

        # Padrão 2: [nome]leiloes.com
        match = re.match(r'^([a-z]+)leiloes\\\.', dominio, re.IGNORECASE)
        if match:
            nome = match.group(1)
            if len(nome) <= 4:  # Sigla
                return nome.upper() + " Leilões"
            return nome.capitalize() + " Leilões"

        # Padrão 3: leiloes[nome].com
        match = re.match(r'^leiloes([a-z]+)\\\.', dominio, re.IGNORECASE)
        if match:
            return "Leilões " + match.group(1).capitalize()

        # Padrão 4: [nome]lances.com
        match = re.match(r'^([a-z]+)lances\\\.', dominio, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() + " Lances"

        # Padrão 5: gestaodeleiloes -> Gestão de Leilões
        if 'gestao' in dominio.lower():
            return "Gestão de Leilões"

        return "N/D"

    except:
        return "N/D"
""")

print()
print("="*80)
print("TESTE DA FUNCAO (simulacao)")
print("="*80)
print()

# Testar função em 10 links
teste_links = links_unicos[:10]

def extrair_nome_do_link(link: str) -> str:
    if not link or link in ['N/D', 'PRESENCIAL']:
        return "N/D"

    try:
        from urllib.parse import urlparse
        import re

        parsed = urlparse(link)
        dominio = (parsed.netloc or parsed.path).replace('www.', '')

        # Padrão 1: [nome]leiloeiro.com
        match = re.match(r'^([a-z]+)leiloeir[oa]\.', dominio, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() + " Leiloeiro"

        # Padrão 2: [nome]leiloes.com
        match = re.match(r'^([a-z]+)leiloes\.', dominio, re.IGNORECASE)
        if match:
            nome = match.group(1)
            if len(nome) <= 4:  # Sigla
                return nome.upper() + " Leilões"
            return nome.capitalize() + " Leilões"

        # Padrão 3: leiloes[nome].com
        match = re.match(r'^leiloes([a-z]+)\.', dominio, re.IGNORECASE)
        if match:
            return "Leilões " + match.group(1).capitalize()

        # Padrão 4: [nome]lances.com
        match = re.match(r'^([a-z]+)lances\.', dominio, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() + " Lances"

        # Padrão 5: gestaodeleiloes
        if 'gestao' in dominio.lower():
            return "Gestão de Leilões"

        return "N/D"

    except:
        return "N/D"

for link in teste_links:
    nome = extrair_nome_do_link(link)
    print(f"{link[:45]:45s} -> {nome}")

print()
print("="*80)
