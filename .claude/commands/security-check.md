# Security Check — Auditoria de Segurança

Realize uma auditoria de segurança completa no projeto NF Entrada. Analise os arquivos em $ARGUMENTS (ou em todo o projeto se não especificado).

## 1. Credenciais Expostas

Procure por secrets hardcoded nos arquivos Python e de configuração:

```bash
grep -rn "password\s*=\|api_key\s*=\|token\s*=\|secret\s*=" --include="*.py" --include="*.toml" --include="*.env" .
```

Verifique também padrões de URL com credenciais embutidas:

```bash
grep -rn "postgresql://.*:.*@\|mysql://.*:.*@" --include="*.py" .
```

## 2. Arquivos Sensíveis no Git

Confirme que o `.gitignore` exclui os arquivos críticos:

```bash
cat .gitignore
git status --short
```

Verifique se `secrets.toml` ou `historico.db` aparecem como tracked:

```bash
git ls-files | grep -E "secrets\.toml|historico\.db|\.env"
```

## 3. Queries SQL contra Injection

Procure por f-strings ou concatenação em queries SQL (padrão inseguro):

```bash
grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE\|f'.*SELECT\|f'.*INSERT" --include="*.py" .
grep -rn "\.format(.*SELECT\|% .*SELECT" --include="*.py" .
```

Confirme uso de placeholders seguros (`%s`):

```bash
grep -rn "%s" src/database.py src/database_pg.py
```

## 4. Debug e Configurações de Produção

```bash
grep -rn "debug\s*=\s*True\|DEBUG\s*=\s*True" --include="*.py" .
grep -rn "st\.write.*password\|st\.write.*token\|st\.write.*secret" --include="*.py" .
```

## 5. Validação de Uploads

Verifique se os uploads de arquivo têm validação de tipo e tamanho:

```bash
grep -n "file_uploader\|maxUploadSize\|type=" app.py
```

## 6. Session State e Cache Streamlit

Procure por dados sensíveis em cache ou session_state:

```bash
grep -rn "st\.session_state\|st\.cache" --include="*.py" . | grep -i "password\|token\|secret\|key"
```

## Relatório Final

Gere um relatório estruturado com:

### Criticos (corrigir antes do deploy)
- Liste cada problema com arquivo:linha e descrição

### Avisos (revisar)
- Liste melhorias recomendadas

### OK
- Liste o que está correto e seguro

### Resumo
- Status geral: PRONTO / ATENÇÃO / BLOQUEADO para deploy
