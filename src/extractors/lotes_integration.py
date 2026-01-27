#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
LOTES INTEGRATION - Módulo de Integração com Pipeline
=============================================================================
Conecta o extrator de lotes ao Cloud Auditor V19.

Versão: 1.1.0
Data: 2026-01-26
Autor: Tech Lead (Claude Code)

Changelog:
- V1.1.0: Idempotência via tabela arquivos_processados_lotes
- V1.1.0: Skip de PDFs já processados (usa hash SHA256)
- V1.0.0: Versão inicial

Funcionalidades:
- Aceita BytesIO (memória) ou caminho de arquivo
- Integra com repositório Supabase existente
- Retorna métricas de extração
- IDEMPOTÊNCIA: Verifica se PDF já foi processado via hash
=============================================================================
"""

import hashlib
import logging
import os
import tempfile
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import pdfplumber
from supabase import Client

# Importar componentes do extrator
from .lotes_extractor_v1 import (
    ClassificadorPDF,
    ExtratorTabelas,
    LoteExtraido,
    ResultadoExtracao,
    FamiliaPDF,
    EstagioFalha,
    CodigoErro,
    VERSAO_EXTRATOR,
)

logger = logging.getLogger('LotesIntegration')


class LotesIntegration:
    """
    Módulo de integração do extrator de lotes com o pipeline.

    Projetado para ser chamado pelo Cloud Auditor V19 após
    extrair o link do leiloeiro.
    """

    def __init__(self, supabase_client: Optional[Client] = None):
        """
        Inicializa o módulo de integração.

        Args:
            supabase_client: Cliente Supabase já conectado (opcional)
        """
        self.client = supabase_client
        self.extrator = ExtratorTabelas()
        self.classificador = ClassificadorPDF()

        # Métricas da sessão
        self.metricas = {
            'total_pdfs': 0,
            'total_lotes': 0,
            'total_quarentena': 0,
            'pdfs_skip_ja_processados': 0,  # V1.1: Idempotência
            'por_familia': {},
        }

    # =========================================================================
    # V1.1: MÉTODOS DE IDEMPOTÊNCIA
    # =========================================================================

    def _calcular_hash_pdf(self, pdf_bytesio: BytesIO) -> str:
        """
        Calcula hash SHA256 do PDF para identificação única.

        Args:
            pdf_bytesio: PDF em memória

        Returns:
            Hash SHA256 em hexadecimal
        """
        pdf_bytesio.seek(0)
        hash_sha256 = hashlib.sha256(pdf_bytesio.read()).hexdigest()
        pdf_bytesio.seek(0)  # Reset para leitura posterior
        return hash_sha256

    def _verificar_arquivo_processado(self, hash_arquivo: str) -> Optional[Dict[str, Any]]:
        """
        Verifica se um arquivo já foi processado via tabela arquivos_processados_lotes.

        Args:
            hash_arquivo: Hash SHA256 do arquivo

        Returns:
            Registro encontrado ou None se não processado
        """
        if not self.client:
            return None

        try:
            response = (
                self.client.table('arquivos_processados_lotes')
                .select('*')
                .eq('hash_arquivo', hash_arquivo)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Erro ao verificar arquivo processado: {e}")
            return None

    def _registrar_arquivo_processado(
        self,
        edital_id: int,
        nome_arquivo: str,
        hash_arquivo: str,
        tipo_detectado: str,
        familia_pdf: Optional[str],
        total_lotes: int,
        total_quarentena: int,
        status: str,
        mensagem: Optional[str],
        tempo_ms: int,
    ) -> bool:
        """
        Registra que um arquivo foi processado.

        Args:
            edital_id: ID do edital
            nome_arquivo: Nome do arquivo
            hash_arquivo: Hash SHA256
            tipo_detectado: Tipo do arquivo (pdf_nativo, pdf_escaneado, etc)
            familia_pdf: Família estrutural do PDF
            total_lotes: Total de lotes extraídos
            total_quarentena: Total enviado para quarentena
            status: Status final (processado, erro, escaneado)
            mensagem: Mensagem de status
            tempo_ms: Tempo de processamento em ms

        Returns:
            True se registrado com sucesso
        """
        if not self.client:
            return False

        try:
            dados = {
                'edital_id': edital_id,
                'nome_arquivo': nome_arquivo,
                'hash_arquivo': hash_arquivo,
                'tipo_detectado': tipo_detectado,
                'familia_pdf': familia_pdf,
                'total_lotes_extraidos': total_lotes,
                'total_lotes_quarentena': total_quarentena,
                'status': status,
                'mensagem_status': mensagem,
                'versao_extrator': VERSAO_EXTRATOR,
                'processado_em': datetime.now().isoformat(),
                'tempo_processamento_ms': tempo_ms,
            }

            # UPSERT: Se o hash já existir, atualiza (reprocessamento com --force)
            self.client.table('arquivos_processados_lotes').upsert(
                dados,
                on_conflict='hash_arquivo'
            ).execute()

            logger.debug(f"[IDEMPOTENCIA] Arquivo registrado: {nome_arquivo} ({status})")
            return True

        except Exception as e:
            logger.error(f"Erro ao registrar arquivo processado: {e}")
            return False

    def extrair_lotes_de_bytesio(
        self,
        pdf_bytesio: BytesIO,
        edital_id: int,
        arquivo_nome: str,
        pncp_id: Optional[str] = None,
    ) -> ResultadoExtracao:
        """
        Extrai lotes de um PDF em memória (BytesIO).

        Args:
            pdf_bytesio: PDF em memória
            edital_id: ID do edital no banco (FK)
            arquivo_nome: Nome do arquivo para rastreamento
            pncp_id: ID PNCP (opcional, para logs)

        Returns:
            ResultadoExtracao com lotes extraídos ou erros
        """
        logger.info(f"Extraindo lotes de {arquivo_nome} (edital_id={edital_id})")

        # Salvar em arquivo temporário para processamento
        # (pdfplumber funciona melhor com arquivo)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytesio.getvalue())
            tmp_path = tmp.name

        try:
            resultado = self.extrator.extrair(tmp_path, edital_id)

            # Atualizar métricas
            self.metricas['total_pdfs'] += 1
            if resultado.familia_pdf:
                familia = resultado.familia_pdf.value
                self.metricas['por_familia'][familia] = \
                    self.metricas['por_familia'].get(familia, 0) + 1

            if resultado.sucesso:
                self.metricas['total_lotes'] += len(resultado.lotes)
                logger.info(f"  Extraídos {len(resultado.lotes)} lotes de {arquivo_nome}")
            else:
                self.metricas['total_quarentena'] += 1
                logger.warning(f"  Falha na extração de {arquivo_nome}: {resultado.erros}")

            return resultado

        finally:
            # Limpar arquivo temporário
            try:
                os.unlink(tmp_path)
            except:
                pass

    def salvar_lotes_supabase(
        self,
        lotes: List[LoteExtraido],
        edital_id: int,
        arquivo_nome: str,
        familia_pdf: Optional[FamiliaPDF] = None,
    ) -> Dict[str, Any]:
        """
        Salva lotes extraídos no Supabase.

        Args:
            lotes: Lista de lotes extraídos
            edital_id: ID do edital (FK)
            arquivo_nome: Nome do arquivo fonte
            familia_pdf: Família do PDF

        Returns:
            Dict com estatísticas da operação
        """
        if not self.client:
            logger.warning("Cliente Supabase não configurado - lotes não salvos")
            return {'sucesso': False, 'motivo': 'sem_cliente_supabase'}

        salvos = 0
        erros = 0

        for lote in lotes:
            try:
                id_interno = lote.gerar_id_interno(edital_id)
                hash_fonte = hashlib.sha256(
                    lote.texto_fonte_completo.encode() if lote.texto_fonte_completo else b''
                ).hexdigest()

                dados = {
                    'id_interno': id_interno,
                    'edital_id': edital_id,

                    # Dados brutos
                    'numero_lote_raw': lote.numero_lote_raw,
                    'descricao_raw': lote.descricao_raw,
                    'valor_raw': lote.valor_raw,
                    'texto_fonte_completo': lote.texto_fonte_completo,

                    # Dados processados
                    'numero_lote': lote.numero_lote,
                    'descricao_completa': lote.descricao_completa,
                    'avaliacao_valor': lote.avaliacao_valor,

                    # Dados de veículo
                    'placa': lote.placa,
                    'chassi': lote.chassi,
                    'renavam': lote.renavam,
                    'marca': lote.marca,
                    'modelo': lote.modelo,
                    'ano_fabricacao': lote.ano_fabricacao,

                    # Metadados
                    'fonte_tipo': 'pdf_tabela',
                    'fonte_arquivo': arquivo_nome,
                    'fonte_pagina': lote.fonte_pagina,
                    'hash_conteudo_fonte': hash_fonte,
                    'versao_extrator': VERSAO_EXTRATOR,
                    'familia_pdf': familia_pdf.value if familia_pdf else None,
                }

                self.client.table('lotes_leilao').upsert(
                    dados,
                    on_conflict='id_interno'
                ).execute()

                salvos += 1

            except Exception as e:
                logger.error(f"Erro ao salvar lote: {e}")
                erros += 1

        logger.info(f"Lotes salvos: {salvos}, erros: {erros}")
        return {'sucesso': True, 'salvos': salvos, 'erros': erros}

    def enviar_quarentena(
        self,
        edital_id: int,
        arquivo_nome: str,
        resultado: ResultadoExtracao,
    ) -> bool:
        """
        Envia resultado com erro para quarentena.

        Args:
            edital_id: ID do edital
            arquivo_nome: Nome do arquivo
            resultado: Resultado da extração com erros

        Returns:
            True se enviado com sucesso
        """
        if not self.client:
            return False

        try:
            for erro in resultado.erros:
                dados = {
                    'edital_id': edital_id,
                    'payload_original': {'arquivo': arquivo_nome},
                    'estagio_falha': EstagioFalha.EXTRACAO.value,
                    'codigo_erro': erro.get('codigo', 'DESCONHECIDO'),
                    'mensagem_erro': erro.get('mensagem', 'Erro desconhecido'),
                    'fonte_tipo': 'pdf',
                    'fonte_arquivo': arquivo_nome,
                    'familia_pdf': resultado.familia_pdf.value if resultado.familia_pdf else None,
                    'versao_extrator': VERSAO_EXTRATOR,
                    'status': 'pendente',
                }

                self.client.table('lotes_quarentena').insert(dados).execute()

            return True

        except Exception as e:
            logger.error(f"Erro ao enviar para quarentena: {e}")
            return False

    def processar_pdf_completo(
        self,
        pdf_bytesio: BytesIO,
        edital_id: int,
        arquivo_nome: str,
        pncp_id: Optional[str] = None,
        salvar_banco: bool = True,
        force_reprocess: bool = False,
    ) -> Dict[str, Any]:
        """
        Processa um PDF completo: extrai lotes e salva no banco.

        Este é o método principal a ser chamado pelo Auditor V19.

        V1.1 IDEMPOTÊNCIA: Verifica se o PDF já foi processado via hash.
        Use force_reprocess=True para reprocessar mesmo assim.

        Args:
            pdf_bytesio: PDF em memória
            edital_id: ID do edital no banco
            arquivo_nome: Nome do arquivo
            pncp_id: ID PNCP (para logs)
            salvar_banco: Se True, salva no Supabase
            force_reprocess: Se True, reprocessa mesmo se já foi processado

        Returns:
            Dict com estatísticas:
            {
                'sucesso': bool,
                'total_lotes': int,
                'lotes_salvos': int,
                'familia_pdf': str,
                'tempo_ms': int,
                'skip_ja_processado': bool,  # V1.1
            }
        """
        import time
        inicio = time.time()

        # V1.1: IDEMPOTÊNCIA - Verificar se já foi processado
        hash_arquivo = self._calcular_hash_pdf(pdf_bytesio)
        registro_existente = self._verificar_arquivo_processado(hash_arquivo)

        if registro_existente and not force_reprocess:
            # Já foi processado - SKIP
            self.metricas['pdfs_skip_ja_processados'] += 1
            logger.info(
                f"[IDEMPOTENCIA] SKIP: {arquivo_nome} já processado em "
                f"{registro_existente.get('processado_em', '?')} "
                f"(lotes={registro_existente.get('total_lotes_extraidos', 0)})"
            )
            return {
                'sucesso': True,
                'total_lotes': registro_existente.get('total_lotes_extraidos', 0),
                'lotes_salvos': registro_existente.get('total_lotes_extraidos', 0),
                'familia_pdf': registro_existente.get('familia_pdf'),
                'tempo_ms': 0,
                'erros': [],
                'skip_ja_processado': True,
                'processado_em_anterior': registro_existente.get('processado_em'),
            }

        if registro_existente and force_reprocess:
            logger.info(f"[IDEMPOTENCIA] FORCE: Reprocessando {arquivo_nome} (--force ativo)")

        # Extrair lotes
        resultado = self.extrair_lotes_de_bytesio(
            pdf_bytesio=pdf_bytesio,
            edital_id=edital_id,
            arquivo_nome=arquivo_nome,
            pncp_id=pncp_id,
        )

        stats = {
            'sucesso': resultado.sucesso,
            'total_lotes': len(resultado.lotes),
            'lotes_salvos': 0,
            'familia_pdf': resultado.familia_pdf.value if resultado.familia_pdf else None,
            'tempo_ms': 0,
            'erros': resultado.erros,
            'skip_ja_processado': False,
        }

        total_quarentena = 0

        if resultado.sucesso and resultado.lotes and salvar_banco:
            # Salvar lotes
            res_salvar = self.salvar_lotes_supabase(
                lotes=resultado.lotes,
                edital_id=edital_id,
                arquivo_nome=arquivo_nome,
                familia_pdf=resultado.familia_pdf,
            )
            stats['lotes_salvos'] = res_salvar.get('salvos', 0)

        elif not resultado.sucesso and salvar_banco:
            # Enviar para quarentena
            self.enviar_quarentena(
                edital_id=edital_id,
                arquivo_nome=arquivo_nome,
                resultado=resultado,
            )
            total_quarentena = 1

        stats['tempo_ms'] = int((time.time() - inicio) * 1000)

        # V1.1: Registrar arquivo como processado
        if salvar_banco:
            status_final = 'processado' if resultado.sucesso else 'erro'
            self._registrar_arquivo_processado(
                edital_id=edital_id,
                nome_arquivo=arquivo_nome,
                hash_arquivo=hash_arquivo,
                tipo_detectado='pdf_nativo',  # TODO: detectar tipo real
                familia_pdf=stats['familia_pdf'],
                total_lotes=len(resultado.lotes),
                total_quarentena=total_quarentena,
                status=status_final,
                mensagem=resultado.erros[0].get('mensagem') if resultado.erros else None,
                tempo_ms=stats['tempo_ms'],
            )

        return stats

    def get_metricas(self) -> Dict[str, Any]:
        """Retorna métricas da sessão."""
        return self.metricas.copy()

    def reset_metricas(self):
        """Reseta métricas da sessão."""
        self.metricas = {
            'total_pdfs': 0,
            'total_lotes': 0,
            'total_quarentena': 0,
            'por_familia': {},
        }


# =============================================================================
# FUNÇÃO DE CONVENIÊNCIA PARA O AUDITOR
# =============================================================================

def criar_integrador_lotes(supabase_client: Optional[Client] = None) -> LotesIntegration:
    """
    Cria uma instância do integrador de lotes.

    Uso no Auditor V19:
        from src.extractors.lotes_integration import criar_integrador_lotes

        integrador = criar_integrador_lotes(self.repo.client)

        # Após processar PDF
        stats = integrador.processar_pdf_completo(
            pdf_bytesio=BytesIO(pdf_data),
            edital_id=edital['id'],
            arquivo_nome=pdf_info['name'],
            pncp_id=pncp_id,
        )
    """
    return LotesIntegration(supabase_client)
