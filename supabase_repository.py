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

    # =========================================================================
    # MÉTODOS PARA DASHBOARD - Filtros e consultas
    # =========================================================================

    def listar_editais_filtrados(
        self,
        uf: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        modalidade: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Lista editais com filtros opcionais.

        Args:
            uf: Filtrar por UF (ex: "SP", "RJ")
            data_inicio: Data inicial ISO (ex: "2026-01-01")
            data_fim: Data final ISO (ex: "2026-01-31")
            modalidade: ONLINE | PRESENCIAL | HIBRIDO | N/D
            limit: Máximo de resultados (default 100)

        Returns:
            Lista de dicionários com dados dos editais
        """
        if not self.enable_supabase:
            return []

        try:
            query = self.client.table("editais_leilao").select(
                "id, pncp_id, titulo, orgao, uf, cidade, "
                "data_publicacao, data_leilao, valor_estimado, "
                "quantidade_itens, modalidade_leilao, nome_leiloeiro, "
                "link_pncp, storage_path, score"
            )

            # Aplicar filtros
            if uf:
                query = query.eq("uf", uf)

            if data_inicio:
                query = query.gte("data_publicacao", data_inicio)

            if data_fim:
                query = query.lte("data_publicacao", data_fim)

            if modalidade:
                query = query.eq("modalidade_leilao", modalidade)

            # Ordenar e limitar
            query = query.order("data_publicacao", desc=True).limit(limit)

            response = query.execute()
            return response.data

        except Exception as e:
            logger.error("Erro ao listar editais filtrados: %s", e)
            return []

    def listar_ufs_disponiveis(self) -> List[str]:
        """
        Lista UFs que possuem editais no banco.

        Returns:
            Lista de UFs ordenadas (ex: ["BA", "MG", "SP"])
        """
        if not self.enable_supabase:
            return []

        try:
            response = (
                self.client.table("editais_leilao")
                .select("uf")
                .execute()
            )

            # Extrair UFs únicas
            ufs = set(item["uf"] for item in response.data if item.get("uf"))
            return sorted(list(ufs))

        except Exception as e:
            logger.error("Erro ao listar UFs: %s", e)
            return []

    def listar_modalidades_disponiveis(self) -> List[str]:
        """
        Lista modalidades de leilão disponíveis.

        Returns:
            Lista de modalidades (ex: ["ONLINE", "PRESENCIAL", "N/D"])
        """
        if not self.enable_supabase:
            return []

        try:
            response = (
                self.client.table("editais_leilao")
                .select("modalidade_leilao")
                .execute()
            )

            modalidades = set(
                item["modalidade_leilao"]
                for item in response.data
                if item.get("modalidade_leilao")
            )
            return sorted(list(modalidades))

        except Exception as e:
            logger.error("Erro ao listar modalidades: %s", e)
            return []

    # =========================================================================
    # MÉTODOS PARA MINER V10 - Execuções e Editais direto do Miner
    # =========================================================================

    def iniciar_execucao_miner(
        self,
        versao_miner: str,
        janela_temporal: int,
        termos: int,
        paginas: int,
    ) -> Optional[int]:
        """
        Registra início de execução do Miner no Supabase.

        Args:
            versao_miner: Versão do miner (ex: "V10_CRON")
            janela_temporal: Janela temporal em horas (ex: 24)
            termos: Número de termos de busca
            paginas: Páginas por termo

        Returns:
            ID da execução (BIGSERIAL) ou None se erro
        """
        if not self.enable_supabase:
            logger.debug("Supabase desabilitado - skip iniciar_execucao")
            return None

        try:
            data = {
                "execution_start": datetime.now().isoformat(),
                "status": "RUNNING",
                "versao_miner": versao_miner,
                "janela_temporal_horas": janela_temporal,
                "termos_buscados": termos,
                "paginas_por_termo": paginas,
                "editais_analisados": 0,
                "editais_novos": 0,
                "editais_duplicados": 0,
                "downloads": 0,
                "downloads_sucesso": 0,
                "downloads_falha": 0,
            }

            response = self.client.table("execucoes_miner").insert(data).execute()

            if response.data:
                exec_id = response.data[0]["id"]
                logger.info("Execução Miner iniciada: ID=%d", exec_id)
                return exec_id

            return None

        except Exception as e:
            logger.error("Erro ao iniciar execução miner: %s", e)
            return None

    def finalizar_execucao_miner(
        self,
        execucao_id: int,
        metricas: dict,
        status: str = "SUCCESS",
        erro: str = None,
    ) -> bool:
        """
        Finaliza execução do Miner com métricas.

        Args:
            execucao_id: ID retornado por iniciar_execucao_miner
            metricas: Dict com métricas do MetricsTracker
            status: "SUCCESS" ou "FAILED"
            erro: Mensagem de erro (se status=FAILED)

        Returns:
            True se sucesso
        """
        if not self.enable_supabase or not execucao_id:
            return False

        try:
            # Preparar snapshot do checkpoint (últimos 100 IDs)
            pncp_ids = metricas.get("pncp_ids_processados", [])
            checkpoint_snapshot = {
                "pncp_ids_count": len(pncp_ids),
                "last_ids": pncp_ids[-100:] if pncp_ids else [],
            }

            data = {
                "execution_end": datetime.now().isoformat(),
                "duration_seconds": metricas.get("duration_seconds", 0),
                "editais_analisados": metricas.get("editais_analisados", 0),
                "editais_novos": metricas.get("editais_novos", 0),
                "editais_duplicados": metricas.get("editais_duplicados", 0),
                "taxa_deduplicacao": metricas.get("taxa_deduplicacao", 0.0),
                "downloads": metricas.get("downloads", 0),
                "downloads_sucesso": metricas.get("downloads_sucesso", 0),
                "downloads_falha": metricas.get("downloads_falha", 0),
                "status": status,
                "erro": erro[:500] if erro else None,
                "checkpoint_snapshot": checkpoint_snapshot,
            }

            response = (
                self.client.table("execucoes_miner")
                .update(data)
                .eq("id", execucao_id)
                .execute()
            )

            logger.info(
                "Execução #%d finalizada: %s (%d novos editais)",
                execucao_id,
                status,
                metricas.get("editais_novos", 0),
            )
            return True

        except Exception as e:
            logger.error("Erro ao finalizar execução %d: %s", execucao_id, e)
            return False

    def inserir_edital_miner(self, edital_model_data: dict) -> bool:
        """
        Insere edital vindo diretamente do Miner (EditalModel).

        Faz mapeamento EditalModel -> editais_leilao schema V13.
        Campos não disponíveis no Miner serão preenchidos pelo Auditor.

        Args:
            edital_model_data: Dict com dados do EditalModel do Miner

        Returns:
            True se inserido/atualizado com sucesso
        """
        if not self.enable_supabase:
            return False

        try:
            # Mapear EditalModel para schema V13
            dados_v13 = self._mapear_edital_model_para_v13(edital_model_data)

            # Usar método inserir_edital existente (tem upsert e freio)
            return self.inserir_edital(dados_v13)

        except Exception as e:
            logger.error(
                "Erro ao inserir edital miner %s: %s",
                edital_model_data.get("pncp_id"),
                e,
            )
            return False

    def _mapear_edital_model_para_v13(self, edital: dict) -> dict:
        """
        Mapeia EditalModel do Miner V10 para schema editais_leilao.

        Campos do Miner (EditalModel):
        - pncp_id, orgao_nome, orgao_cnpj, uf, municipio
        - titulo, descricao, objeto
        - data_publicacao, data_atualizacao, data_inicio_propostas
        - score, link_pncp, files_url
        - ano_compra, numero_sequencial, modalidade

        Campos V13 que o Auditor preenche depois:
        - link_leiloeiro, valor_estimado, quantidade_itens, nome_leiloeiro
        """
        # Extrair dados básicos
        uf_raw = str(edital.get("uf", "") or "").strip().upper()
        # Validar UF: deve ter exatamente 2 letras
        if len(uf_raw) == 2 and uf_raw.isalpha():
            uf = uf_raw
        else:
            # Tentar extrair UF do município ou usar fallback
            uf = "XX"

        cidade_raw = str(edital.get("municipio", "") or "").strip()
        cidade = cidade_raw.upper().replace(" ", "_") if cidade_raw else "DESCONHECIDA"
        cidade = cidade[:30]  # Limitar tamanho
        pncp_id = edital.get("pncp_id", "")

        # Gerar id_interno: UF_CIDADE_PNCP_ID
        id_interno = f"{uf}_{cidade}_{pncp_id}"

        # Formatar data_publicacao
        data_pub = edital.get("data_publicacao")
        if data_pub:
            if hasattr(data_pub, "strftime"):
                data_pub_str = data_pub.strftime("%Y-%m-%d")
            elif hasattr(data_pub, "isoformat"):
                data_pub_str = str(data_pub).split("T")[0]
            else:
                data_pub_str = str(data_pub).split("T")[0]
        else:
            data_pub_str = datetime.now().strftime("%Y-%m-%d")

        # Formatar data_atualizacao
        data_atual = edital.get("data_atualizacao")
        if data_atual:
            if hasattr(data_atual, "isoformat"):
                data_atual_str = str(data_atual).split("T")[0]
            else:
                data_atual_str = str(data_atual).split("T")[0] if data_atual else None
        else:
            data_atual_str = None

        # Formatar data_leilao (data_inicio_propostas)
        data_leilao = edital.get("data_inicio_propostas")
        if data_leilao:
            if hasattr(data_leilao, "isoformat"):
                data_leilao_str = data_leilao.isoformat()
            else:
                data_leilao_str = str(data_leilao)
        else:
            data_leilao_str = None

        # Gerar n_edital e n_pncp
        seq = edital.get("numero_sequencial", "")
        ano = edital.get("ano_compra", "")
        cnpj = edital.get("orgao_cnpj", "")

        n_edital = f"{seq}/{ano}" if seq and ano else pncp_id
        n_pncp = f"{cnpj}/{ano}/{seq}" if cnpj and ano and seq else pncp_id

        # Score para arquivo_origem
        score = edital.get("score", 0)

        return {
            # Identificadores
            "id_interno": id_interno,
            "pncp_id": pncp_id,
            # Localização
            "orgao": edital.get("orgao_nome", "")[:200],
            "uf": uf,
            "cidade": edital.get("municipio", "")[:100],
            # Edital
            "n_edital": n_edital[:50],
            "n_pncp": n_pncp[:100],
            # Datas
            "data_publicacao": data_pub_str,
            "data_atualizacao": data_atual_str,
            "data_leilao": data_leilao_str,
            # Conteúdo
            "titulo": str(edital.get("titulo", ""))[:500],
            "descricao": str(edital.get("descricao", ""))[:2000],
            "objeto_resumido": str(edital.get("objeto", ""))[:500] if edital.get("objeto") else None,
            # Tags - Miner adiciona tag inicial, Auditor enriquece
            "tags": ["miner_v10"],
            # Links
            "link_pncp": edital.get("link_pncp", ""),
            "link_leiloeiro": None,  # Auditor extrai do PDF
            # Comercial - Auditor extrai esses campos
            "modalidade_leilao": edital.get("modalidade", "N/D"),
            "valor_estimado": None,  # Auditor extrai
            "quantidade_itens": None,  # Auditor extrai
            "nome_leiloeiro": None,  # Auditor extrai
            # Metadata
            "arquivo_origem": f"{uf}_{cidade}/{data_pub_str}_S{score}_{pncp_id}",
            "pdf_hash": None,
            "versao_auditor": "MINER_V10",  # Será sobrescrito pelo Auditor
            # V11: Storage cloud
            "storage_path": edital.get("storage_path"),
            "pdf_storage_url": edital.get("pdf_storage_url"),
        }


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
