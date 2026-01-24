"""
Script para Regenerar Tags de Editais Existentes
=================================================
Usa a nova taxonomia automotiva do Supabase (V18.2) para
regenerar as tags de todos os editais no banco de dados.

OBJETIVO:
    - Remover tags indesejadas (ELETRONICO, IMOVEL, MOBILIARIO)
    - Aplicar a nova logica de classificacao baseada na taxonomia

Uso:
    python scripts/regenerar_tags_editais.py [--dry-run] [--limite N]

Opcoes:
    --dry-run   Mostra o que seria alterado sem modificar o banco
    --limite N  Processa apenas os primeiros N editais (para teste)

Requer:
    - SUPABASE_URL no .env
    - SUPABASE_SERVICE_KEY no .env (ou SUPABASE_KEY)
"""

import os
import sys
import argparse
import unicodedata
from pathlib import Path
from datetime import datetime

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# TAXONOMIA LOADER (copiado do miner V18 para independencia)
# ============================================================

class TaxonomiaLoader:
    """Carrega taxonomia automotiva do Supabase."""

    FALLBACK_TAXONOMIA = {
        "VEICULO": ["veiculo", "veiculos", "automovel", "automoveis", "carro", "carros", "automotor", "automotivo"],
        "SUCATA": ["sucata", "sucatas", "inservivel", "inserviveis", "ferroso", "ferrosos", "sucateado"],
        "MOTO": ["moto", "motos", "motocicleta", "motocicletas", "ciclomotor", "ciclomotores", "motociclo"],
        "CAMINHAO": ["caminhao", "caminhoes", "caminhonete", "camionete", "truck", "trucks", "cavalo mecanico"],
        "ONIBUS": ["onibus", "microonibus", "micro-onibus", "micro onibus"],
        "CARRETA": ["carreta", "carretas", "semi-reboque", "semirreboque", "reboque", "reboques", "implemento rodoviario"],
        "MAQUINARIO": [
            "maquina", "maquinas", "trator", "tratores", "retroescavadeira", "escavadeira",
            "pa carregadeira", "carregadeira", "motoniveladora", "patrol"
        ],
        "DOCUMENTADO": ["documentado", "documentados", "com documento", "documento ok"],
        "APREENDIDO": ["apreendido", "apreendidos", "patio", "removido", "removidos", "custodia"],
    }

    CATEGORIA_TO_TAG = {
        "TIPO": None,  # Usa tag_gerada diretamente
        "MARCA": None,
        "MODELO_LEVE": "VEICULO",
        "MODELO_MOTO": "MOTO",
        "MODELO_PESADO": "CAMINHAO",
        "IMPLEMENTO": "CARRETA",
        "MAQUINA": "MAQUINARIO",
    }

    def __init__(self, client):
        self.client = client

    def carregar(self) -> dict:
        """Carrega taxonomia do Supabase ou usa fallback."""
        if not self.client:
            print("  [WARN] Supabase nao conectado - usando taxonomia fallback")
            return self._converter_fallback()

        try:
            result = self.client.table("taxonomia_automotiva").select(
                "categoria, termo, sinonimos, tag_gerada"
            ).eq("ativo", True).execute()

            if result.data and len(result.data) > 0:
                taxonomia = self._processar_db(result.data)
                print(f"  [OK] Taxonomia carregada: {len(result.data)} termos")
                return taxonomia
            else:
                print("  [WARN] Tabela vazia - usando fallback")
                return self._converter_fallback()

        except Exception as e:
            print(f"  [ERRO] {e}")
            print("  [WARN] Usando taxonomia fallback")
            return self._converter_fallback()

    def _processar_db(self, rows: list) -> dict:
        """Processa resultado do Supabase."""
        taxonomia = {}

        for row in rows:
            tag = row.get("tag_gerada")
            termo = row.get("termo", "").lower()
            sinonimos = row.get("sinonimos") or []

            if not tag or not termo:
                continue

            if tag not in taxonomia:
                taxonomia[tag] = []

            if termo not in taxonomia[tag]:
                taxonomia[tag].append(termo)

            for sinonimo in sinonimos:
                s = sinonimo.lower().strip()
                if s and s not in taxonomia[tag]:
                    taxonomia[tag].append(s)

        return taxonomia

    def _converter_fallback(self) -> dict:
        """Converte fallback hardcoded."""
        return self.FALLBACK_TAXONOMIA.copy()


def gerar_tags_v18(titulo: str, descricao: str, objeto: str, taxonomia: dict) -> list:
    """
    Gera tags baseadas na taxonomia automotiva.

    IMPORTANTE: Apenas tags de VEICULOS sao geradas.
    Tags de IMOVEL, MOBILIARIO, ELETRONICO foram REMOVIDAS.
    """
    texto_completo = f"{titulo or ''} {descricao or ''} {objeto or ''}".lower()
    texto_normalizado = unicodedata.normalize('NFKD', texto_completo)
    texto_normalizado = texto_normalizado.encode('ASCII', 'ignore').decode('ASCII').lower()

    tags_encontradas = set()

    for tag, keywords in taxonomia.items():
        for keyword in keywords:
            keyword_norm = unicodedata.normalize('NFKD', keyword)
            keyword_norm = keyword_norm.encode('ASCII', 'ignore').decode('ASCII').lower()

            if keyword_norm in texto_normalizado or keyword in texto_completo:
                tags_encontradas.add(tag)
                break

    return sorted(list(tags_encontradas))


