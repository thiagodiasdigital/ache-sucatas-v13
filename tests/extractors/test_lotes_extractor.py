#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Testes para o Extrator de Lotes V1
=============================================================================
Data: 2026-01-25
Autor: Tech Lead (Claude Code)

Testes unitários para validar:
- Limpeza de dados (número do lote, descrição, valor)
- Geração de ID interno (idempotência)
- Classificação de PDFs
- Códigos de erro padronizados
- Versionamento do extrator
=============================================================================
"""

import pytest
import sys
import os

# Ajustar path para importar o módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'extractors'))

from lotes_extractor_v1 import (
    LoteExtraido,
    ClassificadorPDF,
    ExtratorTabelas,
    FamiliaPDF,
    CodigoErro,
    EstagioFalha,
    ResultadoClassificacao,
    VERSAO_EXTRATOR
)


# =============================================================================
# TESTES: LoteExtraido
# =============================================================================

class TestLoteExtraido:
    """Testes para a classe LoteExtraido."""

    def test_limpeza_numero_lote_basico(self):
        """Testa limpeza básica do número do lote."""
        lote = LoteExtraido(
            numero_lote_raw="  LOTE 01  ",
            descricao_raw="Descrição teste"
        )
        assert lote.numero_lote == "01"

    def test_limpeza_numero_lote_com_prefixo(self):
        """Testa remoção de prefixos variados."""
        casos = [
            ("LOTE 123", "123"),
            ("Item 45", "45"),
            ("N. 67", "67"),
            ("Nº 89", "89"),
            ("  01  ", "01"),
        ]
        for raw, esperado in casos:
            lote = LoteExtraido(numero_lote_raw=raw, descricao_raw="Teste descricao valida")
            assert lote.numero_lote == esperado, f"Falhou para: {raw}"

    def test_limpeza_descricao_remove_quebras(self):
        """Testa que quebras de linha são removidas da descrição."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO\n2010\nBRANCO"
        )
        assert lote.descricao_completa == "FIAT UNO 2010 BRANCO"

    def test_limpeza_descricao_remove_espacos_extras(self):
        """Testa que espaços extras são normalizados."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT    UNO     2010"
        )
        assert lote.descricao_completa == "FIAT UNO 2010"

    def test_limpeza_valor_formato_brasileiro(self):
        """Testa conversão de valores no formato brasileiro."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw="R$ 22.500,00"
        )
        assert lote.avaliacao_valor == 22500.00

    def test_limpeza_valor_formato_brasileiro_sem_centavos(self):
        """Testa conversão de valores sem centavos."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw="R$ 15.000"
        )
        assert lote.avaliacao_valor == 15000.00

    def test_limpeza_valor_formato_simples(self):
        """Testa conversão de valores simples."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw="5000,00"
        )
        assert lote.avaliacao_valor == 5000.00

    def test_limpeza_valor_formato_americano(self):
        """Testa conversão de valores no formato americano."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw="$22,500.00"
        )
        assert lote.avaliacao_valor == 22500.00

    def test_limpeza_valor_invalido_nao_retorna_zero(self):
        """
        TESTE CRÍTICO: Valor inválido NÃO deve retornar 0.0 silenciosamente.
        Deve retornar None para indicar falha.
        """
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw="A DEFINIR"
        )
        assert lote.avaliacao_valor is None, "Valor inválido não deve virar 0.0"

    def test_limpeza_valor_vazio_retorna_none(self):
        """Testa que valor vazio retorna None."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw=""
        )
        assert lote.avaliacao_valor is None

    def test_limpeza_valor_none_retorna_none(self):
        """Testa que valor None retorna None."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="Teste descricao",
            valor_raw=None
        )
        assert lote.avaliacao_valor is None

    def test_gerar_id_interno_deterministico(self):
        """Testa que o mesmo input gera o mesmo id_interno."""
        lote1 = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010"
        )
        lote2 = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010"
        )

        id1 = lote1.gerar_id_interno(edital_id=123)
        id2 = lote2.gerar_id_interno(edital_id=123)

        assert id1 == id2, "Mesmo conteúdo deve gerar mesmo ID"

    def test_gerar_id_interno_diferente_para_editais_diferentes(self):
        """Testa que editais diferentes geram IDs diferentes."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010"
        )

        id1 = lote.gerar_id_interno(edital_id=123)
        id2 = lote.gerar_id_interno(edital_id=456)

        assert id1 != id2, "Editais diferentes devem gerar IDs diferentes"

    def test_gerar_id_interno_diferente_para_lotes_diferentes(self):
        """Testa que lotes diferentes geram IDs diferentes."""
        lote1 = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010"
        )
        lote2 = LoteExtraido(
            numero_lote_raw="02",
            descricao_raw="FIAT PALIO 2015"
        )

        id1 = lote1.gerar_id_interno(edital_id=123)
        id2 = lote2.gerar_id_interno(edital_id=123)

        assert id1 != id2, "Lotes diferentes devem gerar IDs diferentes"

    def test_gerar_id_interno_formato_sha256(self):
        """Testa que o ID interno é um hash SHA256 válido."""
        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010"
        )

        id_interno = lote.gerar_id_interno(edital_id=123)

        # SHA256 tem 64 caracteres hexadecimais
        assert len(id_interno) == 64
        assert all(c in '0123456789abcdef' for c in id_interno)


