"""
Teste do Relatório de Qualidade - EXECUTION BRIEF 1.3
======================================================
Verifica que:
1. QualityReport tem todos os campos do Brief 1.3
2. Taxas são calculadas corretamente
3. top_reason_codes está ordenado por frequência
4. to_json() gera JSON válido com estrutura correta
5. finalize() calcula duração corretamente
"""
import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.dataset_validator import (
    QualityReport,
    ValidationResult,
    RecordStatus,
    ValidationError,
    ErrorCode,
    new_run_id,
)


class TestQualityReportBrief13:
    """Testes do QualityReport conforme Brief 1.3."""

    def test_campos_obrigatorios_brief_1_3(self):
        """QG: to_dict() deve ter todos os campos do Brief 1.3."""
        report = QualityReport(run_id=new_run_id())
        report.finalize()
        data = report.to_dict()

        campos_obrigatorios = [
            "run_id",
            "started_at",
            "finished_at",
            "duration_seconds",
            "total_processados",
            "total_validos",
            "total_quarentena",
            "taxa_validos_percent",
            "taxa_quarentena_percent",
            "top_reason_codes",
        ]

        for campo in campos_obrigatorios:
            assert campo in data, f"Campo {campo} faltando no to_dict()"

    def test_taxa_validos_calculada_corretamente(self):
        """QG: taxa_validos_percent deve ser calculada corretamente."""
        report = QualityReport(run_id="test-taxa")

        # Simular 10 registros: 8 válidos, 2 quarentena
        for _ in range(8):
            report.register(ValidationResult(status=RecordStatus.VALID))
        for _ in range(2):
            report.register(ValidationResult(status=RecordStatus.DRAFT))

        assert report.executed_total == 10
        assert report.valid_count == 8
        assert report.taxa_validos_percent == 80.0

    def test_taxa_quarentena_calculada_corretamente(self):
        """QG: taxa_quarentena_percent deve ser calculada corretamente."""
        report = QualityReport(run_id="test-quarentena")

        # Simular 20 registros: 15 válidos, 5 quarentena
        for _ in range(15):
            report.register(ValidationResult(status=RecordStatus.VALID))
        for _ in range(3):
            report.register(ValidationResult(status=RecordStatus.DRAFT))
        for _ in range(2):
            report.register(ValidationResult(status=RecordStatus.NOT_SELLABLE))

        assert report.executed_total == 20
        assert report.total_quarentena == 5
        assert report.taxa_quarentena_percent == 25.0

    def test_top_reason_codes_ordenado_por_frequencia(self):
        """QG: top_reason_codes deve estar ordenado por frequência (maior primeiro)."""
        report = QualityReport(run_id="test-top-reasons")

        # Criar erros com diferentes frequências
        errors_missing = [ValidationError(
            code=ErrorCode.MISSING_REQUIRED_FIELD,
            field="test",
            message="Campo faltando"
        )]
        errors_date = [ValidationError(
            code=ErrorCode.INVALID_DATE_FORMAT,
            field="data",
            message="Data inválida"
        )]
        errors_url = [ValidationError(
            code=ErrorCode.INVALID_URL,
            field="url",
            message="URL inválida"
        )]

        # MISSING: 5x, DATE: 3x, URL: 1x
        for _ in range(5):
            report.register(ValidationResult(
                status=RecordStatus.DRAFT,
                errors=errors_missing
            ))
        for _ in range(3):
            report.register(ValidationResult(
                status=RecordStatus.REJECTED,
                errors=errors_date
            ))
        report.register(ValidationResult(
            status=RecordStatus.REJECTED,
            errors=errors_url
        ))

        top = report.top_reason_codes

        assert len(top) == 3
        assert top[0]["code"] == "missing_required_field"
        assert top[0]["count"] == 5
        assert top[1]["code"] == "invalid_date_format"
        assert top[1]["count"] == 3
        assert top[2]["code"] == "invalid_url"
        assert top[2]["count"] == 1

    def test_finalize_calcula_duracao(self):
        """QG: finalize() deve calcular duration_seconds."""
        report = QualityReport(run_id="test-duracao")

        # Simular processamento de 0.5 segundos
        time.sleep(0.5)
        report.finalize()

        assert report.finished_at is not None
        assert report.duration_seconds >= 0.4  # Margem de tolerância

    def test_to_json_gera_json_valido(self):
        """QG: to_json() deve gerar JSON parseável."""
        report = QualityReport(run_id="test-json")
        report.register(ValidationResult(status=RecordStatus.VALID))
        report.register(ValidationResult(status=RecordStatus.DRAFT))
        report.finalize()

        json_str = report.to_json()

        # Deve ser parseável
        data = json.loads(json_str)

        # Deve ter estrutura correta
        assert data["run_id"] == "test-json"
        assert data["total_processados"] == 2
        assert data["total_validos"] == 1

    def test_taxa_zero_quando_nenhum_processado(self):
        """QG: Taxas devem ser 0 quando nenhum registro processado."""
        report = QualityReport(run_id="test-vazio")

        assert report.executed_total == 0
        assert report.taxa_validos_percent == 0.0
        assert report.taxa_quarentena_percent == 0.0

    def test_top_reason_codes_limita_a_10(self):
        """QG: top_reason_codes deve retornar no máximo 10 itens."""
        report = QualityReport(run_id="test-limite")

        # Simular 15 tipos diferentes de erro
        for i in range(15):
            # Hackear para ter muitos códigos diferentes
            report.error_counts[f"error_type_{i:02d}"] = i + 1

        top = report.top_reason_codes
        assert len(top) <= 10

    def test_started_at_preenchido_automaticamente(self):
        """QG: started_at deve ser preenchido na criação."""
        report = QualityReport(run_id="test-start")

        assert report.started_at is not None
        assert "T" in report.started_at  # Formato ISO

    def test_total_quarentena_soma_todos_nao_validos(self):
        """QG: total_quarentena = draft + not_sellable + rejected."""
        report = QualityReport(run_id="test-soma")

        report.register(ValidationResult(status=RecordStatus.DRAFT))
        report.register(ValidationResult(status=RecordStatus.DRAFT))
        report.register(ValidationResult(status=RecordStatus.NOT_SELLABLE))
        report.register(ValidationResult(status=RecordStatus.REJECTED))

        assert report.draft_count == 2
        assert report.not_sellable_count == 1
        assert report.rejected_count == 1
        assert report.total_quarentena == 4


if __name__ == "__main__":
    print("=" * 60)
    print("TESTES DO RELATORIO DE QUALIDADE - BRIEF 1.3")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_class = TestQualityReportBrief13()
    test_methods = [m for m in dir(test_class) if m.startswith("test_")]

    for method_name in test_methods:
        try:
            getattr(test_class, method_name)()
            print(f"[PASS] {method_name}")
            tests_passed += 1
        except AssertionError as e:
            print(f"[FAIL] {method_name}: {e}")
            tests_failed += 1
        except Exception as e:
            print(f"[ERROR] {method_name}: {e}")
            tests_failed += 1

    print("=" * 60)
    print(f"RESULTADO: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
