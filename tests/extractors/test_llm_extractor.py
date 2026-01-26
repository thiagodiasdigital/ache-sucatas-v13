#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
TESTES: LLMExtractor - Fallback de Extração via LLM
=============================================================================
Testes unitários para a classe LLMExtractor do LotesExtractor V1.1.

Autor: Tech Lead (Claude Code)
Data: 2026-01-26
=============================================================================
"""

import os
import sys
import pytest

# Adicionar path do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'extractors'))

from lotes_extractor_v1 import LLMExtractor, LoteExtraido


# =============================================================================
# TESTES DE INICIALIZAÇÃO
# =============================================================================

class TestLLMExtractorInit:
    """Testes de inicialização do LLMExtractor."""

    def test_init_sem_api_key(self):
        """Deve inicializar sem cliente se não tiver API key."""
        extractor = LLMExtractor(api_key="")
        assert extractor.client is None

    def test_init_graceful_degradation(self):
        """Deve funcionar mesmo sem biblioteca openai ou API key."""
        extractor = LLMExtractor(api_key="")
        assert extractor.total_requests == 0
        assert extractor.get_estimated_cost() == 0.0

    def test_init_model_default(self):
        """Deve usar gpt-4o-mini como modelo default."""
        extractor = LLMExtractor(api_key="")
        assert extractor.model == "gpt-4o-mini"

    def test_init_model_custom(self):
        """Deve aceitar modelo customizado."""
        extractor = LLMExtractor(api_key="", model="gpt-4o")
        assert extractor.model == "gpt-4o"

    def test_init_contadores_zerados(self):
        """Contadores devem iniciar em zero."""
        extractor = LLMExtractor(api_key="")
        assert extractor.total_input_tokens == 0
        assert extractor.total_output_tokens == 0
        assert extractor.total_requests == 0


# =============================================================================
# TESTES DE FINOPS
# =============================================================================

class TestLLMExtractorFinOps:
    """Testes de rastreamento de custos (FinOps)."""

    def test_calculo_custo_zero(self):
        """Custo deve ser zero sem requests."""
        extractor = LLMExtractor(api_key="")
        assert extractor.get_estimated_cost() == 0.0

    def test_calculo_custo_com_tokens_input(self):
        """Deve calcular custo de input corretamente."""
        extractor = LLMExtractor(api_key="")
        extractor.total_input_tokens = 1_000_000  # 1M tokens

        # Custo esperado: 1M * $0.15/1M = $0.15
        cost = extractor.get_estimated_cost()
        assert cost == 0.15

    def test_calculo_custo_com_tokens_output(self):
        """Deve calcular custo de output corretamente."""
        extractor = LLMExtractor(api_key="")
        extractor.total_output_tokens = 1_000_000  # 1M tokens

        # Custo esperado: 1M * $0.60/1M = $0.60
        cost = extractor.get_estimated_cost()
        assert cost == 0.60

    def test_calculo_custo_combinado(self):
        """Deve calcular custo combinado corretamente."""
        extractor = LLMExtractor(api_key="")
        extractor.total_input_tokens = 1_000_000  # 1M
        extractor.total_output_tokens = 100_000   # 0.1M

        # Custo esperado: (1M * 0.15/1M) + (0.1M * 0.60/1M) = 0.15 + 0.06 = 0.21
        cost = extractor.get_estimated_cost()
        assert cost == 0.21

    def test_token_stats_estrutura(self):
        """Deve retornar estrutura correta de stats."""
        extractor = LLMExtractor(api_key="")
        stats = extractor.get_token_stats()

        assert 'total_requests' in stats
        assert 'total_input_tokens' in stats
        assert 'total_output_tokens' in stats
        assert 'total_tokens' in stats
        assert 'estimated_cost_usd' in stats

    def test_token_stats_valores(self):
        """Deve retornar valores corretos nas stats."""
        extractor = LLMExtractor(api_key="")
        extractor.total_input_tokens = 100
        extractor.total_output_tokens = 50
        extractor.total_requests = 1

        stats = extractor.get_token_stats()

        assert stats['total_requests'] == 1
        assert stats['total_input_tokens'] == 100
        assert stats['total_output_tokens'] == 50
        assert stats['total_tokens'] == 150

    def test_precos_configurados(self):
        """Deve ter preços configurados conforme documentação."""
        assert LLMExtractor.PRICE_INPUT_PER_1M == 0.15
        assert LLMExtractor.PRICE_OUTPUT_PER_1M == 0.60


# =============================================================================
# TESTES DE PROMPTS
# =============================================================================

class TestLLMExtractorPrompts:
    """Testes de geração de prompts."""

    def test_system_prompt_contem_regras(self):
        """System prompt deve conter regras de extração."""
        extractor = LLMExtractor(api_key="")
        prompt = extractor._get_system_prompt()

        assert "lotes" in prompt.lower()
        assert "json" in prompt.lower()
        assert "placa" in prompt.lower()
        assert "chassi" in prompt.lower()

    def test_system_prompt_formato_json(self):
        """System prompt deve especificar formato JSON."""
        extractor = LLMExtractor(api_key="")
        prompt = extractor._get_system_prompt()

        assert '"numero"' in prompt
        assert '"descricao"' in prompt
        assert '"valor"' in prompt

    def test_user_prompt_contem_texto(self):
        """User prompt deve conter o texto do edital."""
        extractor = LLMExtractor(api_key="")
        texto = "Texto do edital de teste"
        prompt = extractor._get_user_prompt(texto)

        assert texto in prompt
        assert "TEXTO DO EDITAL" in prompt

    def test_user_prompt_com_contexto(self):
        """User prompt deve incluir contexto quando fornecido."""
        extractor = LLMExtractor(api_key="")
        prompt = extractor._get_user_prompt(
            "texto do edital",
            {"municipio": "São Paulo", "orgao": "Prefeitura"}
        )

        assert "São Paulo" in prompt
        assert "texto do edital" in prompt

    def test_user_prompt_sem_contexto(self):
        """User prompt deve funcionar sem contexto."""
        extractor = LLMExtractor(api_key="")
        prompt = extractor._get_user_prompt("texto do edital")

        assert "texto do edital" in prompt


# =============================================================================
# TESTES DE OTIMIZAÇÃO DE TEXTO
# =============================================================================

class TestLLMExtractorOtimizacao:
    """Testes de otimização de texto para economia de tokens."""

    def test_texto_curto_nao_trunca(self):
        """Texto curto não deve ser truncado."""
        extractor = LLMExtractor(api_key="")
        texto = "Texto curto de teste"

        resultado = extractor._otimizar_texto(texto, max_chars=1000)
        assert resultado == texto

    def test_texto_exatamente_no_limite(self):
        """Texto exatamente no limite não deve ser truncado."""
        extractor = LLMExtractor(api_key="")
        texto = "A" * 1000

        resultado = extractor._otimizar_texto(texto, max_chars=1000)
        assert resultado == texto

    def test_texto_longo_trunca(self):
        """Texto longo deve ser truncado."""
        extractor = LLMExtractor(api_key="")
        texto = "A" * 10000  # 10k caracteres

        resultado = extractor._otimizar_texto(texto, max_chars=1000)
        assert len(resultado) < len(texto)

    def test_texto_truncado_contem_marcador(self):
        """Texto truncado deve conter marcador de omissão."""
        extractor = LLMExtractor(api_key="")
        texto = "A" * 10000

        resultado = extractor._otimizar_texto(texto, max_chars=1000)
        assert "omitido" in resultado

    def test_texto_truncado_preserva_inicio_e_fim(self):
        """Texto truncado deve preservar início e fim."""
        extractor = LLMExtractor(api_key="")
        texto = "INICIO" + "X" * 10000 + "FIM"

        resultado = extractor._otimizar_texto(texto, max_chars=1000)
        assert "INICIO" in resultado
        assert "FIM" in resultado


# =============================================================================
# TESTES DE CONVERSÃO
# =============================================================================

class TestLLMExtractorConversao:
    """Testes de conversão de JSON para LoteExtraido."""

    def test_conversao_lote_completo(self):
        """Deve converter lote com todos os campos."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": "01",
                "descricao": "FIAT STRADA 2015",
                "placa": "ABC1234",
                "chassi": "9BD178226F5123456",
                "renavam": "12345678901",
                "marca": "FIAT",
                "modelo": "STRADA",
                "ano": 2015,
                "valor": 25000.00
            }]
        }

        lotes = extractor._converter_para_lotes(dados)

        assert len(lotes) == 1
        assert lotes[0].numero_lote == "01"
        assert lotes[0].placa == "ABC1234"
        assert lotes[0].chassi == "9BD178226F5123456"
        assert lotes[0].marca == "FIAT"

    def test_conversao_lote_minimo(self):
        """Deve converter lote com campos mínimos."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": "1",
                "descricao": "Veículo usado para venda"
            }]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 1
        assert lotes[0].numero_lote == "1"

    def test_conversao_ignora_lote_sem_numero(self):
        """Deve ignorar lotes sem número."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [
                {"numero": "", "descricao": "Sem número"},
                {"numero": "1", "descricao": "Com número válido"}
            ]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 1
        assert lotes[0].numero_lote == "1"

    def test_conversao_ignora_lote_descricao_curta(self):
        """Deve ignorar lotes com descrição muito curta."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [
                {"numero": "1", "descricao": "AB"},  # Muito curta (< 5)
                {"numero": "2", "descricao": "Descrição válida"}
            ]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 1
        assert lotes[0].numero_lote == "2"

    def test_conversao_lista_vazia(self):
        """Deve retornar lista vazia se não houver lotes."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor._converter_para_lotes({"lotes": []})
        assert lotes == []

    def test_conversao_dados_sem_lotes(self):
        """Deve retornar lista vazia se chave lotes não existir."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor._converter_para_lotes({})
        assert lotes == []

    def test_conversao_multiplos_lotes(self):
        """Deve converter múltiplos lotes."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [
                {"numero": "01", "descricao": "Primeiro veículo"},
                {"numero": "02", "descricao": "Segundo veículo"},
                {"numero": "03", "descricao": "Terceiro veículo"}
            ]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 3


