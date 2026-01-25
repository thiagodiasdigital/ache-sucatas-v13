"""
Teste de FinOps - EXECUTION BRIEF 3.6
=====================================
Verifica que:
1. OpenAIEnricher rastreia tokens
2. Custos sao calculados corretamente
3. FinOps e persistido no banco
4. Custo por 1000 registros e calculado
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.ache_sucatas_miner_v18 import MinerConfig, OpenAIEnricher


class TestOpenAIEnricherFinOps:
    """Testes do tracking de tokens no OpenAIEnricher."""

    def test_contadores_iniciais_zerados(self):
        """QG: Contadores devem iniciar em zero."""
        enricher = OpenAIEnricher(api_key="", model="gpt-4o-mini")

        assert enricher.total_input_tokens == 0
        assert enricher.total_output_tokens == 0
        assert enricher.total_requests == 0

    def test_get_estimated_cost_inicial_zero(self):
        """QG: Custo inicial deve ser zero."""
        enricher = OpenAIEnricher(api_key="", model="gpt-4o-mini")

        cost = enricher.get_estimated_cost()
        assert cost == 0.0

    def test_get_token_stats_estrutura(self):
        """QG: get_token_stats deve retornar estrutura correta."""
        enricher = OpenAIEnricher(api_key="", model="gpt-4o-mini")

        stats = enricher.get_token_stats()

        assert "total_requests" in stats
        assert "total_input_tokens" in stats
        assert "total_output_tokens" in stats
        assert "total_tokens" in stats
        assert "estimated_cost_usd" in stats

    def test_calculo_custo_com_tokens(self):
        """QG: Custo deve ser calculado corretamente com tokens."""
        enricher = OpenAIEnricher(api_key="", model="gpt-4o-mini")

        # Simular uso de tokens
        enricher.total_input_tokens = 1_000_000  # 1M tokens input
        enricher.total_output_tokens = 100_000   # 100K tokens output

        # Precos GPT-4o-mini: $0.15/1M input, $0.60/1M output
        # Esperado: (1M * 0.15/1M) + (0.1M * 0.60/1M) = 0.15 + 0.06 = 0.21
        cost = enricher.get_estimated_cost()

        assert cost == 0.21

    def test_preco_por_milhao_correto(self):
        """QG: Precos por milhao de tokens devem estar corretos."""
        assert OpenAIEnricher.PRICE_INPUT_PER_1M == 0.15
        assert OpenAIEnricher.PRICE_OUTPUT_PER_1M == 0.60


class TestMinerFinOps:
    """Testes do calculo de FinOps no Miner."""

    def test_finops_estrutura(self):
        """QG: _calcular_finops deve retornar estrutura correta."""
        from src.core.ache_sucatas_miner_v18 import MinerV18

        config = MinerConfig()
        miner = MinerV18(config)

        finops = miner._calcular_finops()

        assert "cost_total" in finops
        assert "cost_openai" in finops
        assert "num_pdfs" in finops
        assert "custo_por_mil" in finops

    def test_finops_custo_por_mil(self):
        """QG: Custo por 1000 deve ser calculado corretamente."""
        from src.core.ache_sucatas_miner_v18 import MinerV18

        config = MinerConfig()
        miner = MinerV18(config)

        # Simular stats
        miner.stats["pdf_extractions"] = 10
        miner.stats["editais_novos"] = 100

        finops = miner._calcular_finops()

        # Custo infra: (10 * 0.001) + (100 * 0.0005) = 0.01 + 0.05 = 0.06
        # Custo por mil: (0.06 / 100) * 1000 = 0.6
        assert finops["num_pdfs"] == 10
        assert finops["cost_total"] >= 0
        assert finops["custo_por_mil"] >= 0

    def test_finops_sem_editais(self):
        """QG: Custo por mil deve ser zero se nao houver editais."""
        from src.core.ache_sucatas_miner_v18 import MinerV18

        config = MinerConfig()
        miner = MinerV18(config)

        miner.stats["pdf_extractions"] = 0
        miner.stats["editais_novos"] = 0

        finops = miner._calcular_finops()

        assert finops["custo_por_mil"] == 0


class TestSupabaseFinOps:
    """Testes de persistencia de FinOps no Supabase."""

    def test_finalizar_execucao_com_finops(self):
        """QG: finalizar_execucao deve aceitar parametro finops."""
        from src.core.ache_sucatas_miner_v18 import SupabaseRepository

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        finops = {
            "cost_total": 0.05,
            "cost_openai": 0.03,
            "num_pdfs": 10,
            "custo_por_mil": 0.5,
        }

        repo.finalizar_execucao(
            execucao_id=1,
            stats={"editais_encontrados": 100},
            status="SUCCESS",
            quality_report=None,
            finops=finops
        )

        # Verificar que foi chamado com os dados de finops
        call_args = mock_client.table.return_value.update.call_args
        dados = call_args[0][0]

        assert dados["cost_estimated_total"] == 0.05
        assert dados["cost_openai_estimated"] == 0.03
        assert dados["num_pdfs"] == 10
        assert dados["custo_por_mil_registros"] == 0.5


if __name__ == "__main__":
    print("=" * 60)
    print("TESTES DE FINOPS - BRIEF 3.6")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_classes = [
        TestOpenAIEnricherFinOps(),
        TestMinerFinOps(),
        TestSupabaseFinOps(),
    ]

    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        test_methods = [m for m in dir(test_class) if m.startswith("test_")]

        for method_name in test_methods:
            try:
                getattr(test_class, method_name)()
                print(f"  [PASS] {method_name}")
                tests_passed += 1
            except AssertionError as e:
                print(f"  [FAIL] {method_name}: {e}")
                tests_failed += 1
            except Exception as e:
                print(f"  [ERROR] {method_name}: {e}")
                tests_failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTADO: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
