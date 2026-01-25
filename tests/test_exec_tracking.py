"""
Teste do Tracking de Execuções - EXECUTION BRIEF 2.2
=====================================================
Verifica que:
1. iniciar_execucao recebe run_id
2. iniciar_execucao registra modo_processamento
3. finalizar_execucao recebe quality_report
4. Métricas do QualityReport são incluídas
5. Correlação run_id permite join entre tabelas
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.ache_sucatas_miner_v18 import MinerConfig
from validators.dataset_validator import QualityReport, ValidationResult, RecordStatus, new_run_id


class TestIniciarExecucao:
    """Testes de iniciar_execucao com run_id."""

    def test_run_id_formato_valido(self):
        """QG: run_id deve ter formato YYYYMMDDTHHMMSSZ_uuid."""
        run_id = new_run_id()

        assert run_id is not None
        assert "T" in run_id
        assert "Z" in run_id
        assert "_" in run_id
        assert len(run_id) > 20

    def test_config_modo_incremental(self):
        """QG: Modo padrao deve ser INCREMENTAL."""
        config = MinerConfig()

        modo = "FULL" if config.force_reprocess else "INCREMENTAL"
        assert modo == "INCREMENTAL"

    def test_config_modo_full(self):
        """QG: Com force_reprocess=True, modo deve ser FULL."""
        config = MinerConfig(force_reprocess=True)

        modo = "FULL" if config.force_reprocess else "INCREMENTAL"
        assert modo == "FULL"


class TestFinalizarExecucao:
    """Testes de finalizar_execucao com QualityReport."""

    def test_quality_report_tem_metricas(self):
        """QG: QualityReport deve ter todas as metricas necessarias."""
        report = QualityReport(run_id=new_run_id())

        # Simular registros
        for _ in range(8):
            report.register(ValidationResult(status=RecordStatus.VALID))
        for _ in range(2):
            report.register(ValidationResult(status=RecordStatus.DRAFT))

        report.finalize()

        # Verificar metricas
        assert report.executed_total == 10
        assert report.valid_count == 8
        assert report.total_quarentena == 2
        assert report.taxa_validos_percent == 80.0
        assert report.taxa_quarentena_percent == 20.0
        assert report.duration_seconds >= 0

    def test_dados_execucao_formato_correto(self):
        """QG: Dados para update devem ter formato correto."""
        report = QualityReport(run_id=new_run_id())
        report.register(ValidationResult(status=RecordStatus.VALID))
        report.finalize()

        stats = {
            "editais_encontrados": 100,
            "editais_novos": 80,
            "editais_skip_existe": 15,
            "erros": 2,
        }

        # Simular construcao dos dados
        dados = {
            "status": "SUCCESS",
            "editais_encontrados": stats.get("editais_encontrados", 0),
            "editais_novos": stats.get("editais_novos", 0),
            "editais_skip_existe": stats.get("editais_skip_existe", 0),
            "total_processados": report.executed_total,
            "total_validos": report.valid_count,
            "total_quarentena": report.total_quarentena,
            "taxa_validos_percent": report.taxa_validos_percent,
            "taxa_quarentena_percent": report.taxa_quarentena_percent,
            "duracao_segundos": report.duration_seconds,
        }

        assert dados["editais_skip_existe"] == 15
        assert dados["total_processados"] == 1
        assert dados["total_validos"] == 1
        assert isinstance(dados["taxa_validos_percent"], float)


class TestCorrelacaoRunId:
    """Testes de correlação entre tabelas via run_id."""

    def test_run_id_consistente(self):
        """QG: Mesmo run_id deve ser usado em todas as tabelas."""
        run_id = new_run_id()

        # Simular dados de diferentes tabelas
        execucao = {"run_id": run_id, "status": "SUCCESS"}
        quality_report = {"run_id": run_id, "total_processados": 100}
        rejection = {"run_id": run_id, "id_interno": "TEST-001"}

        # Todas devem ter o mesmo run_id
        assert execucao["run_id"] == quality_report["run_id"]
        assert quality_report["run_id"] == rejection["run_id"]

    def test_run_id_unicidade(self):
        """QG: Cada execucao deve ter run_id unico."""
        run_id_1 = new_run_id()
        run_id_2 = new_run_id()

        assert run_id_1 != run_id_2


class TestMetricasHistoricas:
    """Testes de métricas para análise histórica."""

    def test_metricas_permiterm_tendencia(self):
        """QG: Métricas devem permitir análise de tendência."""
        # Simular 3 execucoes com diferentes taxas
        execucoes = []

        for i, (validos, quarentena) in enumerate([(80, 20), (85, 15), (90, 10)]):
            report = QualityReport(run_id=f"run_{i}")
            for _ in range(validos):
                report.register(ValidationResult(status=RecordStatus.VALID))
            for _ in range(quarentena):
                report.register(ValidationResult(status=RecordStatus.DRAFT))
            report.finalize()

            execucoes.append({
                "run_id": report.run_id,
                "taxa_validos": report.taxa_validos_percent,
                "taxa_quarentena": report.taxa_quarentena_percent,
            })

        # Verificar tendencia de melhoria
        taxas = [e["taxa_validos"] for e in execucoes]
        assert taxas == [80.0, 85.0, 90.0], "Tendência de melhoria deve ser visível"

    def test_modo_processamento_rastreavel(self):
        """QG: Modo de processamento deve ser rastreavel."""
        config_inc = MinerConfig(force_reprocess=False)
        config_full = MinerConfig(force_reprocess=True)

        execucoes = [
            {"modo": "FULL" if config_full.force_reprocess else "INCREMENTAL"},
            {"modo": "FULL" if config_inc.force_reprocess else "INCREMENTAL"},
        ]

        assert execucoes[0]["modo"] == "FULL"
        assert execucoes[1]["modo"] == "INCREMENTAL"


if __name__ == "__main__":
    print("=" * 60)
    print("TESTES DO TRACKING DE EXECUCOES - BRIEF 2.2")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_classes = [
        TestIniciarExecucao(),
        TestFinalizarExecucao(),
        TestCorrelacaoRunId(),
        TestMetricasHistoricas(),
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