# =============================================================================
# TESTES DO MÉTODO EXTRAIR_LOTES
# =============================================================================

class TestLLMExtractorExtrairLotes:
    """Testes do método principal extrair_lotes."""

    def test_extrair_sem_cliente_retorna_vazio(self):
        """Deve retornar lista vazia se não tiver cliente."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor.extrair_lotes("texto do edital com mais de 100 caracteres para passar na validação de tamanho mínimo")
        assert lotes == []

    def test_extrair_texto_curto_retorna_vazio(self):
        """Deve retornar lista vazia se texto for muito curto."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor.extrair_lotes("curto")
        assert lotes == []

    def test_extrair_texto_vazio_retorna_vazio(self):
        """Deve retornar lista vazia se texto for vazio."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor.extrair_lotes("")
        assert lotes == []

    def test_extrair_texto_none_retorna_vazio(self):
        """Deve retornar lista vazia se texto for None."""
        extractor = LLMExtractor(api_key="")

        lotes = extractor.extrair_lotes(None)
        assert lotes == []


# =============================================================================
# TESTES DE INTEGRAÇÃO COM LOTEEXTRAIDO
# =============================================================================

class TestLLMExtractorIntegracao:
    """Testes de integração com a classe LoteExtraido."""

    def test_lote_convertido_tem_texto_fonte(self):
        """Lote convertido deve ter texto_fonte_completo preenchido."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": "01",
                "descricao": "FIAT STRADA 2015 COMPLETO"
            }]
        }

        lotes = extractor._converter_para_lotes(dados)

        assert len(lotes) == 1
        assert "LLM:" in lotes[0].texto_fonte_completo

    def test_lote_convertido_tipo_correto(self):
        """Lote convertido deve ser do tipo LoteExtraido."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": "01",
                "descricao": "Veículo para teste"
            }]
        }

        lotes = extractor._converter_para_lotes(dados)

        assert len(lotes) == 1
        assert isinstance(lotes[0], LoteExtraido)


# =============================================================================
# TESTES DE ROBUSTEZ
# =============================================================================

class TestLLMExtractorRobustez:
    """Testes de robustez e tratamento de erros."""

    def test_conversao_com_campo_invalido(self):
        """Deve ignorar campos inválidos graciosamente."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": "01",
                "descricao": "Veículo válido",
                "campo_inexistente": "valor"
            }]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 1

    def test_conversao_com_valor_tipo_errado(self):
        """Deve lidar com valores de tipo errado."""
        extractor = LLMExtractor(api_key="")

        dados = {
            "lotes": [{
                "numero": 1,  # Número em vez de string
                "descricao": "Veículo válido",
                "valor": "não é número"  # String em vez de float
            }]
        }

        lotes = extractor._converter_para_lotes(dados)
        assert len(lotes) == 1
        assert lotes[0].numero_lote == "1"