# =============================================================================
# TESTES: ClassificadorPDF
# =============================================================================

class TestClassificadorPDF:
    """Testes para o ClassificadorPDF."""

    def test_normalizar_texto_remove_acentos(self):
        """Testa normalização de texto com acentos."""
        classificador = ClassificadorPDF()

        casos = [
            ("DESCRIÇÃO", "descricao"),
            ("VEÍCULO", "veiculo"),
            ("AVALIAÇÃO", "avaliacao"),
            ("NÚMERO", "numero"),
            ("ÓRGÃO", "orgao"),
            ("CAMINHÃO", "caminhao"),
        ]

        for texto, esperado in casos:
            resultado = classificador._normalizar_texto(texto)
            assert resultado == esperado, f"Falhou para: {texto}"

    def test_normalizar_texto_lowercase(self):
        """Testa que normalização converte para lowercase."""
        classificador = ClassificadorPDF()

        resultado = classificador._normalizar_texto("TEXTO MAIUSCULO")
        assert resultado == "texto maiusculo"

    def test_normalizar_texto_vazio(self):
        """Testa normalização de texto vazio."""
        classificador = ClassificadorPDF()

        resultado = classificador._normalizar_texto("")
        assert resultado == ""

    def test_normalizar_texto_none(self):
        """Testa normalização de None."""
        classificador = ClassificadorPDF()

        resultado = classificador._normalizar_texto(None)
        assert resultado == ""


# =============================================================================
# TESTES: Enums
# =============================================================================

class TestFamiliaPDF:
    """Testes para o enum FamiliaPDF."""

    def test_familias_existem(self):
        """Verifica que todas as famílias estão definidas."""
        assert FamiliaPDF.PDF_TABELA_INICIO.value == "PDF_TABELA_INICIO"
        assert FamiliaPDF.PDF_TABELA_MEIO_FIM.value == "PDF_TABELA_MEIO_FIM"
        assert FamiliaPDF.PDF_NATIVO_SEM_TABELA.value == "PDF_NATIVO_SEM_TABELA"
        assert FamiliaPDF.PDF_ESCANEADO.value == "PDF_ESCANEADO"

    def test_total_familias(self):
        """Verifica que há exatamente 4 famílias."""
        assert len(FamiliaPDF) == 4


class TestCodigosErro:
    """Testa padronização dos códigos de erro."""

    def test_codigos_classificacao_existem(self):
        """Verifica que códigos de classificação estão definidos."""
        assert CodigoErro.PDF_ESCANEADO.value == "PDF_ESCANEADO"
        assert CodigoErro.PDF_CORROMPIDO.value == "PDF_CORROMPIDO"
        assert CodigoErro.TIPO_NAO_SUPORTADO.value == "TIPO_NAO_SUPORTADO"

    def test_codigos_extracao_existem(self):
        """Verifica que códigos de extração estão definidos."""
        assert CodigoErro.TABELA_NAO_ENCONTRADA.value == "TABELA_NAO_ENCONTRADA"
        assert CodigoErro.TABELA_SEM_CABECALHO_VALIDO.value == "TABELA_SEM_CABECALHO_VALIDO"
        assert CodigoErro.ESTRUTURA_INESPERADA.value == "ESTRUTURA_INESPERADA"

    def test_codigos_validacao_existem(self):
        """Verifica que códigos de validação estão definidos."""
        assert CodigoErro.NUMERO_LOTE_AUSENTE.value == "NUMERO_LOTE_AUSENTE"
        assert CodigoErro.DESCRICAO_INSUFICIENTE.value == "DESCRICAO_INSUFICIENTE"
        assert CodigoErro.VALOR_NAO_PARSEAVEL.value == "VALOR_NAO_PARSEAVEL"

    def test_codigos_persistencia_existem(self):
        """Verifica que códigos de persistência estão definidos."""
        assert CodigoErro.ERRO_BANCO_DADOS.value == "ERRO_BANCO_DADOS"
        assert CodigoErro.CONSTRAINT_VIOLADA.value == "CONSTRAINT_VIOLADA"


