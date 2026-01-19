#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CORREÇÕES CRÍTICAS V12 - EMERGENCIAL
Foco: data_leilao (CRÍTICO!) e link_pncp
"""

import re
from pathlib import Path

# Ler arquivo v12_final
v12_path = Path("local_auditor_v12_final.py")

with open(v12_path, 'r', encoding='utf-8') as f:
    conteudo = f.read()

print("[INFO] Aplicando correções críticas...")

# =============================================================================
# CORREÇÃO #1: MELHORAR EXTRAÇÃO DE data_leilao
# =============================================================================

# Adicionar padrões de data MUITO mais agressivos
novo_extrair_data_leilao = '''def extrair_data_leilao_cascata_v12(json_data: dict, pdf_text: str, excel_data: dict, descricao: str = "") -> str:
    """
    V12 BUG #1 CRÍTICO: Cascata de extração para data_leilao.
    SEM ESSA DATA NÃO EXISTE ACHE SUCATAS!

    Ordem de prioridade:
    1. JSON PNCP (campos de data)
    2. DESCRIÇÃO (primeiro, pois vem do JSON)
    3. Excel/CSV anexo
    4. PDF com padrões agressivos
    """
    from local_auditor_v12_final import formatar_data_br

    # FONTE 1: JSON PNCP - Prioridade máxima
    campos_json = [
        'dataAberturaProposta', 'dataAberturaPropostas', 'data_inicio_propostas',
        'dataEncerramentoProposta', 'dataInicioVigencia',
        'dataFimProposta', 'dataFimPropostas',
        'dataRealizacao', 'dataLeilao'
    ]
    for campo in campos_json:
        if json_data.get(campo):
            data_formatada = formatar_data_br(json_data[campo])
            if data_formatada != "N/D":
                return data_formatada

    # FONTE 2: DESCRIÇÃO (texto do JSON) - MUITO IMPORTANTE!
    if descricao:
        # Padrões específicos de leilão
        padroes_desc = [
            r'(?:leil[ãa]o.*?dia|dia.*?leil[ãa]o).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(?:realizar[aá]|ocorrer[aá]).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(?:data|dia).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2}).*?(?:leil[ãa]o|hasta|arremata)',
            r'(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2}).*?(?:às|as|hora|h)\s*\d{1,2}',
        ]

        for padrao in padroes_desc:
            match = re.search(padrao, descricao[:2000], re.IGNORECASE | re.DOTALL)
            if match:
                data_formatada = formatar_data_br(match.group(1))
                if data_formatada != "N/D":
                    return data_formatada

    # FONTE 3: Excel/CSV anexo
    if excel_data:
        colunas_data = [c for c in excel_data.keys() if 'data' in c.lower() or 'leilao' in c.lower()]
        for col in colunas_data:
            if excel_data[col] and excel_data[col] != 'N/D':
                data_formatada = formatar_data_br(excel_data[col])
                if data_formatada != "N/D":
                    return data_formatada

    # FONTE 4: PDF - PADRÕES MUITO AGRESSIVOS
    if pdf_text:
        # Lista de padrões ordenados por especificidade
        padroes_pdf = [
            # Padrão 1: "data do leilão: DD/MM/YYYY"
            r'(?:data\s*(?:do|de)\s*leil[ãa]o)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 2: "leilão dia DD/MM/YYYY"
            r'(?:leil[ãa]o|hasta|pregão).*?(?:dia|data)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 3: "será realizado em DD/MM/YYYY"
            r'(?:será|ser[aá])\s*realizado.*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 4: "ocorrerá no dia DD/MM/YYYY"
            r'(?:ocorrer[aá]|realizar[aá]).*?(?:dia|em)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 5: "abertura" ou "sessão" com data
            r'(?:abertura|sessão|sess[ãa]o)[:\s]*.*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 6: Data seguida de horário (forte indicativo)
            r'(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})[,\s]*(?:às|as|[àa]s|hora)[:\s]*\d{1,2}',

            # Padrão 7: "dia DD/MM/YYYY às HH"
            r'dia\s*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})\s*[àa]s?\s*\d{1,2}',

            # Padrão 8: Formato de convocação
            r'(?:comparecer|participar).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 9: Data em contexto de evento
            r'(?:no\s*dia|na\s*data)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',

            # Padrão 10: AGRESSIVO - Primeira data válida após palavra-chave
            r'(?:leil[ãa]o|hasta|arremata|aliena|pregão|venda)(?:.*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})){1}',

            # Padrão 11: MUITO AGRESSIVO - Qualquer data DD/MM/20YY nos primeiros 3000 chars
            r'(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
        ]

        # Buscar nos primeiros 5000 caracteres (geralmente a data está no início)
        texto_busca = pdf_text[:5000]

        for padrao in padroes_pdf:
            matches = re.finditer(padrao, texto_busca, re.IGNORECASE | re.DOTALL)
            for match in matches:
                data_str = match.group(1)
                data_formatada = formatar_data_br(data_str)
                if data_formatada != "N/D":
                    # Validar se é uma data futura ou recente (não muito antiga)
                    try:
                        from datetime import datetime
                        partes = data_formatada.split('/')
                        data_obj = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
                        # Aceitar datas de 2020 em diante
                        if data_obj.year >= 2020:
                            return data_formatada
                    except:
                        # Se falhar a validação, ainda retorna
                        return data_formatada

    return "N/D"'''

# Substituir a função antiga
inicio_antiga = conteudo.find('def extrair_data_leilao_cascata_v12(')
if inicio_antiga != -1:
    # Encontrar o fim da função (próxima def ou fim de bloco)
    fim_antiga = conteudo.find('\n\ndef ', inicio_antiga + 1)
    if fim_antiga == -1:
        fim_antiga = conteudo.find('\n\n\nclass ', inicio_antiga + 1)

    if fim_antiga != -1:
        conteudo = conteudo[:inicio_antiga] + novo_extrair_data_leilao + '\n\n' + conteudo[fim_antiga:]
        print("[OK] Função extrair_data_leilao_cascata_v12 MELHORADA")

# =============================================================================
# CORREÇÃO #2: FORÇAR CORREÇÃO DO link_pncp
# =============================================================================

# Modificar montar_link_pncp_v12 para ser mais robusto
novo_montar_pncp = '''def montar_link_pncp_v12(cnpj: str, ano: str, sequencial: str) -> str:
    """
    V12 BUG #3 CRÍTICO: Monta link PNCP no formato OFICIAL CORRETO.

    Formato: https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}
    Exemplo: https://pncp.gov.br/app/editais/88150495000186/2025/000490
    """
    # Limpar CNPJ (apenas números, 14 dígitos)
    cnpj_limpo = re.sub(r'\\D', '', str(cnpj))
    if len(cnpj_limpo) != 14:
        return "N/D"

    # Limpar e validar ano (4 dígitos)
    ano_limpo = re.sub(r'\\D', '', str(ano))
    if len(ano_limpo) != 4:
        return "N/D"

    # Limpar sequencial (remover zeros à esquerda mas manter se for só zeros)
    sequencial_limpo = re.sub(r'\\D', '', str(sequencial))
    if not sequencial_limpo:
        return "N/D"

    # Remover zeros à esquerda
    sequencial_limpo = sequencial_limpo.lstrip('0') or '0'

    # FORMATO CORRETO: /CNPJ/ANO/SEQUENCIAL (sem zeros à esquerda no sequencial)
    return f"https://pncp.gov.br/app/editais/{cnpj_limpo}/{ano_limpo}/{sequencial_limpo}"'''

# Substituir função antiga
inicio_antiga = conteudo.find('def montar_link_pncp_v12(')
if inicio_antiga != -1:
    fim_antiga = conteudo.find('\n\ndef ', inicio_antiga + 1)
    if fim_antiga != -1:
        conteudo = conteudo[:inicio_antiga] + novo_montar_pncp + '\n\n' + conteudo[fim_antiga:]
        print("[OK] Função montar_link_pncp_v12 MELHORADA")

# Melhorar extrair_componentes_pncp_v12 para extrair do link antigo também
novo_extrair_componentes = '''def extrair_componentes_pncp_v12(json_data: dict, path_metadata: dict, link_pncp_atual: str = "") -> tuple:
    """
    V12 BUG #3: Extrai CNPJ, ANO e SEQUENCIAL das fontes disponíveis.
    Incluindo extração do link_pncp atual se estiver no formato antigo.
    """
    # Tentar extrair do link_pncp atual (formato antigo: /CNPJ-MODALIDADE-SEQUENCIAL/ANO)
    if link_pncp_atual and 'pncp.gov.br' in link_pncp_atual:
        # Formato: https://pncp.gov.br/app/editais/04302189000128-1-000019/2025
        match = re.search(r'/editais/([\\d]+)[-\\d]+-([\\d]+)/(\\d{4})', link_pncp_atual)
        if match:
            cnpj_link = match.group(1)
            sequencial_link = match.group(2)
            ano_link = match.group(3)
            return cnpj_link, ano_link, sequencial_link

    # CNPJ do órgão
    cnpj = (
        json_data.get('orgaoEntidade', {}).get('cnpj') if isinstance(json_data.get('orgaoEntidade'), dict) else None or
        json_data.get('cnpjOrgao') or
        json_data.get('cnpj') or
        json_data.get('orgao_cnpj') or
        path_metadata.get('cnpj') or
        ''
    )

    # ANO da publicação
    ano = (
        json_data.get('anoCompra') or
        str(json_data.get('dataPublicacaoPncp', ''))[:4] or
        str(json_data.get('data_publicacao', ''))[:4] or
        path_metadata.get('ano') or
        ''
    )

    # SEQUENCIAL da compra
    sequencial = (
        json_data.get('sequencialCompra') or
        json_data.get('numeroCompra') or
        json_data.get('sequencial') or
        path_metadata.get('sequencial') or
        ''
    )

    return cnpj, ano, sequencial'''

# Substituir função antiga
inicio_antiga = conteudo.find('def extrair_componentes_pncp_v12(')
if inicio_antiga != -1:
    fim_antiga = conteudo.find('\n\ndef ', inicio_antiga + 1)
    if fim_antiga != -1:
        conteudo = conteudo[:inicio_antiga] + novo_extrair_componentes + '\n\n' + conteudo[fim_antiga:]
        print("[OK] Função extrair_componentes_pncp_v12 MELHORADA")

# =============================================================================
# CORREÇÃO #3: FORÇAR OVERRIDE NO PROCESSAR_EDITAL
# =============================================================================

# Encontrar a seção onde corrige link_pncp e modificar para SEMPRE sobrescrever
secao_antiga = '''    # BUG #3: Corrigir link_pncp para formato /CNPJ/ANO/SEQUENCIAL
    cnpj, ano, sequencial = extrair_componentes_pncp_v12(json_data, path_data)
    if cnpj and ano and sequencial:
        link_pncp_correto = montar_link_pncp_v12(cnpj, ano, sequencial)
        if link_pncp_correto != "N/D":
            dados_finais["link_pncp"] = link_pncp_correto
            campos_encontrados.append("link_pncp(V12_CORRIGIDO)")'''

secao_nova = '''    # BUG #3: Corrigir link_pncp para formato /CNPJ/ANO/SEQUENCIAL
    # CRÍTICO: SEMPRE sobrescrever o link_pncp, mesmo que já exista!
    cnpj, ano, sequencial = extrair_componentes_pncp_v12(
        json_data, path_data, dados_finais.get("link_pncp", "")
    )
    if cnpj and ano and sequencial:
        link_pncp_correto = montar_link_pncp_v12(cnpj, ano, sequencial)
        if link_pncp_correto != "N/D":
            dados_finais["link_pncp"] = link_pncp_correto  # SEMPRE sobrescrever!
            campos_encontrados.append("link_pncp(V12_CORRIGIDO)")'''

conteudo = conteudo.replace(secao_antiga, secao_nova)
print("[OK] Override forçado de link_pncp implementado")

# Salvar arquivo corrigido
with open(v12_path, 'w', encoding='utf-8') as f:
    f.write(conteudo)

print("\n" + "="*70)
print("CORREÇÕES CRÍTICAS APLICADAS COM SUCESSO!")
print("="*70)
print("[OK] data_leilao: 11 padrões agressivos de extração")
print("[OK] link_pncp: Extração do formato antigo + sempre sobrescrever")
print("\n[PRÓXIMO PASSO] Reprocessar todos os editais:")
print("  python local_auditor_v12_final.py")
print("="*70)
