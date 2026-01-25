"""
Script para remover TODAS as versões duplicadas da função fetch_auctions_paginated
"""

import os
import sys
import psycopg2

# Configuracao via variaveis de ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
SUPABASE_PROJECT = SUPABASE_URL.replace("https://", "").split(".")[0] if SUPABASE_URL else ""

if not SUPABASE_DB_PASSWORD or not SUPABASE_PROJECT:
    print("ERRO: Configure SUPABASE_URL e SUPABASE_DB_PASSWORD no .env")
    sys.exit(1)

DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@db.{SUPABASE_PROJECT}.supabase.co:5432/postgres"

def main():
    print("=" * 60)
    print("FIX AGRESSIVO: REMOVER TODAS AS FUNÇÕES")
    print("=" * 60)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        print("Conexão estabelecida!")

        # Listar TODAS as versões em TODOS os schemas
        print("\n1. Listando TODAS as versões...")
        cursor.execute("""
            SELECT
                n.nspname as schema,
                p.proname as function_name,
                pg_get_function_identity_arguments(p.oid) as arguments,
                p.oid
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE p.proname = 'fetch_auctions_paginated'
            ORDER BY n.nspname;
        """)

        functions = cursor.fetchall()
        print(f"   Encontradas {len(functions)} versões:")
        for func in functions:
            print(f"   - {func[0]}.{func[1]}(oid={func[3]})")
            print(f"     Args: {func[2][:100]}...")

        # Remover cada uma pelo OID
        print("\n2. Removendo cada função pelo OID...")
        for func in functions:
            schema, name, args, oid = func
            try:
                # Construir DROP statement com argumentos completos
                drop_sql = f"DROP FUNCTION IF EXISTS {schema}.{name}({args});"
                cursor.execute(drop_sql)
                print(f"   OK: Removida {schema}.{name} (oid={oid})")
            except Exception as e:
                print(f"   ERRO ao remover {schema}.{name}: {e}")

        # Verificar que todas foram removidas
        print("\n3. Verificando se todas foram removidas...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE p.proname = 'fetch_auctions_paginated';
        """)
        count = cursor.fetchone()[0]
        print(f"   Funções restantes: {count}")

        if count > 0:
            print("   AVISO: Ainda existem funções. Listando...")
            cursor.execute("""
                SELECT n.nspname, pg_get_function_identity_arguments(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE p.proname = 'fetch_auctions_paginated';
            """)
            for row in cursor.fetchall():
                print(f"   - {row[0]}: {row[1]}")

        # Criar a função única
        print("\n4. Criando função única no schema PUBLIC...")

        create_function_sql = """
CREATE OR REPLACE FUNCTION public.fetch_auctions_paginated(
    p_uf TEXT DEFAULT NULL,
    p_cidade TEXT DEFAULT NULL,
    p_valor_min NUMERIC DEFAULT NULL,
    p_valor_max NUMERIC DEFAULT NULL,
    p_data_publicacao_de DATE DEFAULT NULL,
    p_data_publicacao_ate DATE DEFAULT NULL,
    p_data_leilao_de DATE DEFAULT NULL,
    p_data_leilao_ate DATE DEFAULT NULL,
    p_page INTEGER DEFAULT 1,
    p_page_size INTEGER DEFAULT 20,
    p_ordenacao TEXT DEFAULT 'proximos',
    p_temporalidade TEXT DEFAULT 'futuros'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_total INTEGER;
    v_total_pages INTEGER;
    v_offset INTEGER;
    v_data JSON;
BEGIN
    v_offset := (p_page - 1) * p_page_size;

    SELECT COUNT(*) INTO v_total
    FROM pub.v_auction_discovery v
    WHERE
        (p_uf IS NULL OR v.uf = p_uf)
        AND (p_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || p_cidade || '%'))
        AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
        AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
        AND (p_data_publicacao_de IS NULL OR v.data_publicacao >= p_data_publicacao_de)
        AND (p_data_publicacao_ate IS NULL OR v.data_publicacao <= p_data_publicacao_ate)
        AND (p_data_leilao_de IS NULL OR v.data_leilao::date >= p_data_leilao_de)
        AND (p_data_leilao_ate IS NULL OR v.data_leilao::date <= p_data_leilao_ate)
        AND (
            p_temporalidade = 'todos'
            OR (p_temporalidade = 'futuros' AND v.data_leilao >= CURRENT_DATE)
            OR (p_temporalidade = 'passados' AND v.data_leilao < CURRENT_DATE)
        );

    v_total_pages := CEIL(GREATEST(v_total, 1)::DECIMAL / p_page_size);

    SELECT json_agg(row_to_json(t))
    INTO v_data
    FROM (
        SELECT
            v.id,
            v.id_interno,
            v.pncp_id,
            v.orgao,
            v.uf,
            v.cidade,
            v.n_edital,
            v.data_publicacao,
            v.data_leilao,
            v.titulo,
            v.descricao,
            v.objeto_resumido,
            v.tags,
            v.link_pncp,
            v.link_leiloeiro,
            v.modalidade_leilao,
            v.valor_estimado,
            v.quantidade_itens,
            v.nome_leiloeiro,
            v.storage_path,
            v.score,
            v.created_at,
            v.codigo_ibge,
            v.latitude,
            v.longitude,
            v.municipio_oficial,
            CASE
                WHEN v.data_leilao >= CURRENT_DATE THEN 'futuro'
                ELSE 'passado'
            END AS status_temporal
        FROM pub.v_auction_discovery v
        WHERE
            (p_uf IS NULL OR v.uf = p_uf)
            AND (p_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || p_cidade || '%'))
            AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
            AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
            AND (p_data_publicacao_de IS NULL OR v.data_publicacao >= p_data_publicacao_de)
            AND (p_data_publicacao_ate IS NULL OR v.data_publicacao <= p_data_publicacao_ate)
            AND (p_data_leilao_de IS NULL OR v.data_leilao::date >= p_data_leilao_de)
            AND (p_data_leilao_ate IS NULL OR v.data_leilao::date <= p_data_leilao_ate)
            AND (
                p_temporalidade = 'todos'
                OR (p_temporalidade = 'futuros' AND v.data_leilao >= CURRENT_DATE)
                OR (p_temporalidade = 'passados' AND v.data_leilao < CURRENT_DATE)
            )
        ORDER BY
            CASE WHEN p_ordenacao = 'proximos' THEN v.data_leilao END ASC NULLS LAST,
            CASE WHEN p_ordenacao = 'distantes' THEN v.data_leilao END DESC NULLS LAST,
            CASE WHEN p_ordenacao = 'recentes' THEN v.data_publicacao END DESC NULLS LAST,
            CASE WHEN p_ordenacao = 'antigos' THEN v.data_publicacao END ASC NULLS LAST
        LIMIT p_page_size
        OFFSET v_offset
    ) t;

    RETURN json_build_object(
        'data', COALESCE(v_data, '[]'::json),
        'total', v_total,
        'page', p_page,
        'pageSize', p_page_size,
        'totalPages', v_total_pages,
        'temporalidade', p_temporalidade
    );
END;
$$;
"""

        cursor.execute(create_function_sql)
        print("   Função criada!")

        # Permissões
        cursor.execute("""
            GRANT EXECUTE ON FUNCTION public.fetch_auctions_paginated(
                TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE,
                INTEGER, INTEGER, TEXT, TEXT
            ) TO anon, authenticated;
        """)
        print("   Permissões OK!")

        # Verificar final
        print("\n5. Verificação final...")
        cursor.execute("""
            SELECT n.nspname, p.proname
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE p.proname = 'fetch_auctions_paginated';
        """)
        functions = cursor.fetchall()
        print(f"   Total de funções agora: {len(functions)}")
        for f in functions:
            print(f"   - {f[0]}.{f[1]}")

        # Testar
        print("\n6. Teste final...")
        cursor.execute("""
            SELECT
                (public.fetch_auctions_paginated(
                    'MG', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 5, 'proximos', 'todos'
                )::json->'data'->0->>'cidade') as cidade,
                (public.fetch_auctions_paginated(
                    'MG', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 5, 'proximos', 'todos'
                )::json->'data'->0->>'latitude') as lat,
                (public.fetch_auctions_paginated(
                    'MG', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 5, 'proximos', 'todos'
                )::json->'data'->0->>'longitude') as lng
        """)
        result = cursor.fetchone()
        print(f"   Primeiro leilão: {result[0]}")
        print(f"   Latitude: {result[1]}")
        print(f"   Longitude: {result[2]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("SUCESSO!")
        print("Recarregue o navegador para testar.")
        print("=" * 60)

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
