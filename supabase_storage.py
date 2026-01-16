#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase Storage Repository - ACHE SUCATAS DaaS V11
Gerencia upload/download de PDFs e arquivos no Supabase Storage.

Estrutura no Storage:
  editais-pdfs/
  ├── {pncp_id}/
  │   ├── metadados.json
  │   ├── edital_{hash}.pdf
  │   └── anexo_{hash}.xlsx
  └── ...
"""

import os
import json
import logging
import hashlib
from io import BytesIO
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("SupabaseStorage")


class SupabaseStorageRepository:
    """Gerencia arquivos no Supabase Storage."""

    def __init__(self, bucket_name: str = "editais-pdfs"):
        """
        Inicializa repositório de storage.

        Args:
            bucket_name: Nome do bucket no Supabase Storage
        """
        self.bucket_name = bucket_name
        self.client = None
        self.storage = None
        self.enable_storage = os.getenv("ENABLE_SUPABASE_STORAGE", "true").lower() == "true"

        if not self.enable_storage:
            logger.info("Supabase Storage DESABILITADO")
            return

        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("Credenciais Supabase não encontradas no .env")
            logger.warning("Storage continuando em modo LOCAL ONLY")
            self.enable_storage = False
            return

        try:
            from supabase import create_client, Client
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self.storage = self.client.storage
            logger.info(f"Supabase Storage conectado: bucket={bucket_name}")
        except ImportError:
            logger.error("Biblioteca supabase não instalada")
            self.enable_storage = False
        except Exception as e:
            logger.error(f"Erro ao conectar Supabase Storage: {e}")
            self.enable_storage = False

    # =========================================================================
    # UPLOAD METHODS
    # =========================================================================

    def upload_file(
        self,
        path: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = True
    ) -> Optional[str]:
        """
        Upload de arquivo genérico para o Storage.

        Args:
            path: Caminho no bucket (ex: "pncp_id/arquivo.pdf")
            file_data: Conteúdo do arquivo em bytes
            content_type: MIME type do arquivo
            upsert: Se True, sobrescreve arquivo existente

        Returns:
            URL pública do arquivo ou None se erro
        """
        if not self.enable_storage:
            logger.debug("Storage desabilitado - skip upload")
            return None

        try:
            # Supabase Storage API
            response = self.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_data,
                file_options={
                    "content-type": content_type,
                    "upsert": str(upsert).lower()
                }
            )

            logger.info(f"Upload OK: {path} ({len(file_data)} bytes)")
            return self.get_public_url(path)

        except Exception as e:
            error_msg = str(e)

            # Se arquivo já existe e upsert=False
            if "already exists" in error_msg.lower() and not upsert:
                logger.debug(f"Arquivo já existe: {path}")
                return self.get_public_url(path)

            # Se o erro é de bucket não encontrado
            if "bucket" in error_msg.lower() and "not found" in error_msg.lower():
                logger.error(f"Bucket '{self.bucket_name}' não encontrado. Crie no Dashboard Supabase.")
                return None

            logger.error(f"Erro ao fazer upload de {path}: {e}")
            return None

    def upload_pdf(
        self,
        pncp_id: str,
        filename: str,
        pdf_bytes: bytes
    ) -> Optional[str]:
        """
        Upload de PDF para pasta do edital.

        Args:
            pncp_id: Identificador PNCP do edital
            filename: Nome original do arquivo
            pdf_bytes: Conteúdo do PDF

        Returns:
            URL pública do PDF ou None se erro
        """
        # Gerar hash único para o arquivo
        file_hash = hashlib.md5(pdf_bytes).hexdigest()[:8]

        # Sanitizar filename
        safe_filename = self._sanitize_filename(filename)
        if not safe_filename.endswith('.pdf'):
            safe_filename = f"{safe_filename}.pdf"

        # Caminho: pncp_id/hash_filename.pdf
        path = f"{pncp_id}/{file_hash}_{safe_filename}"

        return self.upload_file(path, pdf_bytes, "application/pdf")

    def upload_json(
        self,
        pncp_id: str,
        data: dict,
        filename: str = "metadados.json"
    ) -> Optional[str]:
        """
        Upload de metadados JSON para pasta do edital.

        Args:
            pncp_id: Identificador PNCP do edital
            data: Dicionário com metadados
            filename: Nome do arquivo JSON

        Returns:
            URL pública do JSON ou None se erro
        """
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        path = f"{pncp_id}/{filename}"
        return self.upload_file(path, json_bytes, "application/json")

    def upload_attachment(
        self,
        pncp_id: str,
        filename: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """
        Upload de anexo (Excel, DOCX, etc.) para pasta do edital.

        Args:
            pncp_id: Identificador PNCP do edital
            filename: Nome original do arquivo
            file_bytes: Conteúdo do arquivo
            content_type: MIME type

        Returns:
            URL pública do arquivo ou None se erro
        """
        file_hash = hashlib.md5(file_bytes).hexdigest()[:8]
        safe_filename = self._sanitize_filename(filename)
        path = f"{pncp_id}/{file_hash}_{safe_filename}"
        return self.upload_file(path, file_bytes, content_type)

    # =========================================================================
    # DOWNLOAD METHODS
    # =========================================================================

    def download_file(self, path: str) -> Optional[bytes]:
        """
        Download de arquivo do Storage.

        Args:
            path: Caminho no bucket

        Returns:
            Conteúdo do arquivo em bytes ou None se erro
        """
        if not self.enable_storage:
            logger.debug("Storage desabilitado - skip download")
            return None

        try:
            response = self.storage.from_(self.bucket_name).download(path)
            logger.debug(f"Download OK: {path} ({len(response)} bytes)")
            return response

        except Exception as e:
            logger.error(f"Erro ao baixar {path}: {e}")
            return None

    def download_pdf(self, path: str) -> Optional[BytesIO]:
        """
        Download de PDF como BytesIO (compatível com pdfplumber).

        Args:
            path: Caminho do PDF no bucket

        Returns:
            BytesIO com conteúdo do PDF ou None se erro
        """
        data = self.download_file(path)
        if data:
            return BytesIO(data)
        return None

    def download_json(self, path: str) -> Optional[dict]:
        """
        Download e parse de arquivo JSON.

        Args:
            path: Caminho do JSON no bucket

        Returns:
            Dicionário com dados ou None se erro
        """
        data = self.download_file(path)
        if data:
            try:
                return json.loads(data.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao parsear JSON {path}: {e}")
                return None
        return None

    def download_metadados(self, pncp_id: str) -> Optional[dict]:
        """
        Download dos metadados de um edital.

        Args:
            pncp_id: Identificador PNCP

        Returns:
            Dicionário com metadados ou None
        """
        path = f"{pncp_id}/metadados.json"
        return self.download_json(path)

    # =========================================================================
    # LISTAGEM METHODS
    # =========================================================================

    def listar_editais(self) -> List[str]:
        """
        Lista todos os pncp_ids no bucket.

        Returns:
            Lista de pncp_ids (pastas no bucket)
        """
        if not self.enable_storage:
            return []

        try:
            response = self.storage.from_(self.bucket_name).list()

            # Filtra apenas pastas (diretórios)
            editais = [
                item["name"]
                for item in response
                if item.get("id") is None  # Pastas não têm ID
            ]

            logger.info(f"Encontrados {len(editais)} editais no Storage")
            return editais

        except Exception as e:
            logger.error(f"Erro ao listar editais: {e}")
            return []

    def listar_arquivos(self, pncp_id: str) -> List[dict]:
        """
        Lista arquivos de um edital específico.

        Args:
            pncp_id: Identificador PNCP

        Returns:
            Lista de dicts com info dos arquivos
        """
        if not self.enable_storage:
            return []

        try:
            response = self.storage.from_(self.bucket_name).list(path=pncp_id)

            arquivos = []
            for item in response:
                if item.get("id"):  # Apenas arquivos (têm ID)
                    arquivos.append({
                        "name": item["name"],
                        "path": f"{pncp_id}/{item['name']}",
                        "size": item.get("metadata", {}).get("size", 0),
                        "content_type": item.get("metadata", {}).get("mimetype", ""),
                        "created_at": item.get("created_at"),
                    })

            return arquivos

        except Exception as e:
            logger.error(f"Erro ao listar arquivos de {pncp_id}: {e}")
            return []

    def listar_pdfs(self, pncp_id: str) -> List[dict]:
        """
        Lista apenas PDFs de um edital.

        Args:
            pncp_id: Identificador PNCP

        Returns:
            Lista de dicts com info dos PDFs
        """
        arquivos = self.listar_arquivos(pncp_id)
        return [
            f for f in arquivos
            if f["name"].lower().endswith(".pdf")
        ]

    def arquivo_existe(self, path: str) -> bool:
        """
        Verifica se arquivo existe no Storage.

        Args:
            path: Caminho completo no bucket

        Returns:
            True se existe, False caso contrário
        """
        if not self.enable_storage:
            return False

        try:
            # Tenta listar o arquivo específico
            parts = path.rsplit("/", 1)
            if len(parts) == 2:
                folder, filename = parts
                files = self.storage.from_(self.bucket_name).list(path=folder)
                return any(f["name"] == filename for f in files if f.get("id"))
            return False

        except Exception:
            return False

    def edital_existe(self, pncp_id: str) -> bool:
        """
        Verifica se edital (pasta) existe no Storage.

        Args:
            pncp_id: Identificador PNCP

        Returns:
            True se existe, False caso contrário
        """
        arquivos = self.listar_arquivos(pncp_id)
        return len(arquivos) > 0

    # =========================================================================
    # URL METHODS
    # =========================================================================

    def get_public_url(self, path: str) -> str:
        """
        Obtém URL pública de um arquivo.

        Args:
            path: Caminho no bucket

        Returns:
            URL pública do arquivo
        """
        if not self.enable_storage or not self.client:
            return ""

        try:
            response = self.storage.from_(self.bucket_name).get_public_url(path)
            return response
        except Exception as e:
            logger.error(f"Erro ao obter URL pública de {path}: {e}")
            return ""

    def get_signed_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Gera URL assinada com tempo de expiração.

        Args:
            path: Caminho no bucket
            expires_in: Tempo de expiração em segundos (padrão: 1h)

        Returns:
            URL assinada ou None se erro
        """
        if not self.enable_storage:
            return None

        try:
            response = self.storage.from_(self.bucket_name).create_signed_url(
                path, expires_in
            )
            return response.get("signedURL")
        except Exception as e:
            logger.error(f"Erro ao gerar URL assinada para {path}: {e}")
            return None

    # =========================================================================
    # DELETE METHODS
    # =========================================================================

    def delete_file(self, path: str) -> bool:
        """
        Deleta um arquivo do Storage.

        Args:
            path: Caminho no bucket

        Returns:
            True se sucesso, False se erro
        """
        if not self.enable_storage:
            return False

        try:
            self.storage.from_(self.bucket_name).remove([path])
            logger.info(f"Arquivo deletado: {path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar {path}: {e}")
            return False

    def delete_edital(self, pncp_id: str) -> bool:
        """
        Deleta todos os arquivos de um edital.

        Args:
            pncp_id: Identificador PNCP

        Returns:
            True se sucesso, False se erro
        """
        if not self.enable_storage:
            return False

        try:
            arquivos = self.listar_arquivos(pncp_id)
            paths = [f["path"] for f in arquivos]

            if paths:
                self.storage.from_(self.bucket_name).remove(paths)
                logger.info(f"Edital {pncp_id} deletado ({len(paths)} arquivos)")

            return True
        except Exception as e:
            logger.error(f"Erro ao deletar edital {pncp_id}: {e}")
            return False

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza nome de arquivo para compatibilidade.

        Args:
            filename: Nome original

        Returns:
            Nome sanitizado
        """
        import unicodedata
        import re

        # Normaliza unicode
        filename = unicodedata.normalize('NFKD', filename)
        filename = filename.encode('ascii', 'ignore').decode('ascii')

        # Remove caracteres especiais
        filename = re.sub(r'[^\w\s.-]', '', filename)
        filename = re.sub(r'[-\s]+', '_', filename)

        return filename[:100]  # Limita tamanho

    def get_storage_stats(self) -> dict:
        """
        Obtém estatísticas do storage.

        Returns:
            Dict com estatísticas
        """
        if not self.enable_storage:
            return {"enabled": False}

        try:
            editais = self.listar_editais()

            total_arquivos = 0
            total_bytes = 0

            for pncp_id in editais[:100]:  # Limita para performance
                arquivos = self.listar_arquivos(pncp_id)
                total_arquivos += len(arquivos)
                total_bytes += sum(f.get("size", 0) for f in arquivos)

            return {
                "enabled": True,
                "bucket": self.bucket_name,
                "total_editais": len(editais),
                "total_arquivos_sample": total_arquivos,
                "total_bytes_sample": total_bytes,
                "sample_size": min(100, len(editais)),
            }

        except Exception as e:
            return {
                "enabled": True,
                "bucket": self.bucket_name,
                "error": str(e)
            }


# =========================================================================
# TESTE BÁSICO
# =========================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TESTE SUPABASE STORAGE REPOSITORY")
    print("=" * 60)

    storage = SupabaseStorageRepository()

    if storage.enable_storage:
        print("\n[OK] Supabase Storage conectado")

        # Teste de stats
        stats = storage.get_storage_stats()
        print(f"[INFO] Stats: {stats}")

        # Teste de upload (opcional)
        # url = storage.upload_file("teste/hello.txt", b"Hello World", "text/plain")
        # print(f"[INFO] Upload teste: {url}")

    else:
        print("\n[AVISO] Supabase Storage desabilitado")
