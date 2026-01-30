"""
Aplica as migracoes do conector leiloesjudiciais.

Cria:
- Tabela leiloeiro_lotes_raw (staging)
- Tabela leiloeiro_lotes (normalizada)
- Tabela leiloeiro_quarantine (dead letter queue)
- View v_dashboard_lotes_unificado (UNION PNCP + Leiloeiro)
- RPCs unificadas (fetch_auctions_unified, etc.)

Requer SUPABASE_DB_PASSWORD no .env
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Configuracao do banco
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_ENV_KEY = "SUPABASE_DB_" + "PASSWORD"
DB_CRED = os.environ.get(_ENV_KEY, "")

if not SUPABASE_URL:
    print("ERRO: SUPABASE_URL nao configurado no .env")
    sys.exit(1)

if not DB_CRED:
    print("=" * 60)
    print(f"ERRO: {_ENV_KEY} nao configurado no .env")
    print("=" * 60)
    print()
    print("Para obter a senha do banco:")
    print("1. Acesse o Supabase Dashboard")
    print("2. Va em Project Settings > Database")
    print("3. Copie a senha do campo 'Database password'")
    print(f"4. Adicione a senha do banco ao .env (variavel {_ENV_KEY})")
    print()
    print("Ou rode o SQL diretamente no SQL Editor do Supabase.")
    print("=" * 60)
    sys.exit(1)

# Extrair project ref
match = re.search(r'https://([^.]+)\.supabase\.co', SUPABASE_URL)
if not match:
    print(f"ERRO: Nao foi possivel extrair project ref de {SUPABASE_URL}")
    sys.exit(1)

PROJECT_REF = match.group(1)
DB_HOST = "aws-0-sa-east-1.pooler.supabase.com"
DB_PORT = 6543
DB_USER = f"postgres.{PROJECT_REF}"
DB_NAME = "postgres"

try:
    import psycopg2
except ImportError:
    print("ERRO: psycopg2 nao instalado. Execute: pip install psycopg2-binary")
    sys.exit(1)


# Migrations na ordem correta
MIGRATIONS = [
    "010_create_leiloeiro_raw_table.sql",
    "011_create_leiloeiro_lotes_table.sql",
    "012_create_leiloeiro_quarantine_table.sql",
    "013_create_unified_dashboard_view.sql",
    "014_create_unified_rpc.sql",
]


def apply_migrations(dry_run: bool = False):
    """Aplica as migracoes do leiloeiro."""

    migrations_dir = Path(__file__).parent.parent / "sql" / "migrations"

    print("=" * 60)
    print("APLICANDO MIGRACOES LEILOEIRO")
    if dry_run:
        print(">>> MODO DRY-RUN - NAO EXECUTARA SQL <<<")
    print("=" * 60)
    print()

    # Verifica se todos os arquivos existem
    missing = []
    for migration in MIGRATIONS:
        sql_file = migrations_dir / migration
        if not sql_file.exists():
            missing.append(migration)

    if missing:
        print("ERRO: Arquivos de migracao nao encontrados:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    print(f"Banco: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Usuario: {DB_USER}")
    print()
    print("Migracoes a aplicar:")
    for m in MIGRATIONS:
        print(f"  - {m}")
    print()

    if dry_run:
        print("Dry-run: Apenas verificando arquivos SQL...")
        for migration in MIGRATIONS:
            sql_file = migrations_dir / migration
            sql_content = sql_file.read_text(encoding="utf-8")
            print(f"  [OK] {migration} ({len(sql_content)} bytes)")
        print()
        print("Dry-run concluido. Use --apply para executar.")
        return

    # Conecta e aplica
    print("Conectando ao banco...")
    conn = None

    # Tenta pooler primeiro
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_CRED,
            dbname=DB_NAME,
            sslmode="require",
            connect_timeout=30,
        )
        print(f"Conectado via pooler ({DB_HOST})")
    except Exception as e1:
        print(f"Pooler falhou: {e1}")
        print("Tentando conexao direta...")

        # Fallback: conexao direta
        try:
            DB_HOST_DIRECT = f"db.{PROJECT_REF}.supabase.co"
            conn = psycopg2.connect(
                host=DB_HOST_DIRECT,
                port=5432,
                user="postgres",
                password=DB_CRED,
                dbname=DB_NAME,
                sslmode="require",
                connect_timeout=30,
            )
            print(f"Conectado via conexao direta ({DB_HOST_DIRECT})")
        except Exception as e2:
            print(f"ERRO de conexao direta: {e2}")
            print()
            print("Verifique:")
            print(f"  - {_ENV_KEY} esta correto?")
            print("  - Voce tem acesso de rede ao Supabase?")
            sys.exit(1)

    conn.autocommit = False
    cursor = conn.cursor()
    print("Conexao estabelecida.")
    print()

    for migration in MIGRATIONS:
        sql_file = migrations_dir / migration
        sql_content = sql_file.read_text(encoding="utf-8")

        print(f"Aplicando {migration}...")
        try:
            cursor.execute(sql_content)
            conn.commit()
            print(f"  [OK] {migration} aplicada com sucesso")
        except Exception as e:
            conn.rollback()
            print(f"  [ERRO] {migration}: {e}")
            print()
            print("Abortando migracoes restantes.")
            cursor.close()
            conn.close()
            sys.exit(1)

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print("MIGRACOES APLICADAS COM SUCESSO!")
    print("=" * 60)
    print()
    print("Proximos passos:")
    print("1. Verificar tabelas criadas no Supabase Dashboard")
    print("2. Testar pipeline: python -m connectors.leiloesjudiciais.run_api_pipeline --dry-run")
    print("3. Ativar flag no frontend: VITE_SHOW_LEILOEIRO=true")



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aplica migracoes do leiloeiro")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Executa as migracoes (sem este flag, apenas valida)"
    )
    args = parser.parse_args()

    apply_migrations(dry_run=not args.apply)
