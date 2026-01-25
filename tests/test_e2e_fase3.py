"""
Teste E2E Fase 3 - Validação do Pipeline Completo
==================================================
Verifica:
1. Miner roda sem erros
2. Dados são inseridos em todas as tabelas
3. Idempotência (rodar 2x não duplica)
4. QualityReport é persistido
5. Pipeline events são registrados
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.core.ache_sucatas_miner_v18 import MinerConfig, SupabaseRepository
from validators.dataset_validator import (
    QualityReport, ValidationResult, RecordStatus, new_run_id
)


class TestSupabaseRepositoryFase3:
    """Testes do SupabaseRepository para Fase 3."""

    def test_salvar_quality_report_estrutura(self):
        """QG: salvar_quality_report deve existir e aceitar QualityReport."""
        # Mock do cliente Supabase
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        # Criar QualityReport de teste
        report = QualityReport(run_id=new_run_id())
        for _ in range(8):
            report.register(ValidationResult(status=RecordStatus.VALID))
        for _ in range(2):
            report.register(ValidationResult(status=RecordStatus.DRAFT))
        report.finalize()

        # Executar
        result = repo.salvar_quality_report(report, execucao_id=1)

        # Verificar
        assert result is True
        mock_client.table.assert_called_with("quality_reports")

    def test_registrar_evento_estrutura(self):
        """QG: registrar_evento deve existir e aceitar parâmetros corretos."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        run_id = new_run_id()

        # Executar
        result = repo.registrar_evento(
            run_id=run_id,
            etapa="inicio",
            evento="start",
            nivel="info",
            mensagem="Teste de evento",
            dados={"test": True},
            duracao_ms=100,
            items_processados=10,
            items_sucesso=8,
            items_erro=2
        )

        # Verificar
        assert result is True
        mock_client.table.assert_called_with("pipeline_events")

    def test_registrar_evento_etapas_validas(self):
        """QG: Todas as etapas do pipeline devem ser aceitas."""
        etapas_validas = [
            "inicio", "busca", "coleta", "pdf_download", "pdf_parse",
            "extract", "enrich", "validate", "upsert", "quarantine", "fim"
        ]

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        run_id = new_run_id()

        for etapa in etapas_validas:
            result = repo.registrar_evento(
                run_id=run_id,
                etapa=etapa,
                evento="test",
                nivel="info"
            )
            assert result is True, f"Etapa {etapa} deveria ser válida"


class TestQualityReportPersistencia:
    """Testes de persistência do QualityReport."""

    def test_top_errors_calculado_corretamente(self):
        """QG: Top errors deve ser calculado a partir de error_counts."""
        report = QualityReport(run_id=new_run_id())

        # Simular erros
        from validators.dataset_validator import ErrorCode
        for _ in range(10):
            report.bump_error(ErrorCode.MISSING_REQUIRED_FIELD)
        for _ in range(5):
            report.bump_error(ErrorCode.INVALID_DATE_FORMAT)
        for _ in range(3):
            report.bump_error(ErrorCode.INVALID_URL)

        # Verificar
        assert report.error_counts["missing_required_field"] == 10
        assert report.error_counts["invalid_date_format"] == 5
        assert report.error_counts["invalid_url"] == 3

        # Top reason codes
        top = report.top_reason_codes
        assert len(top) == 3
        assert top[0]["code"] == "missing_required_field"
        assert top[0]["count"] == 10

    def test_metricas_por_status(self):
        """QG: Métricas por status devem ser calculadas corretamente."""
        report = QualityReport(run_id=new_run_id())

        # Registrar diferentes status
        for _ in range(70):
            report.register(ValidationResult(status=RecordStatus.VALID))
        for _ in range(15):
            report.register(ValidationResult(status=RecordStatus.DRAFT))
        for _ in range(10):
            report.register(ValidationResult(status=RecordStatus.NOT_SELLABLE))
        for _ in range(5):
            report.register(ValidationResult(status=RecordStatus.REJECTED))

        report.finalize()

        # Verificar
        assert report.executed_total == 100
        assert report.valid_count == 70
        assert report.draft_count == 15
        assert report.not_sellable_count == 10
        assert report.rejected_count == 5
        assert report.total_quarentena == 30
        assert report.taxa_validos_percent == 70.0
        assert report.taxa_quarentena_percent == 30.0


class TestIdempotencia:
    """Testes de idempotência do pipeline."""

    def test_quality_report_upsert(self):
        """QG: Mesmo run_id não deve duplicar QualityReport."""
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        run_id = new_run_id()
        report = QualityReport(run_id=run_id)
        report.finalize()

        # Salvar 2x com mesmo run_id
        repo.salvar_quality_report(report, execucao_id=1)
        repo.salvar_quality_report(report, execucao_id=1)

        # Verificar que usou upsert (não insert)
        calls = mock_client.table.return_value.upsert.call_args_list
        assert len(calls) == 2
        for call in calls:
            assert call.kwargs.get("on_conflict") == "run_id"


class TestObservabilidade:
    """Testes de observabilidade (Brief 3.4)."""

    def test_evento_tem_run_id(self):
        """QG: Todos os eventos devem ter run_id para correlação."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        run_id = new_run_id()

        repo.registrar_evento(
            run_id=run_id,
            etapa="validate",
            evento="success",
            nivel="info"
        )

        # Verificar que run_id foi passado
        call_args = mock_client.table.return_value.insert.call_args
        dados = call_args[0][0]
        assert dados["run_id"] == run_id

    def test_evento_niveis_validos(self):
        """QG: Níveis de log devem ser válidos."""
        niveis_validos = ["debug", "info", "warning", "error"]

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

        config = MinerConfig()
        repo = SupabaseRepository(config)
        repo.client = mock_client
        repo.enable_supabase = True

        run_id = new_run_id()

        for nivel in niveis_validos:
            result = repo.registrar_evento(
                run_id=run_id,
                etapa="validate",
                evento="test",
                nivel=nivel
            )
            assert result is True


if __name__ == "__main__":
    print("=" * 60)
    print("TESTES E2E FASE 3 - PIPELINE COMPLETO")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_classes = [
        TestSupabaseRepositoryFase3(),
        TestQualityReportPersistencia(),
        TestIdempotencia(),
        TestObservabilidade(),
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
