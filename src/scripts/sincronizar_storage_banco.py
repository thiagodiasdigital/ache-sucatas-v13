#!/usr/bin/env python3
"""
Sincroniza PDFs do Supabase Storage com registros no PostgreSQL.

Fluxo:
1. Lista todas as pastas no Storage (editais-pdfs)
2. Para cada pasta, baixa metadados.json
3. Busca dados completos na API PNCP
4. Insere no banco com storage_path preenchido

Uso:
    python sincronizar_storage_banco.py [--dry-run] [--limit N]

Opcoes:
    --dry-run   Mostra o que seria feito, sem inserir no banco
    --limit N   Limita a N editais (para teste)
"""

import os
import sys
import json
import argparse
import requests
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuracao
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
PNCP_API_BASE = 'https://pncp.gov.br/api/consulta/v1'
BUCKET_NAME = 'editais-pdfs'

# Validar variaveis
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY sao obrigatorios no .env")
    sys.exit(1)

# Cliente Supabase
from supabase import create_client
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
bucket = client.storage.from_(BUCKET_NAME)


def listar_editais_storage():
    """Lista todas as pastas no Storage."""
    pastas = bucket.list()
    editais = []

    for pasta in pastas:
        pncp_base = pasta['name']
        # Listar subpastas (anos)
        subpastas = bucket.list(path=pncp_base)
        for sub in subpastas:
            ano = sub['name']
            editais.append({
                'storage_path': f'{pncp_base}/{ano}',
                'cnpj': pncp_base.split('-')[0],
                'ano': ano,
                'sequencial': pncp_base.split('-')[-1],
            })

    return editais


def baixar_metadados(storage_path):
    """Baixa metadados.json de uma pasta."""
    path = f'{storage_path}/metadados.json'
    try:
        result = bucket.download(path)
        return json.loads(result)
    except Exception as e:
        print(f"  AVISO: Sem metadados.json em {storage_path}: {e}")
        return None


def buscar_dados_pncp(cnpj, ano, sequencial):
    """Busca dados completos na API PNCP."""
    url = f'{PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{sequencial}'
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  AVISO: API PNCP retornou {resp.status_code} para {cnpj}/{ano}/{sequencial}")
            return None
    except Exception as e:
        print(f"  ERRO: Falha ao buscar API PNCP: {e}")
        return None


def listar_arquivos_storage(storage_path):
    """Lista arquivos PDF na pasta do Storage."""
    try:
        arquivos = bucket.list(path=storage_path)
        pdfs = [a['name'] for a in arquivos if a['name'].endswith('.pdf')]
        return pdfs
    except Exception as e:
        print(f"  AVISO: Erro ao listar arquivos em {storage_path}: {e}")
        return []


def verificar_existe_banco(pncp_id):
    """Verifica se o edital ja existe no banco."""
    try:
        resp = client.table('editais_leilao').select('id').eq('pncp_id', pncp_id).execute()
        return len(resp.data) > 0
    except Exception as e:
        print(f"  ERRO: Falha ao verificar banco: {e}")
        return False


def corrigir_encoding(texto):
    """Corrige problemas de encoding."""
    if not texto:
        return texto
    # Corrigir mojibake comum
    replacements = {
        'Ã£': 'ã', 'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
        'Ã§': 'ç', 'Ã': 'Á', 'Ã‰': 'É', 'Ã"': 'Ó', 'Ãœ': 'Ü',
        'Â°': '°', 'Âº': 'º', 'Âª': 'ª',
        '\x00': '', '\ufffd': '',
    }
    for old, new in replacements.items():
        texto = texto.replace(old, new)
    return texto


def inserir_edital(dados):
    """Insere edital no banco."""
    try:
        resp = client.table('editais_leilao').insert(dados).execute()
        return resp.data[0]['id'] if resp.data else None
    except Exception as e:
        print(f"  ERRO: Falha ao inserir: {e}")
        return None