class TestEstagioFalha:
    """Testa enum de estágios de falha."""

    def test_estagios_existem(self):
        """Verifica que todos os estágios estão definidos."""
        assert EstagioFalha.CLASSIFICACAO.value == "classificacao"
        assert EstagioFalha.EXTRACAO.value == "extracao"
        assert EstagioFalha.VALIDACAO.value == "validacao"
        assert EstagioFalha.ENRIQUECIMENTO.value == "enriquecimento"
        assert EstagioFalha.PERSISTENCIA.value == "persistencia"


# =============================================================================
# TESTES: Versionamento
# =============================================================================

class TestVersaoExtrator:
    """Testa versionamento do extrator."""

    def test_versao_definida(self):
        """Verifica que versão está definida corretamente."""
        assert VERSAO_EXTRATOR == "lotes_extractor_v1"

    def test_versao_nao_vazia(self):
        """Verifica que versão não está vazia."""
        assert len(VERSAO_EXTRATOR) > 0


# =============================================================================
# TESTES: ExtratorTabelas
# =============================================================================

class TestExtratorTabelas:
    """Testes para o ExtratorTabelas."""

    def test_identificar_colunas_basico(self):
        """Testa identificação de colunas em cabeçalho básico."""
        extrator = ExtratorTabelas()

        cabecalho = ['Lote', 'Descrição', 'Valor', 'Placa']
        indices = extrator._identificar_colunas(cabecalho)

        assert 'numero' in indices
        assert 'descricao' in indices
        assert 'valor' in indices
        assert 'placa' in indices

    def test_identificar_colunas_veiculo(self):
        """Testa identificação de colunas de veículo."""
        extrator = ExtratorTabelas()

        cabecalho = ['Item', 'Placa', 'Chassi', 'Renavam', 'Marca', 'Modelo', 'Ano']
        indices = extrator._identificar_colunas(cabecalho)

        assert 'numero' in indices
        assert 'placa' in indices
        assert 'chassi' in indices
        assert 'renavam' in indices
        assert 'marca' in indices
        assert 'modelo' in indices
        assert 'ano' in indices

    def test_lote_valido_com_descricao_curta(self):
        """Testa que lote com descrição muito curta é inválido."""
        extrator = ExtratorTabelas()

        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="ABC"  # Menos de 10 caracteres
        )

        assert extrator._lote_valido(lote) is False

    def test_lote_valido_sem_numero(self):
        """Testa que lote sem número é inválido."""
        extrator = ExtratorTabelas()

        lote = LoteExtraido(
            numero_lote_raw="",
            descricao_raw="FIAT UNO 2010 BRANCO"
        )

        assert extrator._lote_valido(lote) is False

    def test_lote_valido_completo(self):
        """Testa que lote completo é válido."""
        extrator = ExtratorTabelas()

        lote = LoteExtraido(
            numero_lote_raw="01",
            descricao_raw="FIAT UNO 2010 BRANCO"
        )

        assert extrator._lote_valido(lote) is True


# =============================================================================
# TESTES: ResultadoClassificacao
# =============================================================================

class TestResultadoClassificacao:
    """Testes para ResultadoClassificacao."""

    def test_resultado_processavel_por_padrao(self):
        """Testa que resultado é processável por padrão."""
        resultado = ResultadoClassificacao(
            familia=FamiliaPDF.PDF_TABELA_INICIO,
            total_caracteres=1000,
            total_paginas=5
        )

        assert resultado.processavel is True
        assert resultado.motivo_nao_processavel is None

    def test_resultado_nao_processavel(self):
        """Testa resultado não processável."""
        resultado = ResultadoClassificacao(
            familia=FamiliaPDF.PDF_ESCANEADO,
            total_caracteres=50,
            total_paginas=3,
            processavel=False,
            motivo_nao_processavel="PDF escaneado"
        )

        assert resultado.processavel is False
        assert resultado.motivo_nao_processavel == "PDF escaneado"


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
