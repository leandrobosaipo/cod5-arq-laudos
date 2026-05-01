# cod5-arq-laudos

Painel público de pendências de arquitetura com classificação operacional, recortes de evidência e filtros por disciplina/complexidade.

## Estrutura
- `public/`: site estático publicado no Cloudflare Pages
- `scripts/`: script de geração do dashboard

## Gerar dashboard local
```bash
cd /Users/leandrobosaipo/Projetos/Arq
python3 _trabalho/scripts/gerar_dashboard_visual.py
cd _trabalho/pages-public
python3 -m http.server 8765 --bind 127.0.0.1
```

## Deploy Cloudflare Pages
```bash
cd /Users/leandrobosaipo/Projetos/Arq/cod5-arq-laudos
npx wrangler login
npx wrangler pages project create cod5-arq-laudos
npx wrangler pages deploy public --project-name cod5-arq-laudos --branch main
```
