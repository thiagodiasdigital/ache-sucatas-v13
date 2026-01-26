#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
LOTES INTEGRATION - Módulo de Integração com Pipeline
=============================================================================
Conecta o extrator de lotes ao Cloud Auditor V19.

Versão: 1.0.0
Data: 2026-01-25
Autor: Tech Lead (Claude Code)

Funcionalidades:
- Aceita BytesIO (memória) ou caminho de arquivo
- Integra com repositório Supabase existente
- Retorna métricas de extração
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
            'por_familia': {},
        }

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
    ) -> Dict[str, Any]:
        """
        Processa um PDF completo: extrai lotes e salva no banco.

        Este é o método principal a ser chamado pelo Auditor V19.

        Args:
            pdf_bytesio: PDF em memória
            edital_id: ID do edital no banco
            arquivo_nome: Nome do arquivo
            pncp_id: ID PNCP (para logs)
            salvar_banco: Se True, salva no Supabase

        Returns:
            Dict com estatísticas:
            {
                'sucesso': bool,
                'total_lotes': int,
                'lotes_salvos': int,
                'familia_pdf': str,
                'tempo_ms': int,
            }
        """
        import time
        inicio = time.time()

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
        }

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

        stats['tempo_ms'] = int((time.time() - inicio) * 1000)

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
