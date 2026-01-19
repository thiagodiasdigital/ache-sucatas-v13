#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FUNÇÕES AUXILIARES V12 - CORREÇÕES CRÍTICAS
Funções novas e melhoradas para o Auditor V12
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse


def validar_link_leiloeiro(url: str, modalidade: str = "", local_realizacao: str = "", descricao: str = "") -> str:
    """
    V12 BUG #2: Valida link do leiloeiro com lógica condicional.
    - Leilão ONLINE: link obrigatório
    - Leilão PRESENCIAL: link pode ser "PRESENCIAL" (ausência válida)
    - Rejeita domínios de email (hotmail, yahoo, gmail, etc)
    """
    from local_auditor_v12 import DOMINIOS_INVALIDOS, detectar_leilao_presencial

    # Detectar se é presencial
    eh_presencial = detectar_leilao_presencial(modalidade, local_realizacao, descricao)

    if not url or url.strip() == '' or url == 'N/D':
        if eh_presencial:
            return "PRESENCIAL"
        return "N/D"

    # Normalizar URL
    url = url.strip().lower()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Extrair domínio
    try:
        dominio = urlparse(url).netloc.replace('www.', '')
    except:
        return "PRESENCIAL" if eh_presencial else "N/D"

    # Verificar se domínio é inválido (email)
    if dominio in DOMINIOS_INVALIDOS:
        if eh_presencial:
            return "PRESENCIAL"
        return "N/D"

    # Verificar se parece um site real
    if '.' not in dominio or len(dominio) < 4:
        if eh_presencial:
            return "PRESENCIAL"
        return "N/D"

    return url


def montar_link_pncp(cnpj: str, ano: str, sequencial: str) -> str:
    """
    V12 BUG #3: Monta link PNCP no formato OFICIAL CORRETO.

    Formato: https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}

    Exemplo correto:
    - CNPJ: 00394460000141
    - ANO: 2024
    - SEQUENCIAL: 1
    - Resultado: https://pncp.gov.br/app/editais/00394460000141/2024/1
    """
    # Limpar CNPJ (apenas números)
    cnpj_limpo = re.sub(r'\D', '', str(cnpj))

    # Validar CNPJ (14 dígitos)
    if len(cnpj_limpo) != 14:
        return "N/D"

    # Limpar e validar ano
    ano_limpo = str(ano).strip()
    if not ano_limpo.isdigit() or len(ano_limpo) != 4:
        return "N/D"

    # Limpar sequencial
    sequencial_limpo = str(sequencial).strip()
    if not sequencial_limpo.isdigit():
        return "N/D"

    # FORMATO CORRETO: /CNPJ/ANO/SEQUENCIAL
    return f"https://pncp.gov.br/app/editais/{cnpj_limpo}/{ano_limpo}/{sequencial_limpo}"


