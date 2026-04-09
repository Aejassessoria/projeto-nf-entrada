# Test Connection — Testar Conectividade do Banco de Dados

Testa se o banco de dados (Neon ou Supabase) está acessível e com as tabelas necessárias criadas corretamente.

## Uso

```
/test-connection           → testa o banco configurado em secrets.toml
/test-connection <URL>     → testa uma URL específica (ex: URL do Supabase)
```

## Verificar Conexão

```bash
python -c "
import sys

# URL vem do argumento ou do secrets.toml
url_arg = '$ARGUMENTS'.strip()

if url_arg:
    db_url = url_arg
    print(f'Testando URL fornecida...')
else:
    try:
        with open('.streamlit/secrets.toml') as f:
            for line in f:
                if 'DATABASE_URL' in line:
                    db_url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                    break
        print('Testando banco configurado em secrets.toml...')
    except Exception as e:
        print(f'ERRO: Nao foi possivel ler secrets.toml: {e}')
        sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    print('Conexao estabelecida com sucesso!')

    # Verifica tabelas
    cur.execute(\"\"\"
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    \"\"\")
    tabelas = [r['table_name'] for r in cur.fetchall()]
    print(f'Tabelas encontradas: {tabelas}')

    # Conta registros
    for t in ['classificacoes', 'regras_ncm', 'clientes']:
        if t in tabelas:
            cur.execute(f'SELECT COUNT(*) as total FROM {t}')
            n = cur.fetchone()['total']
            print(f'  {t}: {n} registros')
        else:
            print(f'  {t}: TABELA NAO ENCONTRADA')

    conn.close()
    print()
    print('STATUS: OK — banco operacional')

except psycopg2.OperationalError as e:
    print(f'ERRO de conexao: {e}')
    print('Verifique: URL correta? Banco ativo? SSL habilitado?')
    sys.exit(1)
except Exception as e:
    print(f'ERRO inesperado: {e}')
    sys.exit(1)
"
```

## Relatório Final

Informe:
- Se a conexão foi estabelecida com sucesso
- Quais tabelas existem no banco
- Quantidade de registros em cada tabela
- Status final: **OPERACIONAL** / **ERRO DE CONEXÃO** / **TABELAS FALTANDO**

Se houver erro, sugira os próximos passos para diagnóstico.
