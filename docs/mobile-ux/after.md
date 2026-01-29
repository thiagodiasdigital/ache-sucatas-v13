# Mobile UX After - Ache Sucatas

## Informações da Análise

- **Data:** 2026-01-29
- **URL Testada:** _Aguardando preview URL do PR_
- **Dispositivo:** Mobile (emulado)
- **Ferramenta:** Lighthouse Mobile

## Comando para Rodar Lighthouse

```bash
# Substitua TARGET_URL pela URL de preview do PR
npx lighthouse ${TARGET_URL}/dashboard --preset=mobile --output=html --output-path=./lighthouse-after.html
```

## Métricas After

> **NOTA:** Preencher após deploy do PR e execução do Lighthouse.

| Métrica | Baseline | After | Melhoria |
|---------|----------|-------|----------|
| LCP (Largest Contentful Paint) | _pendente_ | _pendente_ | - |
| CLS (Cumulative Layout Shift) | _pendente_ | _pendente_ | - |
| INP (Interaction to Next Paint) | _pendente_ | _pendente_ | - |
| TTFB (Time to First Byte) | _pendente_ | _pendente_ | - |
| Performance Score | _pendente_ | _pendente_ | - |

## Mudanças Implementadas

### 1. Overflow Horizontal Corrigido
- **Antes:** Filter bar com 10+ elementos em linha causava overflow
- **Depois:** Mobile usa bottom sheet para filtros, desktop mantém layout
- **Arquivos:** `Header.tsx`, `MobileFilterSheet.tsx`

### 2. Lazy Loading de Imagens
- **Antes:** 20 imagens carregando simultaneamente
- **Depois:** `loading="lazy"` + `decoding="async"` + `aspect-ratio` (previne CLS)
- **Arquivo:** `AuctionCardGrid.tsx`

### 3. N+1 Queries Eliminadas
- **Antes:** `useLotes()` chamado por cada card (20 queries/página)
- **Depois:** Preview usa `objeto_resumido`; lotes completos só no modal
- **Arquivo:** `AuctionCardGrid.tsx`
- **Impacto:** ~20 queries a menos por page load

### 4. Bottom Sheet no Mobile
- **Antes:** Drawer lateral (`side="right"`) em todas as telas
- **Depois:** `side="bottom"` no mobile, `side="right"` no desktop
- **Arquivos:** `LotesModal.tsx`, `MobileFilterSheet.tsx`

### 5. Touch Targets Adequados
- **Antes:** Botões com `py-1.5` (~24px)
- **Depois:** `min-h-[44px]` em todos os botões interativos
- **Arquivo:** `AuctionCardGrid.tsx`

## Screenshots After

> Adicionar screenshots do comportamento no mobile após as correções:
> 1. Header sem overflow horizontal
> 2. Botão de filtros com badge de contagem
> 3. Filtros em bottom sheet
> 4. Detail view em bottom sheet

## Checklist de Verificação

- [ ] Zero overflow horizontal no mobile (<768px)
- [ ] Filtros funcionam no bottom sheet mobile
- [ ] Filtros funcionam normalmente no desktop
- [ ] Detail view abre como bottom sheet no mobile
- [ ] Detail view abre como drawer lateral no desktop
- [ ] Imagens carregam com lazy loading
- [ ] Botões têm área de toque >= 44px
- [ ] N+1 queries eliminadas (verificar DevTools > Network)
