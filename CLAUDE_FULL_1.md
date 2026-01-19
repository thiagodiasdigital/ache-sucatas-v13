# CLAUDE_FULL_1.md - Estado Atual e Frontend React

> **Ultima atualizacao:** 2026-01-18 22:00 UTC
> **Versao atual:** V11 + Auditor V14.2 + CI + Frontend React (Semana 2)
> **Status:** 100% Operacional

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| **1** | **CLAUDE_FULL_1.md** (este) | Estado atual, Frontend React, Hotfixes |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico |

**Resumo rapido:** [CLAUDE.md](./CLAUDE.md)

---

## Visao Geral

**ACHE SUCATAS DaaS** (Data as a Service) - Sistema automatizado de coleta e analise de editais de leilao publico do Brasil.

### O que o sistema faz

1. **Coleta** - Busca editais de leilao na API PNCP (Portal Nacional de Contratacoes Publicas)
2. **Download** - Baixa PDFs dos editais para Supabase Storage (nuvem)
3. **Extracao** - Extrai informacoes estruturadas dos PDFs (titulo, data, valores, itens, leiloeiro)
4. **Persistencia** - Armazena metadados no Supabase PostgreSQL
5. **Automacao** - Executa 3x/dia via GitHub Actions (sem necessidade de PC local)
6. **Notificacao** - Envia email automatico quando o workflow falha
7. **Validacao** - CI automatico com lint e testes em cada push/PR
8. **Frontend React** - Dashboard multi-view (Grid/Mapa/Calendario) com sistema de notificacoes

### Escopo do Projeto

**Objetivo de Negocio:** Criar um banco de dados estruturado de leiloes publicos do Brasil, focando em:
- Veiculos e maquinas agricolas inserviveis
- Sucatas de veiculos
- Bens moveis de orgaos publicos

**Publico-Alvo:**
- Centro de desmanche automotivo
- Compradores de leiloes publicos
- Auto pecas usadas

---

## Metricas Atuais

| Metrica | Valor |
|---------|-------|
| Editais no banco (PostgreSQL) | 294 |
| Editais no Storage (PDFs) | 698+ |
| Workflows de coleta executados | 3 (100% sucesso) |
| Workflows de CI executados | 4 (100% sucesso) |
| Ultima execucao coleta | 2026-01-17 08:17 UTC |
| Ultima coleta historica | 2026-01-18 10:52 UTC (268 novos) |
| Testes unitarios | 98 (100% passando) |

---

## Funcionalidades Implementadas

| Funcionalidade | Status | Data |
|----------------|--------|------|
| Coleta automatica de editais | Operacional | 2026-01-16 |
| Upload para Supabase Storage | Operacional | 2026-01-16 |
| Persistencia no PostgreSQL | Operacional | 2026-01-16 |
| Extracao de dados dos PDFs | Operacional | 2026-01-16 |
| Execucao agendada 3x/dia | Operacional | 2026-01-16 |
| Notificacao de falha por email | Operacional | 2026-01-17 |
| CI com ruff + pytest (98 testes) | Operacional | 2026-01-17 |
| Coleta historica 30 dias | Operacional | 2026-01-18 |
| **Frontend React - Semana 2** | Operacional | 2026-01-18 |
| Dashboard multi-view (Grid/Mapa/Calendario) | Operacional | 2026-01-18 |
| Sistema de notificacoes Supabase Realtime | Operacional | 2026-01-18 |
| Filtros salvos do usuario (alertas) | Operacional | 2026-01-18 |
| Visualizacao em mapa com MapLibre GL | Operacional | 2026-01-18 |
| Atalhos de teclado (G/M/C) | Operacional | 2026-01-18 |
| Clusterizacao de pins (Supercluster) | Operacional | 2026-01-18 |

---

## Frontend React (Semana 2)

### Visao Geral

| Propriedade | Valor |
|-------------|-------|
| Framework | React 19 + Vite 7 |
| Linguagem | TypeScript |
| Estilizacao | Tailwind CSS 4 + Shadcn/UI |
| Mapa | MapLibre GL JS + react-map-gl |
| Calendario | react-day-picker |
| Estado | TanStack React Query |
| Realtime | Supabase Realtime |
| Diretorio | `frontend/` |

### Estrutura de Arquivos

```
frontend/
├── src/
│   ├── components/
│   │   ├── AuctionCard.tsx          # Card de leilao
│   │   ├── AuctionDrawer.tsx        # Drawer lateral (calendario)
│   │   ├── AuctionGrid.tsx          # Grid de leiloes
│   │   ├── CalendarView.tsx         # Visualizacao em calendario
│   │   ├── Layout.tsx               # Layout principal
│   │   ├── MapView.tsx              # Visualizacao em mapa
│   │   ├── ModeSwitcher.tsx         # Alternador Grid/Mapa/Calendario
│   │   ├── NotificationBell.tsx     # Sino de notificacoes
│   │   ├── TopFilterBar.tsx         # Barra de filtros
│   │   └── ui/                      # Componentes Shadcn
│   ├── contexts/
│   │   ├── AuthContext.tsx          # Autenticacao
│   │   └── NotificationContext.tsx  # Notificacoes Realtime
│   ├── hooks/
│   │   ├── useAuctions.ts           # Busca leiloes
│   │   ├── useNotifications.ts      # Hook de notificacoes
│   │   ├── useUserFilters.ts        # Filtros salvos
│   │   └── useViewMode.ts           # Modo de visualizacao
│   ├── pages/
│   │   ├── Dashboard.tsx            # Pagina principal
│   │   └── Login.tsx                # Login
│   ├── lib/
│   │   ├── supabase.ts              # Cliente Supabase
│   │   └── utils.ts                 # Utilitarios
│   └── types/
│       └── database.ts              # Tipos TypeScript
├── supabase/
│   └── week2_schema.sql             # Schema SQL de notificacoes
└── package.json
```

