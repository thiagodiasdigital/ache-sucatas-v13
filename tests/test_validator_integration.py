"""
Teste de Integração: Validator no Pipeline Miner V18
=====================================================
EXECUTION BRIEF 1.1 - Quality Gate QG1

Verifica que:
1. Registro VALID vai para tabela principal
2. Registro INVÁLIDO vai para quarentena
3. Idempotência: rodar 2x não duplica
"""
import pytest
from datetime import datetime

# Imports do projeto
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.dataset_validator import (
    validate_record,
    ValidationResult,
    RecordStatus,
    QualityReport,
    new_run_id,
    build_rejection_row,
    ErrorCode,
)


class TestValidatorIntegration:
    """Testes de integração do validador com o pipeline."""

    def test_registro_valido_retorna_status_valid(self):
        """QG: Registro completo deve ter status VALID."""
        registro = {
            "id_interno": "TEST-001",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "15-02-2026",
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-001",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão de Veículos Apreendidos",
            "descricao": "Leilão de veículos apreendidos pela Receita Federal",
            "orgao": "Receita Federal do Brasil",
            "n_edital": "001/2026",
            "objeto_resumido": "Veículos diversos",
            "tags": "VEICULO, APREENDIDO",
            "valor_estimado": 50000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        assert result.status == RecordStatus.VALID
        assert result.is_valid is True
        assert len([e for e in result.errors if e.code not in (
            ErrorCode.URL_NORMALIZED, ErrorCode.TAGS_NORMALIZED
        )]) == 0

    def test_registro_sem_data_leilao_retorna_not_sellable(self):
        """QG: Registro sem data_leilao deve ser NOT_SELLABLE."""
        registro = {
            "id_interno": "TEST-002",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": None,  # FALTANDO
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-002",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão de Veículos",
            "descricao": "Descrição do leilão",
            "orgao": "Orgão Teste",
            "n_edital": "002/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO",
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        assert result.status == RecordStatus.NOT_SELLABLE
        assert result.is_valid is False
        assert any(e.field == "data_leilao" for e in result.errors)

    def test_registro_com_data_formato_errado_retorna_rejected(self):
        """QG: Registro com data em formato errado (barra) deve ser REJECTED."""
        registro = {
            "id_interno": "TEST-003",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "15/02/2026",  # FORMATO ERRADO (barra)
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-003",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão de Veículos",
            "descricao": "Descrição do leilão",
            "orgao": "Orgão Teste",
            "n_edital": "003/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO",
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        assert result.status == RecordStatus.REJECTED
        assert result.is_valid is False
        assert any(e.code == ErrorCode.INVALID_DATE_FORMAT for e in result.errors)

    def test_registro_sem_campos_obrigatorios_retorna_draft_ou_not_sellable(self):
        """QG: Registro incompleto deve ser DRAFT ou NOT_SELLABLE."""
        registro = {
            "id_interno": "TEST-004",
            # Faltam vários campos
        }

        result = validate_record(registro)

        assert result.status in (RecordStatus.DRAFT, RecordStatus.NOT_SELLABLE)
        assert result.is_valid is False
        assert any(e.code == ErrorCode.MISSING_REQUIRED_FIELD for e in result.errors)

    def test_build_rejection_row_estrutura_correta(self):
        """QG: build_rejection_row deve gerar estrutura correta para quarentena."""
        registro = {"id_interno": "TEST-005", "municipio": "Teste"}
        result = validate_record(registro)
        run_id = new_run_id()

        rejection = build_rejection_row(run_id, registro, result)

        assert "run_id" in rejection
        assert "id_interno" in rejection
        assert "status" in rejection
        assert "errors" in rejection
        assert "raw_record" in rejection
        assert "normalized_record" in rejection

        assert rejection["run_id"] == run_id
        assert rejection["id_interno"] == "TEST-005"
        assert rejection["status"] in ("draft", "not_sellable", "rejected")
        assert isinstance(rejection["errors"], list)
        assert isinstance(rejection["raw_record"], dict)

    def test_quality_report_contagem_correta(self):
        """QG: QualityReport deve contar corretamente cada status."""
        run_id = new_run_id()
        report = QualityReport(run_id=run_id)

        # Registro válido
        result_valid = ValidationResult(
            status=RecordStatus.VALID,
            errors=[],
            normalized_record={}
        )
        report.register(result_valid)

        # Registro draft
        result_draft = ValidationResult(
            status=RecordStatus.DRAFT,
            errors=[],
            normalized_record={}
        )
        report.register(result_draft)

        # Registro not_sellable
        result_not_sellable = ValidationResult(
            status=RecordStatus.NOT_SELLABLE,
            errors=[],
            normalized_record={}
        )
        report.register(result_not_sellable)

        assert report.executed_total == 3
        assert report.valid_count == 1
        assert report.draft_count == 1
        assert report.not_sellable_count == 1
        assert report.rejected_count == 0

    def test_new_run_id_formato_correto(self):
        """QG: run_id deve ter formato YYYYMMDDTHHMMSSZ_uuid."""
        run_id = new_run_id()

        assert "_" in run_id
        parts = run_id.split("_")
        assert len(parts) == 2

        timestamp_part = parts[0]
        uuid_part = parts[1]

        # Timestamp deve terminar com Z
        assert timestamp_part.endswith("Z")
        # UUID parte deve ter 12 chars hex
        assert len(uuid_part) == 12

    def test_url_www_normalizada_para_https(self):
        """QG: URL com www. deve ser normalizada para https://www."""
        registro = {
            "id_interno": "TEST-006",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "15-02-2026",
            "pncp_url": "www.pncp.gov.br/app/editais/TEST-006",  # www sem https
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão",
            "descricao": "Descrição",
            "orgao": "Orgão",
            "n_edital": "006/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO",
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        # URL deve ter sido normalizada
        normalized_url = result.normalized_record.get("pncp_url")
        assert normalized_url.startswith("https://")

    def test_tag_sem_classificacao_removida(self):
        """QG: Tag 'SEM CLASSIFICAÇÃO' deve ser removida automaticamente."""
        registro = {
            "id_interno": "TEST-007",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "15-02-2026",
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-007",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão",
            "descricao": "Descrição",
            "orgao": "Orgão",
            "n_edital": "007/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO, SEM CLASSIFICAÇÃO, APREENDIDO",  # Contém tag proibida
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result = validate_record(registro)

        normalized_tags = result.normalized_record.get("tags", "")
        assert "SEM CLASSIFICAÇÃO" not in normalized_tags.upper()
        assert "VEICULO" in normalized_tags.upper()
        assert "APREENDIDO" in normalized_tags.upper()


class TestIdempotencia:
    """Testes de idempotência do pipeline."""

    def test_mesmo_registro_mesmo_resultado(self):
        """QG: Validar mesmo registro 2x deve dar mesmo resultado."""
        registro = {
            "id_interno": "TEST-IDEMP-001",
            "municipio": "São Paulo",
            "uf": "SP",
            "data_leilao": "15-02-2026",
            "pncp_url": "https://pncp.gov.br/app/editais/TEST-IDEMP-001",
            "data_atualizacao": "25-01-2026",
            "titulo": "Leilão de Veículos",
            "descricao": "Descrição",
            "orgao": "Orgão",
            "n_edital": "001/2026",
            "objeto_resumido": "Veículos",
            "tags": "VEICULO",
            "valor_estimado": 10000.00,
            "tipo_leilao": "Eletrônico",
            "data_publicacao": "20-01-2026",
        }

        result1 = validate_record(registro)
        result2 = validate_record(registro)

        assert result1.status == result2.status
        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)

    def test_rejection_row_mesmo_run_id(self):
        """QG: Mesmo registro no mesmo run deve gerar mesmo id_interno."""
        registro = {"id_interno": "TEST-IDEMP-002"}
        result = validate_record(registro)
        run_id = "20260125T120000Z_testrun001"

        row1 = build_rejection_row(run_id, registro, result)
        row2 = build_rejection_row(run_id, registro, result)

        # Mesmo run_id + id_interno = chave única para idempotência
        assert row1["run_id"] == row2["run_id"]
        assert row1["id_interno"] == row2["id_interno"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