def main():
    parser = argparse.ArgumentParser(description="Regenera tags dos editais existentes")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra alteracoes, sem modificar")
    parser.add_argument("--limite", type=int, default=0, help="Limita quantidade de editais (0=todos)")
    args = parser.parse_args()

    print("=" * 70)
    print("REGENERADOR DE TAGS - Ache Sucatas V18.2")
    print("=" * 70)
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modo: {'DRY-RUN (simulacao)' if args.dry_run else 'PRODUCAO (vai modificar o banco)'}")
    if args.limite > 0:
        print(f"Limite: {args.limite} editais")
    print("=" * 70)

    # Conectar Supabase
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))

    if not supabase_url or not supabase_key:
        print("\n[ERRO] SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar no .env")
        sys.exit(1)

    try:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)
        print("\n[OK] Conectado ao Supabase")
    except ImportError:
        print("\n[ERRO] Biblioteca supabase nao instalada. Execute: pip install supabase")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO] Falha ao conectar: {e}")
        sys.exit(1)

    # Carregar taxonomia
    print("\n[1/4] Carregando taxonomia automotiva...")
    loader = TaxonomiaLoader(client)
    taxonomia = loader.carregar()
    print(f"  Tags disponiveis: {list(taxonomia.keys())}")

    # Buscar editais
    print("\n[2/4] Buscando editais...")
    try:
        query = client.table("editais_leilao").select("id, titulo, descricao, objeto_resumido, tags")

        if args.limite > 0:
            query = query.limit(args.limite)

        result = query.execute()
        editais = result.data or []
        print(f"  Encontrados: {len(editais)} editais")
    except Exception as e:
        print(f"  [ERRO] Falha ao buscar editais: {e}")
        sys.exit(1)

    if not editais:
        print("\n[INFO] Nenhum edital encontrado no banco.")
        sys.exit(0)

    # Processar editais
    print("\n[3/4] Processando editais...")

    estatisticas = {
        "total": len(editais),
        "alterados": 0,
        "sem_alteracao": 0,
        "tags_removidas": {"ELETRONICO": 0, "IMOVEL": 0, "MOBILIARIO": 0},
        "erros": 0,
    }

    editais_para_atualizar = []

    for i, edital in enumerate(editais, 1):
        edital_id = edital.get("id")
        titulo = edital.get("titulo") or ""
        descricao = edital.get("descricao") or ""
        objeto = edital.get("objeto_resumido") or ""
        tags_antigas = edital.get("tags") or []

        # Gerar novas tags
        tags_novas = gerar_tags_v18(titulo, descricao, objeto, taxonomia)

        # Verificar diferenca
        set_antigas = set(tags_antigas)
        set_novas = set(tags_novas)

        if set_antigas != set_novas:
            # Contabilizar tags removidas
            for tag_rem in ["ELETRONICO", "IMOVEL", "MOBILIARIO"]:
                if tag_rem in set_antigas and tag_rem not in set_novas:
                    estatisticas["tags_removidas"][tag_rem] += 1

            estatisticas["alterados"] += 1
            editais_para_atualizar.append({
                "id": edital_id,
                "tags_novas": tags_novas,
                "tags_antigas": tags_antigas,
            })

            if i <= 10 or args.dry_run:  # Mostra os primeiros 10 ou todos em dry-run
                removidas = set_antigas - set_novas
                adicionadas = set_novas - set_antigas
                print(f"  [{i}/{len(editais)}] ID {edital_id}")
                print(f"      Antigas: {tags_antigas}")
                print(f"      Novas:   {tags_novas}")
                if removidas:
                    print(f"      Removidas: {removidas}")
                if adicionadas:
                    print(f"      Adicionadas: {adicionadas}")
        else:
            estatisticas["sem_alteracao"] += 1

        # Progresso
        if i % 100 == 0:
            print(f"  ... {i}/{len(editais)} processados")

    # Atualizar banco
    print("\n[4/4] Atualizando banco de dados...")

    if args.dry_run:
        print("  [DRY-RUN] Nenhuma alteracao feita no banco")
    elif editais_para_atualizar:
        print(f"  Atualizando {len(editais_para_atualizar)} editais...")

        for i, item in enumerate(editais_para_atualizar, 1):
            try:
                client.table("editais_leilao").update({
                    "tags": item["tags_novas"]
                }).eq("id", item["id"]).execute()

                if i % 50 == 0:
                    print(f"  ... {i}/{len(editais_para_atualizar)} atualizados")
            except Exception as e:
                print(f"  [ERRO] ID {item['id']}: {e}")
                estatisticas["erros"] += 1

        print(f"  [OK] {len(editais_para_atualizar) - estatisticas['erros']} editais atualizados")
    else:
        print("  [INFO] Nenhum edital precisa ser atualizado")

    # Relatorio final
    print("\n" + "=" * 70)
    print("RELATORIO FINAL")
    print("=" * 70)
    print(f"Total de editais:    {estatisticas['total']}")
    print(f"Alterados:           {estatisticas['alterados']}")
    print(f"Sem alteracao:       {estatisticas['sem_alteracao']}")
    print(f"Erros:               {estatisticas['erros']}")
    print("\nTags removidas:")
    for tag, count in estatisticas["tags_removidas"].items():
        if count > 0:
            print(f"  - {tag}: {count}")
    print("=" * 70)

    if args.dry_run and estatisticas["alterados"] > 0:
        print("\n[AVISO] Execute sem --dry-run para aplicar as alteracoes")


if __name__ == "__main__":
    main()
