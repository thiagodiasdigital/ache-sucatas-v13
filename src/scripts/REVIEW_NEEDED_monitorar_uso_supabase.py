#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Uso Supabase - Freio de Seguranca $50 USD
Monitora uso e alerta ANTES de gerar custos
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from supabase_repository import SupabaseRepository
import json
from datetime import datetime
from pathlib import Path

# LIMITES FREE TIER SUPABASE
LIMITE_DATABASE_MB = 500  # Free tier
LIMITE_EDITAIS = 10000    # Estimativa conservadora
LIMITE_BANDWIDTH_GB_MES = 2  # Free tier

# THRESHOLDS DE ALERTA
ALERTA_80_PERCENT = 0.8
ALERTA_90_PERCENT = 0.9

print("=" * 60)
print("MONITOR DE USO SUPABASE - FREIO $50 USD")
print("=" * 60)

repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("\n[ERRO] Supabase nao conectado")
    sys.exit(1)

print("\n[OK] Conectado ao Supabase")

# 1. CONTAR EDITAIS
print("\n[1] Verificando quantidade de editais...")
count_editais = repo.contar_editais()
print(f"    Total: {count_editais}")

percent_editais = (count_editais / LIMITE_EDITAIS) * 100

if count_editais > LIMITE_EDITAIS * ALERTA_90_PERCENT:
    print(f"    [ALERTA CRITICO] {percent_editais:.1f}% do limite estimado!")
elif count_editais > LIMITE_EDITAIS * ALERTA_80_PERCENT:
    print(f"    [AVISO] {percent_editais:.1f}% do limite estimado")
else:
    print(f"    [OK] {percent_editais:.1f}% do limite ({count_editais}/{LIMITE_EDITAIS})")

# 2. ESTIMAR TAMANHO DO DATABASE
print("\n[2] Estimando tamanho do database...")

# Estimar: cada edital ~ 2-5 KB em média
# JSON com todos os campos + indexes + overhead
tamanho_medio_kb = 3  # Conservador
tamanho_estimado_mb = (count_editais * tamanho_medio_kb) / 1024

print(f"    Estimativa: {tamanho_estimado_mb:.2f} MB")

percent_db = (tamanho_estimado_mb / LIMITE_DATABASE_MB) * 100

if tamanho_estimado_mb > LIMITE_DATABASE_MB * ALERTA_90_PERCENT:
    print(f"    [ALERTA CRITICO] {percent_db:.1f}% do limite free tier!")
    print(f"    [ACAO] PAUSAR insercoes!")
elif tamanho_estimado_mb > LIMITE_DATABASE_MB * ALERTA_80_PERCENT:
    print(f"    [AVISO] {percent_db:.1f}% do limite free tier")
else:
    print(f"    [OK] {percent_db:.1f}% do limite ({tamanho_estimado_mb:.1f}/{LIMITE_DATABASE_MB} MB)")

# 3. LISTAR ÚLTIMOS EDITAIS (sample)
print("\n[3] Verificando integridade dos dados...")
editais_recentes = repo.listar_editais_recentes(limit=3)
print(f"    Sample: {len(editais_recentes)} editais recentes")

for e in editais_recentes:
    print(f"    - {e.get('id_interno')}: {e.get('titulo', '')[:40]}...")

# 4. ESTATÍSTICAS GERAIS
print("\n[4] Estatisticas gerais...")

# Calcular data range
datas_leilao = [e.get('data_leilao') for e in editais_recentes if e.get('data_leilao')]
if datas_leilao:
    print(f"    Data leilao (sample): {datas_leilao[0][:10]} a {datas_leilao[-1][:10]}")

# UFs representadas
ufs = set(e.get('uf') for e in editais_recentes if e.get('uf'))
print(f"    UFs (sample): {', '.join(sorted(ufs))}")

# 5. CÁLCULO DE CUSTO ESTIMADO
print("\n[5] Estimativa de custo...")

if tamanho_estimado_mb <= LIMITE_DATABASE_MB and count_editais <= LIMITE_EDITAIS:
    custo_estimado = 0.0
    tier = "FREE"
    print(f"    Tier atual: {tier}")
    print(f"    Custo mensal: ${custo_estimado:.2f}")
    print(f"    [OK] Dentro do free tier!")
else:
    # Se ultrapassar, estimar Pro plan
    tier = "PRO (estimado)"
    custo_base = 25.0  # Pro plan base

    # Database overage
    database_overage_gb = max(0, (tamanho_estimado_mb - LIMITE_DATABASE_MB) / 1024)
    custo_database = database_overage_gb * 0.125  # $0.125/GB

    custo_estimado = custo_base + custo_database

    print(f"    Tier estimado: {tier}")
    print(f"    Custo base Pro: ${custo_base:.2f}")
    print(f"    Database overage: ${custo_database:.2f}")
    print(f"    TOTAL ESTIMADO: ${custo_estimado:.2f}/mes")

    if custo_estimado > 50:
        print(f"    [ALERTA MAXIMO] ULTRAPASSOU LIMITE DE $50!")
        print(f"    [ACAO OBRIGATORIA] PARAR TODAS AS INSERCOES!")

# 6. SALVAR LOG
print("\n[6] Salvando log de monitoramento...")

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

log_data = {
    "timestamp": datetime.now().isoformat(),
    "count_editais": count_editais,
    "tamanho_estimado_mb": round(tamanho_estimado_mb, 2),
    "percent_database": round(percent_db, 2),
    "tier": tier,
    "custo_estimado_usd": round(custo_estimado if 'custo_estimado' in locals() else 0.0, 2),
    "status": "OK" if tamanho_estimado_mb < LIMITE_DATABASE_MB * ALERTA_80_PERCENT else "AVISO"
}

log_file = log_dir / f"usage_{datetime.now().strftime('%Y-%m-%d')}.json"

# Append ao log do dia
logs_hoje = []
if log_file.exists():
    with open(log_file, 'r', encoding='utf-8') as f:
        logs_hoje = json.load(f)

logs_hoje.append(log_data)

with open(log_file, 'w', encoding='utf-8') as f:
    json.dump(logs_hoje, f, indent=2, ensure_ascii=False)

print(f"    [OK] Log salvo: {log_file}")

# 7. RESUMO FINAL
print("\n" + "=" * 60)
print("RESUMO DO FREIO DE SEGURANCA")
print("=" * 60)
print(f"Editais no banco: {count_editais} / {LIMITE_EDITAIS}")
print(f"Database estimado: {tamanho_estimado_mb:.1f} MB / {LIMITE_DATABASE_MB} MB")
print(f"Tier: {'FREE' if tamanho_estimado_mb <= LIMITE_DATABASE_MB else 'PRO'}")
print(f"Custo estimado: ${log_data['custo_estimado_usd']:.2f}/mes")

if log_data['custo_estimado_usd'] > 0:
    print(f"\n[AVISO] Custo projetado detectado!")
    if log_data['custo_estimado_usd'] > 50:
        print(f"[ALERTA MAXIMO] Ultrapassou limite de $50 USD!")
        print(f"[ACAO] Execute: python desligar_supabase.py")
else:
    print(f"\n[OK] Tudo dentro do free tier - sem custos!")

print("=" * 60)
