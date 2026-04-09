# Code Review — Revisão de Qualidade de Código

Revise o código em $ARGUMENTS para qualidade, performance e boas práticas. Se não especificado, revise `app.py` e todos os arquivos em `src/`.

## 1. Leitura dos Arquivos

Leia os arquivos relevantes:

```bash
find ${ARGUMENTS:-.} -name "*.py" -not -path "*/__pycache__/*" | sort
```

## 2. Checklist de Qualidade

### Legibilidade
- Nomes de variáveis e funções são descritivos?
- Funções fazem uma única coisa?
- Há lógica complexa sem comentário explicativo?
- Constantes estão nomeadas (sem magic numbers)?

### Performance
- Há operações de banco dentro de loops?
- DataFrames Pandas sendo copiados desnecessariamente?
- Consultas que poderiam ser feitas em batch mas são feitas uma a uma?

Procure padrões problemáticos:

```bash
grep -n "for.*in.*:\|while " src/*.py app.py | head -40
```

### Tratamento de Erros
- `except:` sem tipo específico (captura tudo, perigoso)?
- Erros sendo silenciados sem log?

```bash
grep -rn "except:" --include="*.py" .
grep -rn "except Exception:" --include="*.py" .
```

### Streamlit — Padrões Específicos
- `st.cache_data` ou `st.cache_resource` usados corretamente?
- Session state inicializado antes de usar?
- Operações pesadas dentro do fluxo principal sem cache?

```bash
grep -n "st\.cache\|@st\.cache" app.py src/*.py
grep -n "st\.session_state" app.py src/*.py | head -20
```

### Duplicação de Código
- Há blocos repetidos que poderiam ser função?
- Imports duplicados?

```bash
grep -rn "^import\|^from" --include="*.py" . | sort | uniq -d
```

### Conexões de Banco
- Conexões são fechadas corretamente (uso de `with` ou `.close()`)?

```bash
grep -n "get_connection\|\.close()\|with.*conn" src/database.py src/database_pg.py
```

## Relatório Final

Para cada arquivo revisado, liste:

### Problemas Críticos
- `arquivo.py:linha` — descrição + sugestão de correção

### Melhorias Recomendadas
- `arquivo.py:linha` — descrição

### Pontos Positivos
- O que está bem implementado

### Nota de Qualidade
- Score: X/10 com justificativa breve
