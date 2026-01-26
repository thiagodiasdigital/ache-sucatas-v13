# -*- coding: utf-8 -*-
"""
Módulo de Extratores - Ache Sucatas DaaS

Este módulo contém os extratores de dados para processamento de PDFs e outros formatos.
"""

from .lotes_extractor_v1 import (
    LotesExtractorV1,
    ExtratorTabelas,
    ClassificadorPDF,
    LotesRepository,
    LoteExtraido,
    ResultadoExtracao,
    ResultadoClassificacao,
    MetricasExecucao,
    FamiliaPDF,
    EstagioFalha,
    CodigoErro,
    VERSAO_EXTRATOR,
)

from .lotes_integration import (
    LotesIntegration,
    criar_integrador_lotes,
)

__all__ = [
    # Extrator V1
    'LotesExtractorV1',
    'ExtratorTabelas',
    'ClassificadorPDF',
    'LotesRepository',
    'LoteExtraido',
    'ResultadoExtracao',
    'ResultadoClassificacao',
    'MetricasExecucao',
    'FamiliaPDF',
    'EstagioFalha',
    'CodigoErro',
    'VERSAO_EXTRATOR',
    # Integração
    'LotesIntegration',
    'criar_integrador_lotes',
]
