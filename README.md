# ClipsGrind

SaaS que corta lives e VODs (YouTube, Twitch, Kick) automaticamente em Shorts: detecta os picos do chat, corta em 9:16, legenda e gera título, descrição e hashtags, e pode postar sozinho nas contas conectadas.

## Estado atual

Protótipo de **interface** (front-end apenas, sem backend). Tudo roda num único arquivo de design:

- `project/Main.dc.html` — o app inteiro: login/cadastro, painel, processamento, resultados, editor estilo CapCut (vídeo, áudio e trilha extra com dividir/excluir/desfazer), histórico, automação, planos/checkout, configurações, suporte, indicações, tema claro/escuro.
- `project/canvas.json` — índice do canvas.
- `project/Processing.dc.html`, `project/Results.dc.html` — rascunhos antigos de telas.

## Próximos passos

- **Motor** (separado da interface): download → transcrição → detecção de pico de chat → corte com ffmpeg → legenda → título/descrição/hashtags → postagem. Planejado em Python + ffmpeg + n8n.
- **Front real**: portar a interface para Next.js + Tailwind + shadcn (`components/ui`).
- **Dados e segurança**: Supabase (auth, banco com RLS), tokens OAuth guardados criptografados, pagamento via Stripe/Mercado Pago com validação de webhook.
