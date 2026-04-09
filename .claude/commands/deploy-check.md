# Deploy Check — Verificação Pré-Deploy Streamlit Cloud

Verifique se o projeto NF Entrada está pronto para deploy no Streamlit Community Cloud.

## 1. Sintaxe Python

Verifique se todos os arquivos `.py` têm sintaxe válida:

```bash
find . -name "*.py" -not -path "*/__pycache__/*" | while read f; do
  python -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" 2>&1 && echo "OK: $f" || echo "ERRO: $f"
done
```

## 2. Dependências

Confirme que `requirements.txt` existe e contém os pacotes essenciais:

```bash
cat requirements.txt
```

Verifique se os pacotes principais estão instalados no ambiente atual:

```bash
python -c "import streamlit, pandas, psycopg2, fpdf; print('Dependencias OK')" 2>&1
```

## 3. Arquivos Sensíveis — NÃO devem ir para o GitHub

```bash
git ls-files | grep -E "secrets\.toml|historico\.db|\.env|backup.*\.sql"
```

O resultado deve ser VAZIO. Se aparecer qualquer arquivo, PARE — não faça o push.

Confirme que o `.gitignore` está correto:

```bash
grep -E "secrets\.toml|historico\.db|\.env" .gitignore
```

## 4. Git Status

```bash
git status --short
git log --oneline -5
```

Verifique:
- Há arquivos modificados que precisam de commit antes do deploy?
- O branch `main` está atualizado?

## 5. Estrutura de Pastas Esperada

O Streamlit Cloud precisa encontrar:

```bash
test -f app.py && echo "app.py OK" || echo "ERRO: app.py nao encontrado"
test -f requirements.txt && echo "requirements.txt OK" || echo "ERRO: requirements.txt nao encontrado"
test -d src && echo "src/ OK" || echo "ERRO: pasta src/ nao encontrada"
```

## 6. Variáveis de Ambiente Esperadas

O app precisa de `DATABASE_URL` configurado nos secrets do Streamlit Cloud:

```bash
grep -rn "st\.secrets" --include="*.py" . | grep -v "^Binary"
```

Liste todas as chaves esperadas em `st.secrets` para configurar no painel do Streamlit Cloud.

## 7. Configuração de Upload

Confirme o limite de upload configurado no bat de inicialização:

```bash
grep "maxUploadSize" iniciar_servidor.bat iniciar.bat 2>/dev/null
```

> No Streamlit Cloud, o limite padrão é 200MB. Se precisar de mais, adicione `.streamlit/config.toml` com `[server] maxUploadSize = 1024`.

## Relatório Final

### Status de cada verificação
- [ ] Sintaxe Python: OK / ERRO
- [ ] requirements.txt: OK / FALTANDO
- [ ] Secrets fora do git: OK / RISCO
- [ ] .gitignore correto: OK / INCOMPLETO
- [ ] Estrutura de pastas: OK / PROBLEMA
- [ ] Variáveis documentadas: OK / PENDENTE

### Veredicto Final
- **PRONTO** para deploy
- **ATENÇÃO** — itens a corrigir antes
- **BLOQUEADO** — problemas críticos impedem o deploy
