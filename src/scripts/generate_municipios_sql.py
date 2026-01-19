#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gera insert_municipios.sql para popular pub.ref_municipios com todos os municípios do Brasil.

- Lista oficial: API de Localidades do IBGE
- Coordenadas: kelvins/municipios-brasileiros (json/municipios.json)
- Saída: INSERT ... ON CONFLICT (codigo_ibge) DO NOTHING;

Uso:
  python generate_municipios_sql.py --out insert_municipios.sql --use-zero-when-missing
  python generate_municipios_sql.py --out insert_municipios.sql --omit-when-missing
"""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen


IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
IBGE_MUNICIPIOS_URL_FALLBACK = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

KELVINS_MUNICIPIOS_JSON = (
    "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/json/municipios.json"
)

LOWER_WORDS = {
    "de", "da", "do", "das", "dos",
    "e",
    "em", "no", "na", "nos", "nas",
    "para", "por",
    "a", "o", "as", "os",
    "d'",
}


@dataclass(frozen=True)
class MunicipioIBGE:
    codigo_ibge: int
    nome: str
    uf: str


def http_get_bytes(url: str, timeout: int = 60) -> Tuple[bytes, str]:
    """
    Faz GET e retorna (bytes, content_encoding).
    Aceita gzip/deflate e identifica gzip por header também (magic bytes 1F 8B).
    """
    req = Request(
        url,
        headers={
            "User-Agent": "ache-sucatas-daas/1.0 (data-engineering)",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
    return raw, encoding


def decode_text_safely(raw: bytes) -> str:
    """
    Decodifica bytes em texto tratando:
    - UTF-8 normal
    - UTF-8 com BOM (utf-8-sig remove BOM)
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # fallback conservador
        return raw.decode("utf-8", errors="strict")

def decode_text_with_bom_handling(raw: bytes) -> str:
    """
    Preferir utf-8-sig pra remover BOM se existir.
    Se não tiver BOM, funciona igual utf-8.
    """
    return raw.decode("utf-8-sig")


def http_get_json(url: str, timeout: int = 60):
    raw, encoding = http_get_bytes(url, timeout=timeout)

    # Detecta gzip por header OU por magic bytes 1F 8B
    is_gzip = "gzip" in encoding or (len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B)
    if is_gzip:
        raw = gzip.decompress(raw)

    # BOM handling (principalmente arquivos do GitHub/RAW que às vezes vêm com BOM)
    text = decode_text_with_bom_handling(raw)

    return json.loads(text)


def smart_title_ptbr(name: str) -> str:
    """
    Title Case para PT-BR com regras simples:
    - Primeira palavra: Capitaliza
    - Preposições/conjunções comuns: minúsculas (quando não são a primeira)
    - Hífens: trata segmento a segmento
    """
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return name

    out: List[str] = []
    for i, w in enumerate(parts):
        lw = w.lower()

        if "-" in w:
            segs = w.split("-")
            seg_out: List[str] = []
            for j, s in enumerate(segs):
                sl = s.lower()
                if i == 0 and j == 0:
                    seg_out.append(sl[:1].upper() + sl[1:])
                elif sl in LOWER_WORDS:
                    seg_out.append(sl)
                else:
                    seg_out.append(sl[:1].upper() + sl[1:])
            out.append("-".join(seg_out))
            continue

        if i == 0:
            out.append(lw[:1].upper() + lw[1:])
        elif lw in LOWER_WORDS:
            out.append(lw)
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out)