### Componentes Principais

#### ModeSwitcher
| Propriedade | Descricao |
|-------------|-----------|
| Modos | Grid, Mapa, Calendario |
| Sincronizacao | URL param `view` + localStorage |
| Atalhos | G (Grid), M (Mapa), C (Calendario) |

#### MapView
| Propriedade | Descricao |
|-------------|-----------|
| Biblioteca | MapLibre GL JS + react-map-gl |
| Tiles | OpenStreetMap |
| Pins | Emerald (#10B981) para Sucata, Royal Blue (#3B82F6) para Documentado |
| Clusterizacao | Supercluster com cores dinamicas |
| UF Lock | Mapa so renderiza com UF selecionado |

#### CalendarView
| Propriedade | Descricao |
|-------------|-----------|
| Biblioteca | react-day-picker |
| Indicadores | Dots verdes (Sucata) e azuis (Documentado) |
| Interacao | Clique no dia abre Drawer lateral |
| Locale | ptBR (portugues) |

#### NotificationBell
| Propriedade | Descricao |
|-------------|-----------|
| Badge | Contador de nao lidas (Emerald #10B981) |
| Animacao | `animate-ping` quando ha novos itens |
| Dropdown | Ultimas 20 notificacoes com ScrollArea |
| Realtime | Atualiza via Supabase subscription |

### Schema SQL de Notificacoes

**Tabelas:**
- `pub.user_filters` - Filtros salvos pelo usuario (alertas)
- `pub.notifications` - Notificacoes geradas por match

**Trigger de Match-Making:**
```sql
CREATE TRIGGER trg_check_matches_on_insert
AFTER INSERT ON raw.leiloes
FOR EACH ROW
EXECUTE FUNCTION audit.fn_match_and_notify();
```

### Hooks do Frontend

```typescript
// useNotifications
{
  notifications: Notification[]
  unreadCount: number
  markAsRead: (id) => void
  markAllAsRead: () => void
}

// useUserFilters
{
  filters: UserFilter[]
  saveFilter: (label, params) => Promise
  deleteFilter: (id) => Promise
  toggleFilter: (id, active) => Promise
}

// useViewMode
{
  viewMode: 'grid' | 'map' | 'calendar'
}
```

### Dependencias

```json
{
  "react": "^19.1.0",
  "react-router-dom": "^7.5.1",
  "@supabase/supabase-js": "^2.50.0",
  "@tanstack/react-query": "^5.75.5",
  "maplibre-gl": "^5.5.0",
  "react-map-gl": "^8.0.4",
  "react-day-picker": "^9.7.0",
  "lucide-react": "^0.511.0",
  "tailwindcss": "^4.1.5"
}
```

### Comandos

```bash
cd frontend && npm install   # Instalar
npm run dev                  # Dev em localhost:5173
npm run build                # Build producao
```

### Configuracao

1. Criar `frontend/.env`:
```env
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=sua_anon_key_aqui
```

2. Executar `frontend/supabase/week2_schema.sql` no Supabase

3. Habilitar Realtime:
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE pub.notifications;
```

---

## Hotfix V14.2 - Correcoes de Bugs (2026-01-17)

| Bug | Severidade | Arquivo | Correcao |
|-----|------------|---------|----------|
| #9 | ALTA | supabase_repository.py | AttributeError em listar_tags_disponiveis() |
| #1 | CRITICA | streamlit_app.py | Coluna link_leiloeiro com links clicaveis |
| #2 | CRITICA | cloud_auditor_v14.py | extrair_nome_leiloeiro() com 9 padroes regex |
| #3 | ALTA | streamlit_app.py | Corrigido "R$ nan" |
| #5 | ALTA | supabase_repository.py | listar_tags_disponiveis() |
| #6 | MEDIA | cloud_auditor_v14.py | extrair_quantidade_itens() melhorada |
| #7 | MEDIA | supabase_repository.py | _validar_e_corrigir_uf() |
| #8 | BAIXA | cloud_auditor_v14.py | padronizar_modalidade() |

### Novas Funcoes

```python
# supabase_repository.py
def listar_tags_disponiveis() -> List[str]
def _extrair_uf_de_texto(texto: str) -> Optional[str]
def _validar_e_corrigir_uf(uf_raw: str, municipio: str, orgao: str) -> str

# cloud_auditor_v14.py
def padronizar_modalidade(modalidade: str) -> str
```

---

## Commits Recentes

| Hash | Data | Descricao |
|------|------|-----------|
| `bf5d431` | 2026-01-18 | fix: Resolve React DOM reconciliation error |
| `dfe15df` | 2026-01-18 | feat: Week 2 realtime & geo-intel enhancements |
| `fa6f18f` | 2026-01-18 | feat: Add Week 2 frontend - notifications, multi-view |
| `9839b3b` | 2026-01-18 | feat: Add historical collection script |
| `bb47f2f` | 2026-01-17 | fix: AttributeError in listar_tags_disponiveis |
| `e5343be` | 2026-01-17 | fix: Resolve 8 critical bugs |

---

> Proximo: [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) - Arquitetura e Fluxos
