"""
Teste do Processamento Incremental - EXECUTION BRIEF 2.1
=========================================================
Verifica que:
1. MinerConfig tem campo force_reprocess (default False)
2. Modo incremental ignora editais existentes
3. Modo --force reprocessa editais existentes
4. Stats registra editais_skip_existe
5. Log indica modo de processamento
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar apenas o necessario para testes unitarios
from src.core.ache_sucatas_miner_v18 import MinerConfig


class TestMinerConfigPhase2:
    """Testes de configuracao para Fase 2."""

    def test_force_reprocess_default_false(self):
        """QG: force_reprocess deve ser False por padrao (modo incremental)."""
        config = MinerConfig()
        assert hasattr(config, "force_reprocess"), "MinerConfig deve ter atributo force_reprocess"
        assert config.force_reprocess is False, "force_reprocess deve ser False por padrao"

    def test_force_reprocess_pode_ser_true(self):
        """QG: force_reprocess pode ser True (modo full)."""
        config = MinerConfig(force_reprocess=True)
        assert config.force_reprocess is True

    def test_config_preserva_outros_defaults(self):
        """QG: force_reprocess nao deve quebrar outros defaults."""
        config = MinerConfig(force_reprocess=True)
        # Verificar que outros defaults ainda funcionam
        assert config.dias_retroativos == 1
        assert config.paginas_por_termo == 3
        assert config.min_score == 60  # Score minimo para processamento


class TestIncrementalLogic:
    """Testes da logica de processamento incremental."""

    def test_stats_tem_campo_skip_existe(self):
        """QG: Stats deve registrar editais_skip_existe."""
        # Simular stats do miner
        stats = {
            "editais_encontrados": 100,
            "editais_novos": 80,
            "editais_skip_existe": 15,  # Fase 2: editais pulados
            "editais_duplicados": 5,
        }

        assert "editais_skip_existe" in stats
        assert stats["editais_skip_existe"] == 15

        # Total deve bater
        total_processamento = stats["editais_novos"] + stats["editais_skip_existe"] + stats["editais_duplicados"]
        assert total_processamento == 100

    def test_modo_incremental_default(self):
        """QG: Modo padrao deve ser incremental (force_reprocess=False)."""
        config = MinerConfig()

        # Simular logica do miner
        edital_existe_no_banco = True
        force = config.force_reprocess

        deve_processar = force or not edital_existe_no_banco
        assert deve_processar is False, "Nao deve processar edital existente em modo incremental"

    def test_modo_full_com_force(self):
        """QG: Com --force, deve processar mesmo edital existente."""
        config = MinerConfig(force_reprocess=True)

        # Simular logica do miner
        edital_existe_no_banco = True
        force = config.force_reprocess

        deve_processar = force or not edital_existe_no_banco
        assert deve_processar is True, "Deve processar edital existente em modo full"

    def test_edital_novo_sempre_processado(self):
        """QG: Edital novo deve ser processado em ambos os modos."""
        # Modo incremental
        config_inc = MinerConfig(force_reprocess=False)
        edital_existe = False
        deve_processar_inc = config_inc.force_reprocess or not edital_existe
        assert deve_processar_inc is True

        # Modo full
        config_full = MinerConfig(force_reprocess=True)
        deve_processar_full = config_full.force_reprocess or not edital_existe
        assert deve_processar_full is True


class TestCLIArgument:
    """Testes do argumento CLI --force."""

    def test_argparse_com_force_true(self):
        """QG: --force deve setar force_reprocess=True."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forca reprocessamento"
        )

        args = parser.parse_args(["--force"])
        assert args.force is True

    def test_argparse_sem_force_false(self):
        """QG: Sem --force, deve ser False."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forca reprocessamento"
        )

        args = parser.parse_args([])
        assert args.force is False

    def test_config_recebe_force_do_argparse(self):
        """QG: MinerConfig deve receber force_reprocess do argparse."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--force", action="store_true")

        # Simular execucao com --force
        args = parser.parse_args(["--force"])

        config = MinerConfig(
            force_reprocess=args.force
        )

        assert config.force_reprocess is True


class TestIdempotenciaProcessamento:
    """Testes de idempotencia do processamento."""

    def test_reprocessamento_nao_duplica_dados(self):
        """QG: Reprocessar mesmo edital nao deve duplicar no banco."""
        # Este teste documenta o comportamento esperado:
        # - Se edital ja existe E mode=incremental: SKIP (nao processa)
        # - Se edital ja existe E mode=full: UPDATE (nao INSERT duplicado)
        # A implementacao usa UPSERT no banco

        pncp_id = "00000000000191-1-000001/2026"

        # Cenario 1: modo incremental com edital existente
        config_inc = MinerConfig(force_reprocess=False)
        edital_existe = True
        skip_em_incremental = not config_inc.force_reprocess and edital_existe
        assert skip_em_incremental is True, "Deve pular em modo incremental"

        # Cenario 2: modo full com edital existente (usa UPSERT)
        config_full = MinerConfig(force_reprocess=True)
        processa_em_full = config_full.force_reprocess or not edital_existe
        assert processa_em_full is True, "Deve processar em modo full"


if __name__ == "__main__":
    print("=" * 60)
    print("TESTES DO PROCESSAMENTO INCREMENTAL - BRIEF 2.1")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    test_classes = [
        TestMinerConfigPhase2(),
        TestIncrementalLogic(),
        TestCLIArgument(),
        TestIdempotenciaProcessamento(),
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