def extrair_componentes_pncp(json_data: dict, path_metadata: dict) -> tuple:
    """
    V12 BUG #3: Extrai CNPJ, ANO e SEQUENCIAL das fontes disponíveis.
    """
    # CNPJ do órgão
    cnpj = (
        json_data.get('orgaoEntidade', {}).get('cnpj') or
        json_data.get('cnpjOrgao') or
        json_data.get('cnpj') or
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

    return cnpj, ano, sequencial


def extrair_tags_inteligente(descricao: str, pdf_text: str, titulo: str) -> str:
    """
    V12 BUG #4: Extrai tags específicas do conteúdo real do edital.
    Retorna lista de tags separadas por vírgula.
    """
    from local_auditor_v12 import MAPA_TAGS

    # Combinar todas as fontes de texto
    texto_completo = f"{titulo} {descricao} {pdf_text[:3000]}".lower()

    tags_encontradas = set()

    for tag, palavras_chave in MAPA_TAGS.items():
        for palavra in palavras_chave:
            if palavra.lower() in texto_completo:
                tags_encontradas.add(tag)
                break  # Evita duplicatas da mesma categoria

    # Garantir pelo menos uma tag
    if not tags_encontradas:
        # Análise de fallback
        if 'veículo' in texto_completo or 'veiculo' in texto_completo:
            tags_encontradas.add('veiculo')
        if 'leilão' in texto_completo or 'leilao' in texto_completo:
            tags_encontradas.add('leilao')

    # Se ainda vazio, usar tag genérica com aviso
    if not tags_encontradas:
        return "sem_classificacao"

    return ','.join(sorted(tags_encontradas))


def extrair_titulo_inteligente(pdf_text: str, json_data: dict, n_edital: str) -> str:
    """
    V12 BUG #5: Extrai título da primeira linha do PDF, limitado a 100 caracteres.

    Prioridade:
    1. Primeira linha significativa do PDF
    2. Objeto resumido do JSON
    3. Fallback para "Edital nº X"
    """
    # FONTE 1: Primeira linha do PDF
    if pdf_text:
        linhas = pdf_text.strip().split('\n')
        for linha in linhas[:10]:  # Procurar nas primeiras 10 linhas
            linha_limpa = linha.strip()
            # Ignorar linhas muito curtas ou só com números
            if len(linha_limpa) > 20 and not linha_limpa.replace(' ', '').isdigit():
                # Ignorar cabeçalhos genéricos
                ignorar = ['ministério', 'secretaria', 'governo', 'estado', 'página', 'pag.', 'poder executivo']
                if not any(ig in linha_limpa.lower() for ig in ignorar):
                    return linha_limpa[:100]

    # FONTE 2: Objeto do JSON PNCP
    objeto = json_data.get('objetoCompra', '') or json_data.get('objeto', '')
    if objeto and len(objeto) > 20:
        return objeto[:100]

    # FONTE 3: Fallback
    return f"Edital nº {n_edital}" if n_edital else "Edital sem identificação"


def extrair_modalidade(json_data: dict, pdf_text: str, descricao: str = "") -> str:
    """
    V12: Retorna: ONLINE | PRESENCIAL | HÍBRIDO | N/D
    """
    texto = f"{json_data.get('modalidadeNome', '')} {pdf_text[:2000]} {descricao}".lower()

    tem_online = any(x in texto for x in ['eletrônico', 'eletronico', 'online', 'internet', 'virtual', 'plataforma digital'])
    tem_presencial = any(x in texto for x in ['presencial', 'sede', 'auditório', 'sala', 'comparecimento', 'local:'])

    if tem_online and tem_presencial:
        return "HÍBRIDO"
    elif tem_online:
        return "ONLINE"
    elif tem_presencial:
        return "PRESENCIAL"
    return "N/D"


def extrair_valor_estimado(json_data: dict, pdf_text: str) -> str:
    """
    V12: Extrai valor estimado/mínimo do leilão.
    """
    # JSON primeiro
    valor = json_data.get('valorTotalEstimado') or json_data.get('valorEstimado') or json_data.get('valorTotal')
    if valor:
        try:
            valor_float = float(valor)
            return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            pass

    # PDF com regex
    padrao = r'(?:valor|lance|mínimo|avaliação|avaliacao|estimado)[:\s]*R?\$?\s*([\d.,]+)'
    match = re.search(padrao, pdf_text[:3000], re.IGNORECASE)
    if match:
        valor_str = match.group(1).replace('.', '').replace(',', '.')
        try:
            valor_float = float(valor_str)
            return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            pass

    return "N/D"


def extrair_quantidade_itens(json_data: dict, pdf_text: str) -> str:
    """
    V12: Extrai quantidade de itens/lotes do leilão.
    """
    qtd = json_data.get('quantidadeItens') or json_data.get('numeroItens')
    if qtd:
        return str(qtd)

    # Contar "LOTE" no PDF
    lotes = len(re.findall(r'\bLOTE\s*\d+', pdf_text[:5000], re.IGNORECASE))
    if lotes > 0:
        return str(lotes)

    # Contar "ITEM" no PDF
    itens = len(re.findall(r'\bITEM\s*\d+', pdf_text[:5000], re.IGNORECASE))
    if itens > 0:
        return str(itens)

    return "N/D"


def extrair_nome_leiloeiro(json_data: dict, pdf_text: str) -> str:
    """
    V12: Extrai nome do leiloeiro oficial.
    """
    # JSON
    leiloeiro = json_data.get('nomeLeiloeiro') or json_data.get('leiloeiro') or json_data.get('responsavel')
    if leiloeiro:
        return str(leiloeiro).strip()[:100]

    # PDF - procurar padrão "Leiloeiro: Nome Completo"
    padrao = r'(?:leiloeiro|leiloeira)[:\s]*(?:oficial|público|a)?\s*[:\s]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})'
    match = re.search(padrao, pdf_text[:3000])
    if match:
        return match.group(1).strip()[:100]

    # PDF - procurar padrão "Responsável: Nome Completo"
    padrao2 = r'(?:responsável|responsavel)[:\s]*(?:pelo\s+leilão|pela\s+venda)?\s*[:\s]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})'
    match2 = re.search(padrao2, pdf_text[:3000], re.IGNORECASE)
    if match2:
        return match2.group(1).strip()[:100]

    return "N/D"


def extrair_data_leilao_cascata(json_data: dict, pdf_text: str, excel_data: dict, descricao: str = "") -> str:
    """
    V12 BUG #1: Cascata de extração para data_leilao.
    1. JSON PNCP: campos dataAberturaProposta, dataEncerramentoProposta, dataInicioVigencia
    2. Excel/CSV anexo: colunas com "data", "leilao", "abertura"
    3. PDF: regex para padrões brasileiros de data
    """
    from local_auditor_v12 import formatar_data_br

    # FONTE 1: JSON PNCP (prioridade máxima)
    campos_json = [
        'dataAberturaProposta',
        'dataAberturaPropostas',
        'data_inicio_propostas',
        'dataEncerramentoProposta',
        'dataInicioVigencia',
        'dataPublicacaoPncp',
        'dataInclusao'
    ]
    for campo in campos_json:
        if json_data.get(campo):
            data_formatada = formatar_data_br(json_data[campo])
            if data_formatada != "N/D":
                return data_formatada

    # FONTE 2: Excel/CSV anexo
    if excel_data:
        colunas_data = [c for c in excel_data.keys() if 'data' in c.lower() or 'leilao' in c.lower()]
        for col in colunas_data:
            if excel_data[col] and excel_data[col] != 'N/D':
                data_formatada = formatar_data_br(excel_data[col])
                if data_formatada != "N/D":
                    return data_formatada

    # FONTE 3: PDF com regex robusto
    padroes_data = [
        r'(?:data\s*(?:do\s*)?leil[aã]o|abertura|sess[aã]o)[:\s]*(\d{2}[/.-]\d{2}[/.-]\d{4})',
        r'(?:realizar[aá]|ocorrer[aá]|ser[aá]\s*realizado)[^\d]*(\d{2}[/.-]\d{2}[/.-]\d{4})',
        r'dia\s*(\d{2}[/.-]\d{2}[/.-]\d{4})\s*[àa]s?\s*\d{1,2}[h:]',
        r'(\d{2}[/.-]\d{2}[/.-]\d{4})\s*[àa]s?\s*\d{1,2}[h:]\d{2}',
    ]
    for padrao in padroes_data:
        match = re.search(padrao, pdf_text[:5000], re.IGNORECASE)
        if match:
            data_formatada = formatar_data_br(match.group(1))
            if data_formatada != "N/D":
                return data_formatada

    # FONTE 4: Descrição (última opção)
    if descricao:
        from local_auditor_v12 import extrair_data_de_texto
        data_desc = extrair_data_de_texto(descricao)
        if data_desc:
            return data_desc

    return "N/D"


def extrair_data_atualizacao_cascata(json_data: dict) -> str:
    """
    V12 BUG #1: Data de atualização vem EXCLUSIVAMENTE do JSON PNCP.
    """
    from local_auditor_v12 import formatar_data_br

    campos = ['dataAtualizacao', 'dataModificacao', 'dataUltimaAtualizacao', 'data_atualizacao']
    for campo in campos:
        if json_data.get(campo):
            data_formatada = formatar_data_br(json_data[campo])
            if data_formatada != "N/D":
                return data_formatada

    # Fallback: usar data de publicação como última opção
    if json_data.get('dataPublicacaoPncp') or json_data.get('data_publicacao'):
        data_pub = json_data.get('dataPublicacaoPncp') or json_data.get('data_publicacao')
        data_formatada = formatar_data_br(data_pub)
        if data_formatada != "N/D":
            return data_formatada

    return "N/D"


def validar_registro_completo(registro: dict) -> dict:
    """
    V12: Validação final de todos os campos obrigatórios.
    Retorna registro com estatísticas de qualidade.
    """
    campos_obrigatorios = [
        'id_interno', 'orgao', 'uf', 'cidade', 'n_pncp', 'n_edital',
        'data_publicacao', 'data_atualizacao', 'data_leilao', 'titulo',
        'descricao', 'tags', 'link_pncp', 'link_leiloeiro',
        'objeto_resumido', 'modalidade_leilao', 'valor_estimado',
        'quantidade_itens', 'nome_leiloeiro', 'arquivo_origem'
    ]

    campos_preenchidos = 0
    campos_validos = 0
    problemas = []

    for campo in campos_obrigatorios:
        valor = registro.get(campo, '')

        # Verificar preenchimento
        if valor and valor != 'N/D' and str(valor).strip():
            campos_preenchidos += 1

            # Validações específicas
            if campo == 'link_pncp':
                if '/editais/' in valor and valor.count('/') >= 5:
                    # Verificar formato: /CNPJ/ANO/SEQUENCIAL
                    partes = valor.split('/editais/')[1].split('/')
                    if len(partes) == 3:
                        campos_validos += 1
                    else:
                        problemas.append(f"link_pncp formato incorreto: {valor}")
                else:
                    problemas.append(f"link_pncp inválido: {valor}")

            elif campo == 'link_leiloeiro':
                if valor == 'PRESENCIAL' or (valor.startswith('http') and '.' in valor):
                    campos_validos += 1
                else:
                    problemas.append(f"link_leiloeiro suspeito: {valor}")

            elif campo == 'tags':
                if valor != 'veiculos_gerais' and (',' in valor or len(valor) > 3):
                    campos_validos += 1
                else:
                    problemas.append(f"tags muito genérica: {valor}")

            else:
                campos_validos += 1
        else:
            problemas.append(f"{campo}: vazio ou N/D")

    registro['_qualidade'] = {
        'preenchimento': f"{campos_preenchidos}/{len(campos_obrigatorios)}",
        'percentual': round(campos_preenchidos / len(campos_obrigatorios) * 100, 1),
        'problemas': problemas[:5]  # Limitar a 5 problemas para não poluir
    }

    return registro
