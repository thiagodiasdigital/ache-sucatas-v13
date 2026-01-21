# Projeto Ache Sucatas - Instruções para Claude

## Sobre o Usuário (Thiago)

- **Nível de experiência**: Iniciante em desenvolvimento
- **Consideração importante**: Tenho TDAH

## Como Claude deve responder

1. **Explicações detalhadas**: Além de ser tecnicamente correto, explicar o "porquê" das coisas, não apenas o "como"

2. **Passo a passo**: Sempre que possível, dividir tarefas em etapas numeradas e claras

3. **Evitar assumir conhecimento prévio**: Explicar termos técnicos quando usados pela primeira vez

4. **Foco e clareza**: Manter respostas organizadas e evitar muitas tangentes de uma vez

5. **Resumos**: Para tarefas longas, começar com um resumo do que será feito

## Estrutura do Projeto

- **Frontend**: React + TypeScript + Vite (pasta `frontend/`)
- **Backend**: Supabase (PostgreSQL)
- **Componentes UI**: shadcn/ui
- **Mapas**: MapLibre GL com react-map-gl

## Comandos úteis

```bash
# Iniciar servidor de desenvolvimento
cd frontend && npm run dev

# Build de produção
cd frontend && npm run build
```

## Domínios Validados para link_leiloeiro

Os seguintes domínios foram validados manualmente pelo usuário em 2026-01-21 e NÃO devem ser considerados falsos positivos no saneamento de links:

- `bllcompras.com` - Portal de compras públicas
- `campinas.sp.gov.br` - Portal governo de Campinas
- `atende.net` - Plataforma de atendimento (pomerode, janiopolis, consorciojacui, santarosadosul, terraroxa)
- `sobradinho-rs.com.br` - Site do município

Esses domínios estão configurados na whitelist em `sanitize_invalid_links.py`.