def montar_registro(storage_info, metadados, pncp_data):
    """Monta registro para inserir no banco."""

    # Prioridade: API PNCP > metadados.json
    orgao = pncp_data.get('orgaoEntidade', {}) if pncp_data else {}
    unidade = pncp_data.get('unidadeOrgao', {}) if pncp_data else {}

    # PNCP ID no formato esperado
    pncp_id = pncp_data.get('numeroControlePNCP', '').replace('/', '-') if pncp_data else None
    if not pncp_id and metadados:
        pncp_id = metadados.get('pncp_id', '').replace('/', '-')
    if not pncp_id:
        pncp_id = f"{storage_info['cnpj']}-1-{storage_info['sequencial']}-{storage_info['ano']}"

    # UF com fallback
    uf = unidade.get('ufSigla', '')
    if not uf and metadados:
        uf = metadados.get('uf', '')
    if not uf or len(uf) != 2:
        uf = 'XX'

    # Municipio
    municipio = corrigir_encoding(unidade.get('municipioNome', ''))
    if not municipio and metadados:
        municipio = corrigir_encoding(metadados.get('municipio', ''))

    # Titulo/Objeto
    titulo = corrigir_encoding(pncp_data.get('objetoCompra', '')) if pncp_data else ''
    if not titulo and metadados:
        titulo = corrigir_encoding(metadados.get('titulo', '') or metadados.get('objeto', ''))

    # Valor estimado
    valor = pncp_data.get('valorTotalEstimado') if pncp_data else None

    # Data publicacao
    data_pub = None
    if pncp_data and pncp_data.get('dataPublicacaoPncp'):
        data_pub = pncp_data['dataPublicacaoPncp'][:10]  # YYYY-MM-DD

    # Data do leilao (abertura da proposta)
    data_leilao = None
    if pncp_data and pncp_data.get('dataAberturaProposta'):
        data_leilao = pncp_data['dataAberturaProposta']

    # Link PNCP
    link_pncp = f"https://pncp.gov.br/app/editais/{pncp_id.replace('-', '/')}"

    # Score
    score = metadados.get('score', 50) if metadados else 50

    # Modalidade
    modalidade = pncp_data.get('modalidadeNome', 'Leilão') if pncp_data else 'Leilão'

    # Gerar id_interno unico
    id_interno = f"ID_{uuid.uuid4().hex[:12].upper()}"

    # Numero do edital
    n_compra = pncp_data.get('numeroCompra', '') if pncp_data else ''
    n_edital = n_compra or f"{storage_info['sequencial']}/{storage_info['ano']}"
    n_pncp = n_edital

    # Descricao/objeto resumido
    descricao = corrigir_encoding(titulo[:200]) if titulo else 'Leilão público'

    return {
        'id_interno': id_interno,
        'pncp_id': pncp_id,
        'n_edital': n_edital,
        'n_pncp': n_pncp,
        'titulo': titulo or f"Leilão {pncp_id}",
        'orgao': corrigir_encoding(orgao.get('razaoSocial', '')) or (metadados.get('orgao_nome', '') if metadados else ''),
        'uf': uf.upper(),
        'cidade': municipio,
        'data_publicacao': data_pub,
        'data_leilao': data_leilao,
        'valor_estimado': valor,
        'link_pncp': link_pncp,
        'modalidade_leilao': modalidade,
        'nome_leiloeiro': 'N/D',
        'descricao': descricao,
        'objeto_resumido': descricao,
        'tags': ['leilao', 'sync'],
        'score': score,
        'storage_path': storage_info['storage_path'],
        'processado_auditor': False,
        'versao_auditor': 'SYNC_V1',
    }


def main():
    parser = argparse.ArgumentParser(description='Sincroniza Storage com Banco')
    parser.add_argument('--dry-run', action='store_true', help='Mostra sem inserir')
    parser.add_argument('--limit', type=int, default=0, help='Limita a N editais')
    args = parser.parse_args()

    print("=" * 60)
    print("SINCRONIZACAO STORAGE -> BANCO")
    print("=" * 60)
    print(f"Dry-run: {args.dry_run}")
    print(f"Limite: {args.limit or 'Sem limite'}")
    print()

    # 1. Listar editais no Storage
    print("[1/4] Listando editais no Storage...")
    editais_storage = listar_editais_storage()
    print(f"      Encontrados: {len(editais_storage)}")

    if args.limit:
        editais_storage = editais_storage[:args.limit]
        print(f"      Limitado a: {len(editais_storage)}")

    # Estatisticas
    inseridos = 0
    ignorados = 0
    erros = 0

    # 2. Processar cada edital
    print(f"\n[2/4] Processando {len(editais_storage)} editais...")

    for i, storage_info in enumerate(editais_storage, 1):
        storage_path = storage_info['storage_path']
        print(f"\n[{i}/{len(editais_storage)}] {storage_path}")

        # Baixar metadados
        metadados = baixar_metadados(storage_path)

        # Buscar dados na API PNCP
        pncp_data = buscar_dados_pncp(
            storage_info['cnpj'],
            storage_info['ano'],
            storage_info['sequencial']
        )

        # Montar registro
        registro = montar_registro(storage_info, metadados, pncp_data)

        # Verificar se ja existe
        if verificar_existe_banco(registro['pncp_id']):
            print(f"  IGNORADO: {registro['pncp_id']} ja existe no banco")
            ignorados += 1
            continue

        # Inserir ou mostrar
        if args.dry_run:
            print(f"  [DRY-RUN] Seria inserido:")
            print(f"    pncp_id: {registro['pncp_id']}")
            print(f"    orgao: {registro['orgao'][:50]}...")
            print(f"    uf: {registro['uf']}")
            print(f"    valor: R$ {registro['valor_estimado']}")
            print(f"    storage_path: {registro['storage_path']}")
            inseridos += 1
        else:
            id_inserido = inserir_edital(registro)
            if id_inserido:
                print(f"  INSERIDO: ID {id_inserido}")
                inseridos += 1
            else:
                print(f"  ERRO ao inserir")
                erros += 1

    # 3. Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Total no Storage: {len(editais_storage)}")
    print(f"Inseridos: {inseridos}")
    print(f"Ignorados (ja existiam): {ignorados}")
    print(f"Erros: {erros}")

    if args.dry_run:
        print("\n[DRY-RUN] Nenhum dado foi inserido. Execute sem --dry-run para inserir.")


if __name__ == '__main__':
    main()
