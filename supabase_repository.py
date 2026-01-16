#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase Repository - Camada de persistência
ACHE SUCATAS DaaS V13
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logger = logging.getLogger("SupabaseRepository")


class SupabaseRepository:
    """Gerencia persistência no Supabase com segurança máxima."""

    def __init__(self, enable_supabase: bool = True):
        """
        Inicializa repositório Supabase.

        Args:
            enable_supabase: Se False, simula operações (modo local only)
        """
        self.enable_supabase = enable_supabase
        self.client = None

        # FREIO DE SEGURANÇA: Limite máximo de editais
        self.max_editais = int(os.getenv("MAX_EDITAIS_SUPABASE", "10000"))

        if not self.enable_supabase:
            logger.info("Supabase DESABILITADO (modo local only)")
            return

        # Validar credenciais
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("Credenciais Supabase não encontradas no .env")
            logger.warning("Continuando em modo LOCAL ONLY")
            self.enable_supabase = False
            return

        # Importar supabase
        try:
            from supabase import create_client, Client
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase conectado: %s", SUPABASE_URL)
        except ImportError:
            logger.error("Biblioteca supabase não instalada")
            logger.warning("Continuando em modo LOCAL ONLY")
            self.enable_supabase = False
        except Exception as e:
            logger.error("Erro ao conectar Supabase: %s", e)
            logger.warning("Continuando em modo LOCAL ONLY")
            self.enable_supabase = False

    def inserir_edital(self, dados: Dict) -> bool:
        """
        Insere ou atualiza edital no Supabase.

        Args:
            dados: Dicionário com dados do edital (V12 format)

        Returns:
            True se sucesso, False se erro
        """
        if not self.enable_supabase:
            logger.debug("Supabase desabilitado - skip insert")
            return False

        # FREIO DE SEGURANÇA: Verificar limite antes de inserir
        try:
            count_atual = self.contar_editais()
            if count_atual >= self.max_editais:
                logger.error(
                    "LIMITE ATINGIDO: %d/%d editais. Bloqueando insert!",
                    count_atual,
                    self.max_editais,
                )
                return False
        except Exception as e:
            logger.warning("Não foi possível verificar limite: %s", e)
            # Continuar mesmo assim (fail-open para não bloquear operação)

        try:
            # Mapear campos V12 → V13 schema
            edital_data = self._mapear_v12_para_v13(dados)

            # Tentar inserir
            response = self.client.table("editais_leilao").insert(edital_data).execute()

            logger.info("Edital inserido: %s", edital_data["id_interno"])
            return True

        except Exception as e:
            error_msg = str(e)

            # Se já existe, fazer UPDATE
            if "duplicate key" in error_msg.lower() or "unique" in error_msg.lower():
                return self._atualizar_edital(dados)

            # Erro real
            logger.error("Erro ao inserir edital %s: %s", dados.get("id_interno"), e)
            return False

    def _atualizar_edital(self, dados: Dict) -> bool:
        """
        Atualiza edital existente no Supabase.

        Args:
            dados: Dicionário com dados do edital

        Returns:
            True se sucesso, False se erro
        """
        try:
            edital_data = self._mapear_v12_para_v13(dados)
            id_interno = edital_data["id_interno"]

            # Remover campos que não devem ser atualizados
            edital_data.pop("created_at", None)
            edital_data["updated_at"] = datetime.now().isoformat()

            # Atualizar
            response = (
                self.client.table("editais_leilao")
                .update(edital_data)
                .eq("id_interno", id_interno)
                .execute()
            )

            logger.info("Edital atualizado: %s", id_interno)
            return True

        except Exception as e:
            logger.error("Erro ao atualizar edital %s: %s", dados.get("id_interno"), e)
            return False

    def _mapear_v12_para_v13(self, dados: Dict) -> Dict:
        """
        Mapeia campos do formato V12 (CSV) para V13 (Supabase schema).

        Args:
            dados: Dicionário com dados V12

        Returns:
            Dicionário com dados V13
        """
        # Extrair PNCP ID do arquivo_origem
        pncp_id = self._extrair_pncp_id(dados.get("arquivo_origem", ""))

        # Converter tags string → array
        tags_str = dados.get("tags", "")
        if isinstance(tags_str, str):
            tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        else:
            tags = []

        # Converter valor_estimado string → decimal
        valor_estimado = self._parse_valor(dados.get("valor_estimado"))

        # Converter quantidade_itens string → integer
        quantidade_itens = self._parse_int(dados.get("quantidade_itens"))

        # Converter datas
        data_publicacao = self._parse_data(dados.get("data_publicacao"))
        data_atualizacao = self._parse_data(dados.get("data_atualizacao"))
        data_leilao = self._parse_datetime(dados.get("data_leilao"))

        return {
            "id_interno": dados.get("id_interno", ""),
            "pncp_id": pncp_id,
            "orgao": dados.get("orgao", ""),
            "uf": dados.get("uf", ""),
            "cidade": dados.get("cidade", ""),
            "n_edital": dados.get("n_edital", ""),
            "n_pncp": dados.get("n_edital", ""),  # V12 usa n_edital
            "data_publicacao": data_publicacao,
            "data_atualizacao": data_atualizacao,
            "data_leilao": data_leilao,
            "titulo": dados.get("titulo", ""),
            "descricao": dados.get("descricao", ""),
            "objeto_resumido": dados.get("objeto_resumido"),
            "tags": tags,
            "link_pncp": dados.get("link_pncp", ""),
            "link_leiloeiro": dados.get("link_leiloeiro"),
            "modalidade_leilao": dados.get("modalidade_leilao"),
            "valor_estimado": valor_estimado,
            "quantidade_itens": quantidade_itens,
            "nome_leiloeiro": dados.get("nome_leiloeiro"),
            "arquivo_origem": dados.get("arquivo_origem", ""),
            "pdf_hash": None,  # TODO: calcular hash
            "versao_auditor": "V13",
        }

    def _extrair_pncp_id(self, arquivo_origem: str) -> str:
        """
        Extrai PNCP ID do caminho do arquivo.

        Exemplo: "SP_CAMPINAS/2025-11-19_S60_51885242000140-1-001095-2025"
        Retorna: "51885242000140-1-001095-2025"
        """
        import re

        match = re.search(r"(\d{14}-\d+-\d+-\d{4})", arquivo_origem)
        if match:
            return match.group(1)
        return "UNKNOWN"

    def _parse_valor(self, valor_str) -> Optional[float]:
        """Converte string de valor brasileiro para decimal."""
        if not valor_str or valor_str == "N/D":
            return None

        try:
            # Remover "R$" e espaços
            valor_str = str(valor_str).replace("R$", "").strip()
            # Remover pontos de milhar
            valor_str = valor_str.replace(".", "")
            # Trocar vírgula por ponto
            valor_str = valor_str.replace(",", ".")
            return float(valor_str)
        except:
            return None

    def _parse_int(self, valor_str) -> Optional[int]:
        """Converte string para inteiro."""
        if not valor_str or valor_str == "N/D":
            return None

        try:
            return int(str(valor_str).strip())
        except:
            return None

    def _parse_data(self, data_str) -> Optional[str]:
        """
        Converte data brasileira para formato ISO (YYYY-MM-DD).

        Entrada: "15/01/2026" ou "2026-01-15"
        Saída: "2026-01-15"
        """
        if not data_str or data_str == "N/D":
            return None

        try:
            # Se já está em formato ISO
            if "-" in data_str and len(data_str) == 10:
                return data_str

            # Formato brasileiro: DD/MM/YYYY
            parts = data_str.split("/")
            if len(parts) == 3:
                dia, mes, ano = parts
                return f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"

            return None
        except:
            return None

    def _parse_datetime(self, data_str) -> Optional[str]:
        """
        Converte data/hora para formato ISO timestamp.

        Entrada: "15/01/2026 14:30" ou "15/01/2026"
        Saída: "2026-01-15T14:30:00"
        """
        if not data_str or data_str == "N/D":
            return None

        try:
            # Se tem hora
            if " " in data_str:
                data_parte, hora_parte = data_str.split(" ", 1)
                data_iso = self._parse_data(data_parte)
                if data_iso:
                    return f"{data_iso}T{hora_parte}:00"

            # Só data
            data_iso = self._parse_data(data_str)
            if data_iso:
                return f"{data_iso}T00:00:00"

            return None
        except:
            return None

    def contar_editais(self) -> int:
        """
        Conta total de editais no Supabase.

        Returns:
            Número de editais ou -1 se erro
        """
        if not self.enable_supabase:
            return -1

        try:
            response = (
                self.client.table("editais_leilao")
                .select("id", count="exact")
                .limit(0)
                .execute()
            )
            return response.count
        except Exception as e:
            logger.error("Erro ao contar editais: %s", e)
            return -1

    def listar_editais_recentes(self, limit: int = 10) -> List[Dict]:
        """
        Lista editais mais recentes.

        Args:
            limit: Número máximo de editais

        Returns:
            Lista de dicionários com dados dos editais
        """
        if not self.enable_supabase:
            return []

        try:
            response = (
                self.client.table("editais_leilao")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error("Erro ao listar editais: %s", e)
            return []


# Teste básico
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TESTE SUPABASE REPOSITORY")
    print("=" * 60)

    repo = SupabaseRepository()

    if repo.enable_supabase:
        print("\n[OK] Supabase conectado")

        # Contar editais
        count = repo.contar_editais()
        print(f"[INFO] Total de editais no banco: {count}")

    else:
        print("\n[AVISO] Supabase desabilitado")
