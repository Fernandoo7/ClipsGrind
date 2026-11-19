# ClipsGrind — instruções para o Claude

- A interface vive em `project/Main.dc.html` (canvas Design, arquivo único) e é publicada no Artifact
  https://claude.ai/artifact/MPbDejbWHDgrk2kGWyiujD (publicar com `root` = pasta raiz deste repo).
- **Sempre que a interface mudar:** publicar o Artifact **e** fazer commit + push para `main` deste repo, na mesma rodada.
- Por enquanto o trabalho é só de interface (front-end). Motor (Python + ffmpeg + n8n) e backend ficam para depois.
- Formato `.dc.html`: `<sc-if>` sem `invert`, sem `set-inner-html`; holes `{{ }}` são só caminhos, nada de expressões.
- Tema: cores via variáveis `--cg-*` no `:root` / `.theme-light`. O editor de clipes fica sempre escuro e usa `editorAccent`/`rawAccent`.
- Antes de publicar: balancear `sc-if`/`sc-for`, rodar `renderVals()` em Node e conferir prints dos dois temas.