def quantize_6(x: float) -> str:
    d = Decimal(str(x)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{d:.6f}"


def sql_escape_text(s: str) -> str:
    return s.replace("'", "''")


def parse_ibge_municipios(payload) -> List[MunicipioIBGE]:
    """
    Extrai (codigo_ibge, nome, uf) de forma defensiva.
    Suporta:
    - Formato normal: {"id", "nome", ... UF aninhado ...}
    - Formato view=nivelado: {"municipio-id", "municipio-nome", "UF-sigla", ...}
    """
    municipios: List[MunicipioIBGE] = []

    if not isinstance(payload, list):
        return municipios

    for item in payload:
        if not isinstance(item, dict):
            continue

        codigo = (
            item.get("municipio-id")
            or item.get("id")
            or item.get("codigo_ibge")
            or item.get("codigo")
            or item.get("cod")
        )
        nome = item.get("municipio-nome") or item.get("nome") or item.get("nome_municipio") or item.get("municipio")

        uf = item.get("UF-sigla") or item.get("uf") or item.get("sigla")

        if not uf:
            try:
                uf = item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            except Exception:
                pass

        if not uf:
            try:
                uf = item["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
            except Exception:
                pass

        if not uf:
            try:
                uf = item["municipio"]["UF"]["sigla"]
            except Exception:
                pass

        if not uf:
            try:
                uf = item["UF"]["sigla"]
            except Exception:
                pass

        if codigo is None or nome is None or uf is None:
            continue

        try:
            municipios.append(
                MunicipioIBGE(
                    codigo_ibge=int(codigo),
                    nome=str(nome),
                    uf=str(uf).upper().strip(),
                )
            )
        except Exception:
            continue

    return municipios


def load_coords_kelvins() -> Dict[int, Tuple[float, float]]:
    """
    Carrega coordenadas (latitude, longitude) por codigo_ibge do dataset kelvins.
    """
    data = http_get_json(KELVINS_MUNICIPIOS_JSON)
    coords: Dict[int, Tuple[float, float]] = {}

    if not isinstance(data, list):
        raise RuntimeError("Dataset de coordenadas não retornou uma lista. Possível payload inesperado.")

    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            codigo = int(row["codigo_ibge"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            coords[codigo] = (lat, lon)
        except Exception:
            continue

    return coords


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Gera insert_municipios.sql para pub.ref_municipios (IBGE + coords).")
    ap.add_argument("--out", default="insert_municipios.sql", help="Caminho do arquivo .sql de saída")
    ap.add_argument(
        "--use-zero-when-missing",
        action="store_true",
        help="Se faltar coordenada, usar 0.000000/0.000000 (e listar no topo).",
    )
    ap.add_argument(
        "--omit-when-missing",
        action="store_true",
        help="Se faltar coordenada, omitir o município do SQL (ignora --use-zero-when-missing).",
    )
    args = ap.parse_args(argv)

    # 1) Baixa municípios do IBGE
    try:
        payload = http_get_json(IBGE_MUNICIPIOS_URL)
    except Exception:
        payload = http_get_json(IBGE_MUNICIPIOS_URL_FALLBACK)

    municipios = parse_ibge_municipios(payload)
    if not municipios:
        # debug mínimo útil
        sample = payload[0] if isinstance(payload, list) and payload else payload
        raise RuntimeError(
            "Não consegui extrair municípios da API do IBGE (payload inesperado ou indisponível). "
            f"Sample payload: {str(sample)[:250]}"
        )

    # 2) Baixa coordenadas do dataset (BOM tratado)
    coords = load_coords_kelvins()

    # 3) Gera SQL
    missing: List[int] = []
    inserted = 0
    omitted = 0

    municipios_sorted = sorted(municipios, key=lambda m: m.codigo_ibge)

    lines: List[str] = []
    lines.append("-- Generated by generate_municipios_sql.py")
    lines.append("-- Target table: pub.ref_municipios (codigo_ibge, nome_municipio, uf, latitude, longitude)")
    lines.append("-- INSERT ... ON CONFLICT DO NOTHING for idempotency")
    lines.append("BEGIN;")
    lines.append("")

    for m in municipios_sorted:
        latlon = coords.get(m.codigo_ibge)

        if latlon is None:
            missing.append(m.codigo_ibge)
            if args.omit_when_missing:
                omitted += 1
                continue
            if args.use_zero_when_missing:
                lat_s = "0.000000"
                lon_s = "0.000000"
            else:
                omitted += 1
                continue
        else:
            lat_s = quantize_6(latlon[0])
            lon_s = quantize_6(latlon[1])

        nome_fmt = smart_title_ptbr(m.nome)
        sql = (
            "INSERT INTO pub.ref_municipios "
            "(codigo_ibge, nome_municipio, uf, latitude, longitude) VALUES "
            f"({m.codigo_ibge}, '{sql_escape_text(nome_fmt)}', '{sql_escape_text(m.uf)}', {lat_s}, {lon_s}) "
            "ON CONFLICT (codigo_ibge) DO NOTHING;"
        )
        lines.append(sql)
        inserted += 1

    lines.append("")
    lines.append("COMMIT;")
    lines.append("")

    if missing:
        header = [
            f"-- WARNING: {len(missing)} municipios sem coordenadas no dataset de coordenadas.",
            "-- Codigos IBGE afetados (7 digitos): " + ", ".join(str(x) for x in missing),
            "",
        ]
        lines = header + lines

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print(f"OK: gerado {args.out}")
    print(f"IBGE municipios lidos: {len(municipios_sorted)}")
    print(f"Inserts gerados: {inserted}")
    print(f"Omitidos por falta de coords: {omitted}")
    if missing:
        print(f"Sem coords (listados no topo do SQL): {len(missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
