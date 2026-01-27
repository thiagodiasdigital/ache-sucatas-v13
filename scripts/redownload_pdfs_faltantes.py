#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REDOWNLOAD DE PDFs FALTANTES

Objetivo: Re-baixar PDFs do PNCP que estao registrados no banco mas
          nao existem no Supabase Storage.

Fluxo:
    1. Busca editais sem link_leiloeiro que sao eletronicos
    2. Verifica se PDF existe no Storage
    3. Se nao existe, baixa da API do PNCP
    4. Faz upload para o Storage
    5. (Opcional) Re-executa extracao de link

Uso:
    # Modo dry-run (apenas lista o que faria)
    python scripts/redownload_pdfs_faltantes.py --dry-run

    # Executar de verdade
    python scripts/redownload_pdfs_faltantes.py

    # Apenas editais especificos
    python scripts/redownload_pdfs_faltantes.py --pncp-ids "21250048000128-1-000004/2026,81531162000158-1-000288-2025"

Autor: Claude Code
Data: 2026-01-27
"""

import os
import sys
import re
import time
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RedownloadPDFs")


class PNCPClient:
    """Cliente para API do PNCP."""

    BASE_URL = "https://pncp.gov.br/api"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AcheSucatas/1.0 (Minerador de Leiloes)",
            "Accept": "application/json",
        })

    def obter_arquivos(self, pncp_id: str) -> List[dict]:
        """
        Obtem lista de arquivos de um edital.

        Args:
            pncp_id: Ex: "21250048000128-1-000004/2026" ou "21250048000128-1-000004-2026"

        Returns:
            Lista de dicts com info dos arquivos
        """
        # Normalizar pncp_id
        pncp_id_norm = pncp_id.replace("/", "-")
        parts = pncp_id_norm.split("-")

        if len(parts) < 4:
            logger.error(f"PNCP ID invalido: {pncp_id}")
            return []

        cnpj = parts[0]
        # esfera = parts[1]  # nao usado na URL
        sequencial = parts[2]
        ano = parts[3]

        url = f"{self.BASE_URL}/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"

        try:
            logger.debug(f"GET {url}")
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"  Encontrados {len(data)} arquivos")
                    return data
                return []
            else:
                logger.warning(f"  API retornou {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"  Erro ao obter arquivos: {e}")
            return []

    def baixar_arquivo(self, url: str) -> Optional[bytes]:
        """Baixa um arquivo pelo URL."""
        try:
            logger.debug(f"Baixando: {url[:80]}...")
            response = self.session.get(url, timeout=60)

            if response.status_code == 200:
                logger.info(f"  Baixado: {len(response.content)} bytes")
                return response.content
            else:
                logger.warning(f"  Erro ao baixar: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"  Erro ao baixar: {e}")
            return None


class SupabaseManager:
    """Gerenciador do Supabase (banco + storage)."""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_KEY necessarios")

        from supabase import create_client
        self.client = create_client(self.url, self.key)
        logger.info(f"Conectado ao Supabase")

    def buscar_editais_sem_pdf(self, modalidades: List[str] = None) -> List[dict]:
        """
        Busca editais que:
        - Nao tem link_leiloeiro (NULL)
        - Sao eletronicos (ou modalidades especificadas)
        """
        query = self.client.table("editais_leilao")\
            .select("id, pncp_id, orgao, cidade, uf, modalidade_leilao, storage_path, link_pncp")\
            .is_("link_leiloeiro", "null")

        if modalidades:
            query = query.in_("modalidade_leilao", modalidades)

        result = query.execute()
        return result.data or []

    def verificar_arquivo_existe(self, storage_path: str) -> bool:
        """Verifica se arquivo existe no bucket."""
        if not storage_path:
            return False

        try:
            # Tentar listar a pasta
            folder = storage_path.rsplit("/", 1)[0] if "/" in storage_path else storage_path
            files = self.client.storage.from_("editais-pdfs").list(folder)

            # Verificar se o arquivo especifico existe
            filename = storage_path.rsplit("/", 1)[-1] if "/" in storage_path else storage_path
            for f in files:
                if f.get("name") == filename:
                    return True
            return False

        except Exception as e:
            logger.debug(f"Erro ao verificar arquivo: {e}")
            return False

    def upload_arquivo(self, storage_path: str, data: bytes, content_type: str = "application/pdf") -> bool:
        """Faz upload de arquivo para o Storage."""
        try:
            # Criar pasta se necessario (Supabase cria automaticamente)
            result = self.client.storage.from_("editais-pdfs").upload(
                path=storage_path,
                file=data,
                file_options={"content-type": content_type}
            )
            logger.info(f"  Upload OK: {storage_path}")
            return True

        except Exception as e:
            # Se ja existe, tentar atualizar
            if "Duplicate" in str(e) or "already exists" in str(e).lower():
                try:
                    self.client.storage.from_("editais-pdfs").update(
                        path=storage_path,
                        file=data,
                        file_options={"content-type": content_type}
                    )
                    logger.info(f"  Update OK: {storage_path}")
                    return True
                except Exception as e2:
                    logger.error(f"  Erro no update: {e2}")
                    return False
            else:
                logger.error(f"  Erro no upload: {e}")
                return False

    def atualizar_storage_path(self, pncp_id: str, storage_path: str) -> bool:
        """Atualiza o storage_path no banco."""
        try:
            self.client.table("editais_leilao")\
                .update({"storage_path": storage_path, "updated_at": datetime.utcnow().isoformat()})\
                .eq("pncp_id", pncp_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar banco: {e}")
            return False


def limpar_nome_arquivo(nome: str) -> str:
    """Limpa nome de arquivo removendo caracteres problematicos."""
    # Substituir caracteres invalidos
    nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
    # Remover espacos extras
    nome = re.sub(r'\s+', '_', nome)
    # Limitar tamanho
    if len(nome) > 100:
        nome = nome[:100]
    return nome


def processar_edital(
    pncp_client: PNCPClient,
    supabase: SupabaseManager,
    edital: dict,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Processa um edital: baixa PDF e faz upload.

    Returns:
        (sucesso, mensagem)
    """
    pncp_id = edital.get("pncp_id")
    storage_path_atual = edital.get("storage_path")

    logger.info(f"Processando: {pncp_id}")
    logger.info(f"  Orgao: {edital.get('orgao', 'N/A')[:50]}")
    logger.info(f"  Cidade/UF: {edital.get('cidade')}/{edital.get('uf')}")

    # 1. Verificar se ja existe no storage
    if storage_path_atual and supabase.verificar_arquivo_existe(storage_path_atual):
        return (True, "PDF ja existe no Storage")

    # 2. Obter lista de arquivos da API PNCP
    arquivos = pncp_client.obter_arquivos(pncp_id)

    if not arquivos:
        return (False, "Nenhum arquivo encontrado na API PNCP")

    # 3. Filtrar PDFs
    pdfs = [a for a in arquivos if a.get("url", "").lower().endswith(".pdf")]

    if not pdfs:
        # Tentar qualquer arquivo
        pdfs = arquivos

    if not pdfs:
        return (False, "Nenhum PDF encontrado")

    # 4. Escolher o melhor PDF (preferir edital/termo de referencia)
    pdf_escolhido = None
    for pdf in pdfs:
        titulo = (pdf.get("titulo") or pdf.get("descricao") or "").lower()
        if any(termo in titulo for termo in ["edital", "termo", "leilao", "leilão"]):
            pdf_escolhido = pdf
            break

    if not pdf_escolhido:
        pdf_escolhido = pdfs[0]

    url = pdf_escolhido.get("url")
    titulo = pdf_escolhido.get("titulo") or pdf_escolhido.get("descricao") or "documento"

    logger.info(f"  PDF selecionado: {titulo[:50]}")
    logger.info(f"  URL: {url[:80]}...")

    if dry_run:
        return (True, f"[DRY-RUN] Baixaria: {titulo}")

    # 5. Baixar o arquivo
    data = pncp_client.baixar_arquivo(url)

    if not data:
        return (False, "Falha ao baixar PDF")

    # 6. Definir storage_path
    pncp_id_norm = pncp_id.replace("/", "-")
    nome_arquivo = limpar_nome_arquivo(titulo)
    if not nome_arquivo.lower().endswith(".pdf"):
        nome_arquivo += ".pdf"

    novo_storage_path = f"{pncp_id_norm}/{nome_arquivo}"

    # 7. Upload para o Storage
    sucesso = supabase.upload_arquivo(novo_storage_path, data)

    if not sucesso:
        return (False, "Falha no upload para Storage")

    # 8. Atualizar banco se storage_path mudou
    if novo_storage_path != storage_path_atual:
        supabase.atualizar_storage_path(pncp_id, novo_storage_path)
        logger.info(f"  Storage path atualizado: {novo_storage_path}")

    return (True, f"PDF baixado e uploaded: {novo_storage_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Re-download de PDFs faltantes do PNCP para o Supabase Storage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra o que seria feito, sem executar"
    )
    parser.add_argument(
        "--pncp-ids",
        type=str,
        help="Lista de PNCP IDs separados por virgula (opcional)"
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Processar todos os editais sem link (nao apenas eletronicos)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("REDOWNLOAD DE PDFs FALTANTES")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modo: {'DRY-RUN' if args.dry_run else 'EXECUCAO REAL'}")
    print("=" * 70)

    # Inicializar clientes
    pncp_client = PNCPClient()
    supabase = SupabaseManager()

    # Buscar editais para processar
    if args.pncp_ids:
        # Processar apenas os IDs especificados
        pncp_ids = [p.strip() for p in args.pncp_ids.split(",")]
        editais = []
        for pncp_id in pncp_ids:
            result = supabase.client.table("editais_leilao")\
                .select("id, pncp_id, orgao, cidade, uf, modalidade_leilao, storage_path, link_pncp")\
                .eq("pncp_id", pncp_id)\
                .execute()
            if result.data:
                editais.extend(result.data)
        logger.info(f"Editais especificados: {len(editais)}")
    else:
        # Buscar automaticamente
        if args.todos:
            modalidades = None
            logger.info("Buscando TODOS os editais sem link...")
        else:
            modalidades = ["Eletronico", "Eletrônico", "Leilao - Eletronico", "Leilão - Eletrônico"]
            logger.info("Buscando editais ELETRONICOS sem link...")

        editais = supabase.buscar_editais_sem_pdf(modalidades)

    logger.info(f"Total de editais a processar: {len(editais)}")

    if not editais:
        logger.info("Nenhum edital para processar")
        return

    # Processar cada edital
    resultados = {
        "sucesso": 0,
        "falha": 0,
        "ja_existe": 0,
        "detalhes": []
    }

    for i, edital in enumerate(editais, 1):
        print()
        logger.info(f"[{i}/{len(editais)}] {'-' * 50}")

        sucesso, mensagem = processar_edital(
            pncp_client,
            supabase,
            edital,
            dry_run=args.dry_run
        )

        if sucesso:
            if "ja existe" in mensagem.lower():
                resultados["ja_existe"] += 1
            else:
                resultados["sucesso"] += 1
        else:
            resultados["falha"] += 1

        resultados["detalhes"].append({
            "pncp_id": edital.get("pncp_id"),
            "sucesso": sucesso,
            "mensagem": mensagem
        })

        logger.info(f"  Resultado: {mensagem}")

        # Rate limiting
        if not args.dry_run and i < len(editais):
            time.sleep(1)

    # Resumo final
    print()
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"  Total processados: {len(editais)}")
    print(f"  Sucesso (novos):   {resultados['sucesso']}")
    print(f"  Ja existiam:       {resultados['ja_existe']}")
    print(f"  Falhas:            {resultados['falha']}")

    if resultados["falha"] > 0:
        print()
        print("Editais com falha:")
        for d in resultados["detalhes"]:
            if not d["sucesso"]:
                print(f"  - {d['pncp_id']}: {d['mensagem']}")

    print()
    if args.dry_run:
        print("[DRY-RUN] Nenhuma alteracao foi feita")
    else:
        print("Processamento concluido!")


if __name__ == "__main__":
    main()
