# Ache Sucatas - Frontend (Semana 1)

Dashboard DaaS para visualização de leilões públicos do Brasil.

## Stack Técnica

- **React 19** + **Vite** + **TypeScript**
- **Tailwind CSS 3** + Componentes UI customizados (estilo Shadcn)
- **React Router DOM v6** - Roteamento
- **TanStack Query v5** - Data fetching e cache
- **Supabase** - Backend (Auth, RLS, RPC)
- **Lucide React** - Ícones

## Estrutura do Projeto

```
frontend/
├── public/
│   └── _redirects          # Configuração Cloudflare Pages
├── src/
│   ├── components/
│   │   ├── ui/             # Componentes base (Button, Card, Input, etc)
│   │   ├── AuctionCard.tsx
│   │   ├── AuctionCardSkeleton.tsx
│   │   ├── AuctionGrid.tsx
│   │   ├── Layout.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── TopFilterBar.tsx
│   ├── contexts/
│   │   └── AuthContext.tsx
│   ├── hooks/
│   │   └── useAuctions.ts
│   ├── lib/
│   │   ├── supabase.ts
│   │   └── utils.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Login.tsx
│   │   └── Perfil.tsx
│   ├── types/
│   │   └── database.ts
│   ├── App.tsx
│   ├── index.css
│   └── main.tsx
├── supabase/
│   ├── supabase_infrastructure.sql  # Schema completo
│   └── insert_municipios.sql        # Dados IBGE
└── package.json
```

## Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do frontend:

```env
VITE_SUPABASE_URL=https://seu-projeto.supabase.co
VITE_SUPABASE_ANON_KEY=sua-anon-key
```

### 2. Configuração do Supabase

Execute os scripts SQL no Supabase SQL Editor:

1. `supabase/supabase_infrastructure.sql` - Cria schemas, tabelas, views e RPCs
2. `supabase/insert_municipios.sql` - Popula tabela de municípios IBGE

### 3. Instalação e Execução

```bash
# Instalar dependências
npm install

# Desenvolvimento
npm run dev

# Build de produção
npm run build

# Preview do build
npm run preview
```

## Rotas

| Rota | Acesso | Descrição |
|------|--------|-----------|
| `/login` | Público | Tela de login/cadastro |
| `/dashboard` | Privado | Grid de leilões com filtros |
| `/perfil` | Privado | Informações do usuário |

## Funcionalidades

### Dashboard
- Grid responsivo de cards de leilões
- Filtros por UF, Cidade e Valor Mínimo
- Estatísticas em tempo real
- State management via URL (Search Params)

### AuctionCard
- Tag SUCATA: Verde (#10B981)
- Tag DOCUMENTADO: Azul (#3B82F6)
- Valor só aparece se > 0
- Botões "Ver Edital" (PNCP) e "Dar Lance" (Leiloeiro)

### Autenticação
- Login/Cadastro via Supabase Auth
- Rotas protegidas com redirecionamento
- Contexto de autenticação global

## Deploy (Cloudflare Pages)

1. Conecte o repositório no Cloudflare Pages
2. Configure:
   - Build command: `npm run build`
   - Build output: `dist`
3. Adicione as variáveis de ambiente
4. O arquivo `_redirects` já configura SPA mode

## Governança de Dados

- **RLS ativo** em todas as tabelas
- **Auditoria** de consumo via `audit.consumption_logs`
- **RPC auditada** `pub.fetch_auctions_audit` registra todos os acessos
- Usuários só veem dados com `publication_status = 'published'`

## Princípios do Projeto

- **Nenhuma IA no produto final** - Sistema 100% baseado em regras
- **Nenhuma cor vermelha** - Paleta azul/verde/neutro
- **Governança rígida** - Logs de auditoria obrigatórios

---

Desenvolvido para **Ache Sucatas** - DaaS Platform
