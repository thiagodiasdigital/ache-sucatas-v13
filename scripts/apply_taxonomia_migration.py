"""
Script para aplicar migration da Taxonomia Automotiva no Supabase.

Uso:
    python scripts/apply_taxonomia_migration.py

Requer:
    - SUPABASE_URL no .env
    - SUPABASE_SERVICE_KEY no .env (ou SUPABASE_KEY)
"""

import os
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def main():
    """Aplica migration da taxonomia automotiva."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))

    if not supabase_url or not supabase_key:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar configurados no .env")
        sys.exit(1)

    try:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)
    except ImportError:
        print("ERRO: Biblioteca supabase nao instalada. Execute: pip install supabase")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO ao conectar Supabase: {e}")
        sys.exit(1)

    print("=" * 70)
    print("APLICANDO MIGRATION: Taxonomia Automotiva")
    print("=" * 70)

    # Ler arquivo SQL
    migration_path = Path(__file__).parent.parent / "frontend" / "supabase" / "migration_taxonomia_automotiva.sql"

    if not migration_path.exists():
        print(f"ERRO: Arquivo de migration nao encontrado: {migration_path}")
        sys.exit(1)

    print(f"Lendo migration: {migration_path}")

    with open(migration_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Separar comandos SQL (simplificado - para uso com Supabase Dashboard)
    print("\n" + "=" * 70)
    print("INSTRUCOES PARA APLICAR A MIGRATION:")
    print("=" * 70)
    print("""
1. Acesse o Supabase Dashboard: https://supabase.com/dashboard

2. Selecione seu projeto

3. Va em: SQL Editor (icone de banco de dados no menu lateral)

4. Clique em "New Query"

5. Copie e cole TODO o conteudo do arquivo:
   frontend/supabase/migration_taxonomia_automotiva.sql

6. Clique em "Run" (ou Ctrl+Enter)

7. Verifique se a tabela foi criada:
   SELECT COUNT(*) FROM taxonomia_automotiva;

A migration ira:
- Criar a tabela 'taxonomia_automotiva'
- Popular com ~300 termos automotivos
- Configurar indices para busca rapida
""")

    print("=" * 70)
    print("VERIFICANDO SE TABELA JA EXISTE...")
    print("=" * 70)

    try:
        result = client.table("taxonomia_automotiva").select("categoria").limit(1).execute()
        if result.data is not None:
            # Tabela existe, verificar quantidade
            count_result = client.table("taxonomia_automotiva").select("*", count="exact").execute()
            total = count_result.count if hasattr(count_result, 'count') else len(count_result.data)
            print(f"\nTabela 'taxonomia_automotiva' ja existe com {total} registros.")

            if total > 0:
                # Mostrar resumo por categoria
                categorias = {}
                all_data = client.table("taxonomia_automotiva").select("categoria").execute()
                for row in all_data.data:
                    cat = row.get("categoria", "DESCONHECIDO")
                    categorias[cat] = categorias.get(cat, 0) + 1

                print("\nResumo por categoria:")
                for cat, count in sorted(categorias.items()):
                    print(f"  - {cat}: {count} termos")

                print("\nSe quiser recriar a tabela, execute o SQL manualmente no Dashboard.")
            else:
                print("\nTabela existe mas esta vazia. Execute o SQL no Dashboard para popular.")

    except Exception as e:
        if "relation" in str(e).lower() and "does not exist" in str(e).lower():
            print("\nTabela 'taxonomia_automotiva' NAO existe.")
            print("Execute o SQL no Dashboard do Supabase para criar.")
        else:
            print(f"\nErro ao verificar tabela: {e}")
            print("Execute o SQL manualmente no Dashboard do Supabase.")

    print("\n" + "=" * 70)
    print("ARQUIVO SQL PARA COPIAR:")
    print("=" * 70)
    print(f"\n{migration_path}\n")


if __name__ == "__main__":
    main()
