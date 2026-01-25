"""
E2E Controlado - Fase 3
========================
Executa o miner com parâmetros controlados para validar:
1. Pipeline completo funciona
2. Dados são persistidos corretamente
3. Métricas são geradas
4. Observabilidade funciona

USO:
    python scripts/run_e2e_controlado.py

NOTA: Requer variáveis de ambiente configuradas (.env)
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def verificar_ambiente():
    """Verifica se as variáveis de ambiente estão configuradas."""
    # Aceita tanto SUPABASE_KEY quanto SUPABASE_SERVICE_KEY
    supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if supabase_key:
        os.environ["SUPABASE_KEY"] = supabase_key

    required = ["SUPABASE_URL"]
    missing = [var for var in required if not os.getenv(var)]

    if not supabase_key:
        missing.append("SUPABASE_KEY ou SUPABASE_SERVICE_KEY")

    if missing:
        print("=" * 60)
        print("ERRO: Variáveis de ambiente faltando:")
        for var in missing:
            print(f"  - {var}")
        print("\nConfigure no arquivo .env e tente novamente.")
        print("=" * 60)
        return False

    print("[OK] Variaveis de ambiente configuradas")
    return True


def executar_miner_controlado():
    """Executa o miner com parâmetros controlados."""
    from src.core.ache_sucatas_miner_v18 import MinerV18, MinerConfig

    print("\n" + "=" * 60)
    print("E2E CONTROLADO - FASE 3")
    print("=" * 60)
    print(f"Início: {datetime.now().isoformat()}")

    # Configuração mínima para teste
    config = MinerConfig(
        dias_retroativos=1,           # Apenas 24h
        paginas_por_termo=1,          # Apenas 1 página por termo
        run_limit=5,                  # Máximo 5 editais
        min_score=60,                 # Score mínimo
        force_reprocess=False,        # Modo incremental
        # Supabase (das variáveis de ambiente)
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY"),
        storage_bucket=os.getenv("STORAGE_BUCKET", "editais"),
        # OpenAI (opcional)
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )

    print("\nConfiguração:")
    print(f"  - Dias retroativos: {config.dias_retroativos}")
    print(f"  - Páginas por termo: {config.paginas_por_termo}")
    print(f"  - Run limit: {config.run_limit}")
    print(f"  - Modo: INCREMENTAL")
    print(f"  - Supabase: {'Configurado' if config.supabase_url else 'NÃO configurado'}")
    print(f"  - OpenAI: {'Configurado' if config.openai_api_key else 'NÃO configurado'}")

    # Criar e executar miner
    miner = MinerV18(config)

    print("\n" + "-" * 60)
    print("EXECUTANDO MINER...")
    print("-" * 60 + "\n")

    try:
        stats = miner.executar()

        print("\n" + "=" * 60)
        print("RESULTADO E2E")
        print("=" * 60)
        print(f"Run ID: {miner.run_id}")
        print(f"\nEstatísticas:")
        print(f"  - Editais encontrados: {stats.get('editais_encontrados', 0)}")
        print(f"  - Editais novos: {stats.get('editais_novos', 0)}")
        print(f"  - Skip (já existe): {stats.get('editais_skip_existe', 0)}")
        print(f"  - Inseridos no banco: {stats.get('supabase_inserts', 0)}")
        print(f"  - Quarentena: {stats.get('quarentena_inserts', 0)}")
        print(f"  - Erros: {stats.get('erros', 0)}")

        print(f"\nQualityReport:")
        report = miner.quality_report
        print(f"  - Total processados: {report.executed_total}")
        print(f"  - Válidos: {report.valid_count} ({report.taxa_validos_percent}%)")
        print(f"  - Quarentena: {report.total_quarentena} ({report.taxa_quarentena_percent}%)")
        print(f"  - Duração: {report.duration_seconds:.2f}s")

        if report.top_reason_codes:
            print(f"\n  Top Reason Codes:")
            for item in report.top_reason_codes[:5]:
                print(f"    - {item['code']}: {item['count']}")

        print("\n" + "=" * 60)
        print("E2E COMPLETO COM SUCESSO!")
        print("=" * 60)

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"ERRO NO E2E: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


def verificar_dados_no_supabase(run_id: str = None):
    """Verifica se os dados foram persistidos no Supabase."""
    try:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            print("Supabase não configurado, pulando verificação")
            return

        client = create_client(url, key)

        print("\n" + "=" * 60)
        print("VERIFICAÇÃO NO SUPABASE")
        print("=" * 60)

        # Verificar miner_execucoes
        result = client.table("miner_execucoes").select("*").order("inicio", desc=True).limit(3).execute()
        print(f"\nÚltimas execuções (miner_execucoes):")
        for row in result.data:
            print(f"  - ID: {row.get('id')}, Run: {row.get('run_id', 'N/A')[:20]}..., Status: {row.get('status')}")

        # Verificar quality_reports
        result = client.table("quality_reports").select("*").order("created_at", desc=True).limit(3).execute()
        print(f"\nÚltimos QualityReports:")
        for row in result.data:
            print(f"  - Run: {row.get('run_id', 'N/A')[:20]}..., Válidos: {row.get('total_validos')}, Quarentena: {row.get('total_quarentena')}")

        # Verificar pipeline_events
        result = client.table("pipeline_events").select("*").order("created_at", desc=True).limit(5).execute()
        print(f"\nÚltimos eventos do pipeline:")
        for row in result.data:
            print(f"  - [{row.get('nivel')}] {row.get('etapa')}: {row.get('evento')} - {row.get('mensagem', '')[:40]}")

        # Verificar dataset_rejections (últimos)
        result = client.table("dataset_rejections").select("*").order("created_at", desc=True).limit(3).execute()
        print(f"\nÚltimos registros em quarentena:")
        for row in result.data:
            print(f"  - {row.get('reason_code')}: {row.get('id_interno', 'N/A')[:30]}")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\nErro ao verificar Supabase: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TESTE E2E CONTROLADO - FASE 3")
    print("=" * 60)

    if not verificar_ambiente():
        sys.exit(1)

    sucesso = executar_miner_controlado()

    if sucesso:
        verificar_dados_no_supabase()

    sys.exit(0 if sucesso else 1)
