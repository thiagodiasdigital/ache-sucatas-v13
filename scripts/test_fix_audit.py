"""
Teste das Correções da Auditoria Forense
==========================================
Verifica se os patches aplicados funcionam corretamente.

Data: 2026-01-29
"""

import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.dataset_validator import (
    validate_record,
    REQUIRED_FIELDS,
    SELLABLE_REQUIRED_FIELDS,
    RecordStatus,
)
from src.core.ache_sucatas_miner_v18 import extrair_tipo_leilao_pdf


def test_n_edital_removed_from_required():
    """Verifica que n_edital foi removido de REQUIRED_FIELDS."""
    print("=" * 60)
    print("TESTE 1: n_edital removido de REQUIRED_FIELDS")
    print("=" * 60)

    assert "n_edital" not in REQUIRED_FIELDS, "n_edital ainda está em REQUIRED_FIELDS!"
    print("✓ n_edital NÃO está em REQUIRED_FIELDS")

    assert "n_edital" not in SELLABLE_REQUIRED_FIELDS, "n_edital ainda está em SELLABLE_REQUIRED_FIELDS!"
    print("✓ n_edital NÃO está em SELLABLE_REQUIRED_FIELDS")

    print("PASSOU!\n")


def test_extrair_tipo_leilao_pdf():
    """Verifica que a função de extração funciona com acentos."""
    print("=" * 60)
    print("TESTE 2: extrair_tipo_leilao_pdf com acentos")
    print("=" * 60)

    # Teste com texto que contém "leilão eletrônico" (com acentos)
    texto1 = "Este é um leilão eletrônico para alienação de bens."
    resultado1 = extrair_tipo_leilao_pdf(texto1)
    print(f"Texto: '{texto1[:50]}...'")
    print(f"Resultado: '{resultado1}'")
    assert resultado1 == "Eletronico", f"Esperado 'Eletronico', obtido '{resultado1}'"
    print("✓ Extração de 'leilão eletrônico' funcionou!")

    # Teste com texto que contém "leilao eletronico" (sem acentos)
    texto2 = "Este é um leilao eletronico para alienação de bens."
    resultado2 = extrair_tipo_leilao_pdf(texto2)
    print(f"Texto: '{texto2[:50]}...'")
    print(f"Resultado: '{resultado2}'")
    assert resultado2 == "Eletronico", f"Esperado 'Eletronico', obtido '{resultado2}'"
    print("✓ Extração de 'leilao eletronico' funcionou!")

    # Teste com texto que contém "presencial"
    texto3 = "Leilão presencial na sede da prefeitura."
    resultado3 = extrair_tipo_leilao_pdf(texto3)
    print(f"Texto: '{texto3[:50]}...'")
    print(f"Resultado: '{resultado3}'")
    assert resultado3 == "Presencial", f"Esperado 'Presencial', obtido '{resultado3}'"
    print("✓ Extração de 'presencial' funcionou!")

    # Teste híbrido
    texto4 = "Leilão eletrônico com lance presencial na sede."
    resultado4 = extrair_tipo_leilao_pdf(texto4)
    print(f"Texto: '{texto4[:50]}...'")
    print(f"Resultado: '{resultado4}'")
    assert resultado4 == "Hibrido", f"Esperado 'Hibrido', obtido '{resultado4}'"
    print("✓ Extração de 'Híbrido' funcionou!")

    # Teste com "online"
    texto5 = "Processo será realizado online pela plataforma."
    resultado5 = extrair_tipo_leilao_pdf(texto5)
    print(f"Texto: '{texto5[:50]}...'")
    print(f"Resultado: '{resultado5}'")
    assert resultado5 == "Eletronico", f"Esperado 'Eletronico', obtido '{resultado5}'"
    print("✓ Extração de 'online' funcionou!")

    print("PASSOU!\n")


def test_registro_sem_n_edital_valido():
    """Verifica que registro sem n_edital pode ser válido."""
    print("=" * 60)
    print("TESTE 3: Registro sem n_edital pode ser válido")
    print("=" * 60)

    registro_completo = {
        "id_interno": "TEST-001",
        "municipio": "São Paulo",
        "uf": "SP",
        "data_leilao": "30-01-2026",
        "pncp_url": "https://pncp.gov.br/app/editais/test",
        "data_atualizacao": "29-01-2026",
        "titulo": "Alienação de veículos",
        "descricao": "Leilão de veículos usados",
        "orgao": "Prefeitura de São Paulo",
        # "n_edital": None,  # AUSENTE PROPOSITALMENTE
        "objeto_resumido": "Veículos diversos",
        "tags": "VEICULO, SUCATA",
        "valor_estimado": 50000.00,
        "tipo_leilao": "Eletronico",
        "data_publicacao": "28-01-2026",
    }

    resultado = validate_record(registro_completo)

    print(f"Status: {resultado.status.value}")
    print(f"Erros: {len(resultado.errors)}")
    for err in resultado.errors:
        print(f"  - {err.code.value}: {err.field} - {err.message}")

    # Deve ser VALID porque n_edital não é mais obrigatório
    assert resultado.status == RecordStatus.VALID, \
        f"Registro sem n_edital deveria ser VALID, mas foi {resultado.status.value}"

    print("✓ Registro sem n_edital foi marcado como VALID!")
    print("PASSOU!\n")


def test_registro_sem_tipo_leilao_draft():
    """Verifica que registro sem tipo_leilao vai para draft/not_sellable."""
    print("=" * 60)
    print("TESTE 4: Registro sem tipo_leilao vai para quarentena")
    print("=" * 60)

    registro_sem_tipo = {
        "id_interno": "TEST-002",
        "municipio": "São Paulo",
        "uf": "SP",
        "data_leilao": "30-01-2026",
        "pncp_url": "https://pncp.gov.br/app/editais/test2",
        "data_atualizacao": "29-01-2026",
        "titulo": "Alienação de veículos",
        "descricao": "Leilão de veículos usados",
        "orgao": "Prefeitura de São Paulo",
        "objeto_resumido": "Veículos diversos",
        "tags": "VEICULO",
        "valor_estimado": 50000.00,
        "tipo_leilao": "",  # VAZIO
        "data_publicacao": "28-01-2026",
    }

    resultado = validate_record(registro_sem_tipo)

    print(f"Status: {resultado.status.value}")
    print(f"Erros: {len(resultado.errors)}")
    for err in resultado.errors:
        print(f"  - {err.code.value}: {err.field} - {err.message}")

    # Deve ir para quarentena porque tipo_leilao é obrigatório
    assert resultado.status in [RecordStatus.DRAFT, RecordStatus.NOT_SELLABLE], \
        f"Registro sem tipo_leilao deveria ir para quarentena, mas foi {resultado.status.value}"

    print(f"✓ Registro sem tipo_leilao foi para {resultado.status.value} (quarentena)")
    print("PASSOU!\n")


def main():
    print("\n" + "=" * 60)
    print("TESTE DAS CORREÇÕES DA AUDITORIA FORENSE")
    print("Data: 2026-01-29")
    print("=" * 60 + "\n")

    tests = [
        test_n_edital_removed_from_required,
        test_extrair_tipo_leilao_pdf,
        test_registro_sem_n_edital_valido,
        test_registro_sem_tipo_leilao_draft,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FALHOU: {e}")
            failed += 1
        except Exception as e:
            print(f"ERRO: {e}")
            failed += 1

    print("=" * 60)
    print(f"RESULTADO: {passed} passou, {failed} falhou")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
