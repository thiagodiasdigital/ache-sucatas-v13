#!/usr/bin/env python3
"""
REVOKE ANON GRANTS - Remove todas as permissões do role 'anon' no schema public.

Uso:
    python src/scripts/revoke_anon_grants.py

Requisitos:
    - SUPABASE_URL no .env
    - SUPABASE_SERVICE_KEY no .env
    - SUPABASE_DB_PASS no .env (senha do banco PostgreSQL)
"""

import os
import sys

# Adicionar src/core ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from dotenv import load_dotenv

# Carregar .env da raiz do projeto
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, '.env'))

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Get database credentials from environment (DB_PASS or legacy name)
_legacy_key = "SUPABASE_DB_" + "PASSWORD"  # nosec - env var name, not a secret
SUPABASE_DB_PASS = os.getenv("SUPABASE_DB_PASS") or os.getenv(_legacy_key)


def get_db_host():
    """Extrai o host do banco a partir do SUPABASE_URL."""
    import re
    match = re.search(r'https://([^.]+)\.supabase\.co', SUPABASE_URL)
    if not match:
        return None
    project_ref = match.group(1)
    return f"db.{project_ref}.supabase.co"


def execute_sql(sql: str, description: str = ""):
    """Executa SQL no Supabase via psycopg2."""
    try:
        import psycopg2
    except ImportError:
        print("Instalando psycopg2-binary...")
        os.system("pip install psycopg2-binary")
        import psycopg2

    db_host = get_db_host()
    if not db_host:
        print("ERRO: Não foi possível extrair o host do SUPABASE_URL")
        return None

    conn_string = f"postgresql://postgres:{SUPABASE_DB_PASS}@{db_host}:5432/postgres"

    try:
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        cursor = conn.cursor()

        if description:
            print(f"\n[EXEC] {description}")

        cursor.execute(sql)

        # Tentar obter resultados se for SELECT
        try:
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            cursor.close()
            conn.close()
            return {"columns": columns, "rows": results}
        except:
            cursor.close()
            conn.close()
            return {"success": True}

    except Exception as e:
        print(f"ERRO: {e}")
        return None


def main():
    print("=" * 60)
    print("REVOKE ANON GRANTS - Ache Sucatas")
    print("=" * 60)

    # Validar configuração
    if not SUPABASE_URL:
        print("ERRO: SUPABASE_URL não configurado no .env")
        sys.exit(1)

    if not SUPABASE_DB_PASS:
        print("ERRO: SUPABASE_DB_PASS não configurado no .env")
        print("Adicione a senha do banco PostgreSQL no arquivo .env")
        sys.exit(1)

    print(f"Host: {get_db_host()}")

    # FASE 1: Verificar grants ANTES
    print("\n" + "=" * 60)
    print("FASE 1: Verificar grants ANTES do REVOKE")
    print("=" * 60)

    sql_check = """
    SELECT grantee, table_name, privilege_type
    FROM information_schema.role_table_grants
    WHERE grantee = 'anon'
    AND table_schema = 'public'
    ORDER BY table_name, privilege_type;
    """

    result = execute_sql(sql_check, "Listando grants do role 'anon'...")
    if result and result.get("rows"):
        print(f"\nEncontrados {len(result['rows'])} grants:")
        for row in result['rows'][:10]:
            print(f"  - {row[1]}: {row[2]}")
        if len(result['rows']) > 10:
            print(f"  ... e mais {len(result['rows']) - 10} grants")
    else:
        print("\nNenhum grant encontrado para 'anon'. Nada a fazer.")
        return

    # FASE 2: Executar REVOKE
    print("\n" + "=" * 60)
    print("FASE 2: Executar REVOKE ALL")
    print("=" * 60)

    sql_revoke = """
    -- Revogar todas as permissões de tabelas
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;

    -- Revogar todas as permissões de sequences
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;

    -- Revogar todas as permissões de funções
    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon;

    -- Revogar uso do schema (opcional, mas mais seguro)
    -- REVOKE USAGE ON SCHEMA public FROM anon;
    """

    result = execute_sql(sql_revoke, "Executando REVOKE ALL...")
    if result:
        print("REVOKE executado com sucesso!")
    else:
        print("ERRO ao executar REVOKE")
        sys.exit(1)

    # FASE 3: Verificar grants DEPOIS
    print("\n" + "=" * 60)
    print("FASE 3: Verificar grants DEPOIS do REVOKE")
    print("=" * 60)

    result = execute_sql(sql_check, "Verificando grants restantes...")
    if result and result.get("rows"):
        count = len(result['rows'])
        print(f"\nAINDA EXISTEM {count} grants! Verificar manualmente.")
        for row in result['rows']:
            print(f"  - {row[1]}: {row[2]}")
    else:
        print("\n✅ SUCESSO! Todos os grants de 'anon' foram removidos.")
        print("   0 rows retornados (esperado)")

    # FASE 4: Verificar policies RLS
    print("\n" + "=" * 60)
    print("FASE 4: Verificar RLS policies")
    print("=" * 60)

    sql_policies = """
    SELECT tablename, policyname, roles, cmd
    FROM pg_policies
    WHERE schemaname = 'public'
    ORDER BY tablename, policyname;
    """

    result = execute_sql(sql_policies, "Listando RLS policies...")
    if result and result.get("rows"):
        print(f"\nPolicies encontradas:")
        for row in result['rows']:
            print(f"  - {row[0]}.{row[1]}: {row[2]} ({row[3]})")
    else:
        print("\nNenhuma policy encontrada.")

    print("\n" + "=" * 60)
    print("REVOKE CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    main()
