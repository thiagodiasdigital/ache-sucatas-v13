#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
EXTRAIR LOTES DE EDITAIS FUTUROS
=============================================================================
Script para extrair lotes apenas dos editais com data_leilao futura.

Uso:
    python scripts/extrair_lotes_futuros.py [--dry-run] [--limite N]

Opções:
    --dry-run   Apenas mostra o que seria feito, sem extrair
    --limite N  Limita a N editais (padrão: 50)
=============================================================================
"""

import argparse
import hashlib
import logging
import os
import sys
import tempfile
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv()

from supabase import create_client

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExtratorLotesFuturos:
    """Extrai lotes de editais com data futura."""

    def __init__(self, dry_run: bool = False):
        """
        Args:
            dry_run: Se True, apenas mostra o que seria feito
        """
        self.dry_run = dry_run

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios")

        self.client = create_client(url, key)
        logger.info(f"Conectado ao Supabase (dry_run={dry_run})")

    def buscar_editais_futuros_sem_lotes(self, limite: int = 50) -> List[Dict]:
        """
        Busca editais futuros que ainda não têm lotes extraídos.

        Returns:
            Lista de editais com storage_path (PDF disponível)
        """
        logger.info("Buscando editais futuros sem lotes...")

        # Buscar todos os editais futuros
        hoje = datetime.now().isoformat()

        # Primeiro, pegar editais futuros com storage_path
        res = self.client.table("editais_leilao").select(
            "id, id_interno, titulo, data_leilao, storage_path"
        ).gte(
            "data_leilao", hoje
        ).not_.is_(
            "storage_path", "null"
        ).order(
            "data_leilao"
        ).limit(limite * 2).execute()  # Pegar mais para compensar os que já têm lotes

        editais = res.data or []
        logger.info(f"  Editais futuros com PDF: {len(editais)}")

        # Filtrar os que já têm lotes
        editais_sem_lotes = []
        for edital in editais:
            # Verificar se já tem lotes
            res_lotes = self.client.table("lotes_leilao").select(
                "id", count="exact"
            ).eq("edital_id", edital["id"]).limit(1).execute()

            if res_lotes.count == 0:
                editais_sem_lotes.append(edital)

            if len(editais_sem_lotes) >= limite:
                break

        logger.info(f"  Editais sem lotes: {len(editais_sem_lotes)}")
        return editais_sem_lotes

    def baixar_pdf_storage(self, storage_path: str) -> Optional[bytes]:
        """
        Baixa PDF do Supabase Storage.

        Args:
            storage_path: Caminho no storage (ex: "46634507000106-1-000001-2026/compra.pdf")

        Returns:
            Bytes do PDF ou None se falhar
        """
        # Bucket fixo definido no projeto
        BUCKET = "editais-pdfs"

        try:
            # storage_path já é o caminho completo dentro do bucket
            res = self.client.storage.from_(BUCKET).download(storage_path)
            return res

        except Exception as e:
            logger.error(f"Erro ao baixar PDF: {e}")
            return None

    def extrair_lotes_do_pdf(
        self,
        pdf_bytes: bytes,
        edital_id: int,
        arquivo_nome: str
    ) -> Dict[str, Any]:
        """
        Extrai lotes de um PDF.

        Returns:
            Dict com resultado da extração
        """
        from src.extractors.lotes_integration import criar_integrador_lotes

        integrador = criar_integrador_lotes(self.client)

        resultado = integrador.processar_pdf_completo(
            pdf_bytesio=BytesIO(pdf_bytes),
            edital_id=edital_id,
            arquivo_nome=arquivo_nome,
            salvar_banco=not self.dry_run,
        )

        return resultado

    def executar(self, limite: int = 50) -> Dict[str, Any]:
        """
        Executa extração de lotes dos editais futuros.

        Args:
            limite: Número máximo de editais a processar

        Returns:
            Dict com estatísticas da execução
        """
        stats = {
            "total_editais": 0,
            "processados": 0,
            "com_lotes": 0,
            "sem_lotes": 0,
            "erros": 0,
            "total_lotes_extraidos": 0,
            "detalhes": [],
        }

        # Buscar editais
        editais = self.buscar_editais_futuros_sem_lotes(limite)
        stats["total_editais"] = len(editais)

        if not editais:
            logger.info("Nenhum edital futuro sem lotes encontrado!")
            return stats

        print("\n" + "=" * 70)
        print(f"EXTRAÇÃO DE LOTES - EDITAIS FUTUROS")
        print(f"{'(DRY RUN - Nada será salvo)' if self.dry_run else ''}")
        print("=" * 70)
        print(f"Editais a processar: {len(editais)}")
        print("=" * 70 + "\n")

        for i, edital in enumerate(editais, 1):
            edital_id = edital["id"]
            titulo = edital.get("titulo", "Sem título")[:50]
            data_leilao = edital.get("data_leilao", "?")[:10]
            storage_path = edital.get("storage_path", "")

            print(f"\n[{i}/{len(editais)}] {titulo}...")
            print(f"    Data: {data_leilao} | ID: {edital_id}")

            if self.dry_run:
                print(f"    [DRY RUN] Seria processado: {storage_path}")
                stats["processados"] += 1
                continue

            # Baixar PDF
            pdf_bytes = self.baixar_pdf_storage(storage_path)
            if not pdf_bytes:
                print(f"    [ERRO] Não foi possível baixar o PDF")
                stats["erros"] += 1
                continue

            # Extrair lotes
            try:
                resultado = self.extrair_lotes_do_pdf(
                    pdf_bytes=pdf_bytes,
                    edital_id=edital_id,
                    arquivo_nome=os.path.basename(storage_path),
                )

                if resultado["sucesso"] and resultado["total_lotes"] > 0:
                    print(f"    [OK] {resultado['total_lotes']} lotes extraídos, {resultado['lotes_salvos']} salvos")
                    stats["com_lotes"] += 1
                    stats["total_lotes_extraidos"] += resultado["lotes_salvos"]
                else:
                    print(f"    [SEM LOTES] Família: {resultado.get('familia_pdf', '?')}")
                    stats["sem_lotes"] += 1

                stats["processados"] += 1
                stats["detalhes"].append({
                    "edital_id": edital_id,
                    "titulo": titulo,
                    "lotes": resultado["total_lotes"],
                    "familia": resultado.get("familia_pdf"),
                })

            except Exception as e:
                print(f"    [ERRO] {str(e)}")
                stats["erros"] += 1

        # Resumo final
        print("\n" + "=" * 70)
        print("RESUMO DA EXTRAÇÃO")
        print("=" * 70)
        print(f"Total processados: {stats['processados']}")
        print(f"Com lotes: {stats['com_lotes']}")
        print(f"Sem lotes: {stats['sem_lotes']}")
        print(f"Erros: {stats['erros']}")
        print(f"Total lotes extraídos: {stats['total_lotes_extraidos']}")
        print("=" * 70)

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Extrai lotes de editais futuros"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra o que seria feito"
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=50,
        help="Limite de editais a processar (padrão: 50)"
    )

    args = parser.parse_args()

    extrator = ExtratorLotesFuturos(dry_run=args.dry_run)
    stats = extrator.executar(limite=args.limite)

    return 0 if stats["erros"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
