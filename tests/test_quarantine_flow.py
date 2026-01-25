"""
Teste do Fluxo de Quarentena - EXECUTION BRIEF 1.2
==================================================
Verifica que:
1. Registro inválido gera reason_code correto
2. reason_detail é extraído da mensagem do erro
3. Estrutura do rejection_row está completa
4. Idempotência: mesmo (run_id, id_interno) não duplica
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.dataset_validator import (
    validate_record,
    RecordStatus,
    ErrorCode,
    new_run_id,
    build_rejection_row,
)


class TestQuarantineFlow:
    """Testes do fluxo de quarentena (Brief 1.2)."""

    def test_rejection_row_tem_campos_brief_1_2(self):
        """QG: rejection_row deve ter todos os campos do Brief 1.2."""
        registro = {"id_interno": "TEST-Q-001"}  # Registro incompleto
        result = validate_record(registro)
        run_id = new_run_id()

        rejection = build_rejection_row(run_id, registro, result)

        # Campos obrigatórios do Brief 1.2
        campos_obrigatorios = [
            "run_id",
            "id_interno",
            "status",  # reason_code de alto nível
            "errors",  # contém reason_code e reason_detail detalhados
            "raw_record",  # payload_original
            "normalized_record",  # payload_normalizado
        ]

        for campo in campos_obrigatorios:
            assert campo in rejection, f"Campo {campo} faltando no rejection_row"

    def test_reason_code_extraido_do_primeiro_erro(self):
        """QG: reason_code deve ser o código do primeiro erro."""
        # Registro sem data_leilao -> primeiro erro será missing_required_field
        registro = {
            "id_interno": "TEST-Q-002",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": None,  # Faltando
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-Q-002",
        }

        result = validate_record(registro)

        assert len(result.errors) > 0, "Deveria ter erros"

        # O primeiro erro deve ser sobre campo obrigatório faltando
        primeiro_erro = result.errors[0]
        assert primeiro_erro.code in (
            ErrorCode.MISSING_REQUIRED_FIELD,
            ErrorCode.INVALID_DATE_FORMAT,
        )

    def test_reason_detail_contem_mensagem_util(self):
        """QG: reason_detail deve conter mensagem explicativa."""
        registro = {
            "id_interno": "TEST-Q-003",
            "data_leilao": "15/02/2026",  # Formato errado (barra)
        }

        result = validate_record(registro)

        # Deve ter erro de formato de data
        erros_data = [e for e in result.errors if e.code == ErrorCode.INVALID_DATE_FORMAT]
        assert len(erros_data) > 0, "Deveria ter erro de formato de data"

        # Mensagem deve explicar o problema
        erro = erros_data[0]
        assert "DD-MM-YYYY" in erro.message or "hífen" in erro.message.lower() or "barra" in erro.message.lower()

    def test_status_draft_para_registro_incompleto(self):
        """QG: Registro incompleto deve ter status DRAFT ou NOT_SELLABLE."""
        registro = {
            "id_interno": "TEST-Q-004",
            "titulo": "Leilão Teste",
            # Faltam muitos campos obrigatórios
        }

        result = validate_record(registro)

        assert result.status in (RecordStatus.DRAFT, RecordStatus.NOT_SELLABLE)
        assert not result.is_valid

    def test_status_rejected_para_formato_invalido(self):
        """QG: Registro com formato inválido crítico deve ser REJECTED."""
        registro = {
            "id_interno": "TEST-Q-005",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "2026/02/15",  # Formato completamente errado
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-Q-005",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão",
            "descricao": "Descrição",
            "orgao": "Orgão",
            "n_edital": "005/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO",
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        assert result.status == RecordStatus.REJECTED

    def test_error_codes_enum_completo(self):
        """QG: ErrorCode deve ter todos os códigos do Brief 1.2."""
        codigos_obrigatorios = [
            "MISSING_REQUIRED_FIELD",
            "INVALID_DATE_FORMAT",
            "INVALID_URL",
            "REJECTED_CATEGORY",
            "EXTRACTION_ERROR",
            "UNKNOWN",
        ]

        for codigo in codigos_obrigatorios:
            assert hasattr(ErrorCode, codigo), f"ErrorCode.{codigo} não existe"

    def test_payload_original_preservado(self):
        """QG: raw_record deve preservar o registro original intacto."""
        registro_original = {
            "id_interno": "TEST-Q-006",
            "campo_extra": "valor_que_nao_deve_ser_perdido",
            "data_leilao": "15/02/2026",  # Formato errado
        }

        result = validate_record(registro_original)
        run_id = new_run_id()
        rejection = build_rejection_row(run_id, registro_original, result)

        # O raw_record deve ser o registro original
        assert rejection["raw_record"]["campo_extra"] == "valor_que_nao_deve_ser_perdido"
        assert rejection["raw_record"]["data_leilao"] == "15/02/2026"

    def test_payload_normalizado_presente(self):
        """QG: normalized_record deve estar presente mesmo com erros."""
        registro = {
            "id_interno": "TEST-Q-007",
            "pncp_url": "www.pncp.gov.br/teste",  # Será normalizado para https://
        }

        result = validate_record(registro)
        run_id = new_run_id()
        rejection = build_rejection_row(run_id, registro, result)

        # normalized_record deve existir
        assert "normalized_record" in rejection
        assert isinstance(rejection["normalized_record"], dict)


class TestIdempotenciaQuarentena:
    """Testes de idempotência específicos para quarentena."""

    def test_mesmo_run_id_mesmo_id_interno(self):
        """QG: Chave (run_id, id_interno) deve ser única."""
        registro = {"id_interno": "TEST-IDEMP-Q-001"}
        result = validate_record(registro)
        run_id = "20260126T120000Z_fixedrunid"

        row1 = build_rejection_row(run_id, registro, result)
        row2 = build_rejection_row(run_id, registro, result)

        # Mesma chave composta
        assert row1["run_id"] == row2["run_id"]
        assert row1["id_interno"] == row2["id_interno"]

        # No banco, isso seria um UPDATE, não INSERT duplicado

    def test_run_ids_diferentes_permitem_duplicacao_controlada(self):
        """QG: Runs diferentes podem ter o mesmo id_interno (reprocessamento)."""
        registro = {"id_interno": "TEST-IDEMP-Q-002"}
        result = validate_record(registro)

        run_id_1 = "20260126T120000Z_run1"
        run_id_2 = "20260126T130000Z_run2"

        row1 = build_rejection_row(run_id_1, registro, result)
        row2 = build_rejection_row(run_id_2, registro, result)

        # Runs diferentes = registros diferentes (histórico de reprocessamento)
        assert row1["run_id"] != row2["run_id"]
        assert row1["id_interno"] == row2["id_interno"]


if __name__ == "__main__":
    # Executar testes manualmente
    print("=" * 60)
    print("TESTES DO FLUXO DE QUARENTENA - BRIEF 1.2")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_class = TestQuarantineFlow()
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

    test_class_2 = TestIdempotenciaQuarentena()
    test_methods_2 = [m for m in dir(test_class_2) if m.startswith("test_")]

    for method_name in test_methods_2:
        try:
            getattr(test_class_2, method_name)()
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
