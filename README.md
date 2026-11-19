# ClipsGrind

SaaS que corta lives e VODs (YouTube, Twitch, Kick) automaticamente em Shorts: detecta os picos do chat, corta em 9:16, legenda e gera título, descrição e hashtags, e pode postar sozinho nas contas conectadas.

## Estado atual

Protótipo de **interface** (front-end apenas, sem backend). Tudo roda num único arquivo de design:

- `project/Main.dc.html` — o app inteiro: login/cadastro, painel, processamento, resultados, editor estilo CapCut (vídeo, áudio e trilha extra com dividir/excluir/desfazer), histórico, automação, planos/checkout, configurações, suporte, indicações, tema claro/escuro.
- `project/canvas.json` — índice do canvas.
- `project/Processing.dc.html`, `project/Results.dc.html` — rascunhos antigos de telas.

## Motor (gerar clipes sem PC)

Roda no GitHub Actions, nos servidores do GitHub — dá pra disparar pelo celular.

1. No repositório, abra **Actions → Gerar clipes → Run workflow**.
2. Cole o link da live/VOD, escolha quantos clipes e o tamanho, e clique em **Run workflow**.
3. Em poucos minutos a execução fica verde. Abra-a: o **resumo** mostra nota, trecho e título de cada clipe,
   e o pacote **clipes** (no fim da página) traz os `.mp4` 1080×1920 e um `.txt` com título, descrição e hashtags.

Como funciona: lê o chat do replay e acha os picos de mensagens (com peso extra para "KKKK", "?!", "clipa"…);
sem chat, usa os picos de volume do áudio. Baixa **só** os trechos escolhidos, transcreve (faster-whisper),
monta o vertical com fundo desfocado, gancho no topo e legenda palavra a palavra.

### Configurações opcionais (Settings → Secrets and variables → Actions)

| Secret | Para quê |
|---|---|
| `LLM_API_KEY` | Títulos/descrições escritos por IA. Chave grátis em aistudio.google.com (Gemini). Sem ela, o texto é gerado da transcrição. |
| `YTDLP_COOKIES` | Conteúdo de um `cookies.txt` da sua conta do YouTube. Necessário quando o YouTube pedir "confirme que não é um robô" para o servidor. |

Testes: `cd engine && python -m pytest -q tests` · Rodar local: `python -m clipsgrind.cli LINK_OU_VIDEO`.

## Próximos passos

- **Motor**: postagem automática no YouTube (OAuth) e ligação com a interface.
- **Front real**: portar a interface para Next.js + Tailwind + shadcn (`components/ui`).
- **Dados e segurança**: Supabase (auth, banco com RLS), tokens OAuth guardados criptografados, pagamento via Stripe/Mercado Pago com validação de webhook.
