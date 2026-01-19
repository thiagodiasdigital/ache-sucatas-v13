#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para aplicar todas as correções V12 ao local_auditor_v11.py
"""

import re
from pathlib import Path

# Ler arquivo v11
v11_path = Path(r"C:\Users\Larissa\Desktop\testes-12-01-17h\local_auditor_v11.py")
v12_path = Path(r"C:\Users\Larissa\Desktop\testes-12-01-17h\local_auditor_v12_final.py")

with open(v11_path, 'r', encoding='utf-8') as f:
    conteudo = f.read()

# 1. Atualizar cabeçalho
conteudo = conteudo.replace(
    'ACHE SUCATAS DaaS - AUDITOR V11',
    'ACHE SUCATAS DaaS - AUDITOR V12 - CORREÇÕES CRÍTICAS'
)

# 2. Atualizar CSV_OUTPUT
conteudo = conteudo.replace(
    'analise_editais_v11.csv',
    'analise_editais_v12.csv'
)

# 3. Adicionar constantes V12 após KEYWORDS_LEILOEIRO
adicao_constantes = """

# V12: Lista de domínios PROIBIDOS (não são sites de leiloeiros)
DOMINIOS_INVALIDOS = {
    'hotmail.com', 'hotmail.com.br',
    'yahoo.com', 'yahoo.com.br',
    'gmail.com', 'outlook.com',
    'uol.com.br', 'bol.com.br',
    'terra.com.br', 'ig.com.br',
    'globo.com', 'msn.com',
    'live.com', 'icloud.com'
}

# V12: Dicionário de tags específicas
MAPA_TAGS = {
    'sucata': ['sucata', 'sucateamento'],
    'documentado': ['documentado', 'com documento'],
    'sem_documento': ['sem documento', 'indocumentado'],
    'sinistrado': ['sinistrado', 'acidentado'],
    'automovel': ['automóvel', 'automovel', 'carro'],
    'motocicleta': ['motocicleta', 'moto'],
    'caminhao': ['caminhão', 'caminhao'],
    'onibus': ['ônibus', 'onibus'],
    'utilitario': ['utilitário', 'pick-up', 'van'],
    'apreendido': ['apreendido', 'apreensão']
}
"""

# Inserir após KEYWORDS_LEILOEIRO
if 'KEYWORDS_LEILOEIRO' in conteudo and 'DOMINIOS_INVALIDOS' not in conteudo:
    conteudo = conteudo.replace(']', ']' + adicao_constantes, 1)

# 4. Adicionar novos campos ao dataclass ResultadoEdital
if 'modalidade_leilao: str' not in conteudo:
    conteudo = conteudo.replace(
        'link_pncp: str = "N/D"\n    arquivo_origem',
        'link_pncp: str = "N/D"\n    modalidade_leilao: str = "N/D"\n    valor_estimado: str = "N/D"\n    quantidade_itens: str = "N/D"\n    nome_leiloeiro: str = "N/D"\n    arquivo_origem'
    )

# 5. Atualizar as_dict
if '"modalidade_leilao"' not in conteudo:
    conteudo = conteudo.replace(
        '"link_pncp": self.link_pncp,\n            "arquivo_origem"',
        '"link_pncp": self.link_pncp,\n            "modalidade_leilao": self.modalidade_leilao,\n            "valor_estimado": self.valor_estimado,\n            "quantidade_itens": self.quantidade_itens,\n            "nome_leiloeiro": self.nome_leiloeiro,\n            "arquivo_origem"'
    )

# 6. Salvar v12
with open(v12_path, 'w', encoding='utf-8') as f:
    f.write(conteudo)

print(f"[OK] Arquivo criado: {v12_path}")
print(f"[OK] Total de linhas: {len(conteudo.splitlines())}")
print("[OK] Modificações aplicadas!")
print("\n[INFO] Próximo passo: Adicionar manualmente as funções V12 de extração")
print("       (extrair_modalidade_v12, extrair_valor_estimado_v12, etc.)")
