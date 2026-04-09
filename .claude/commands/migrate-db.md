# Migrate DB — Migrar Dados do Neon para Supabase

Exporta todos os dados do banco Neon (origem) e importa no Supabase (destino). Use apenas quando o ambiente de teste estiver 100% validado.

## AVISOS IMPORTANTES

> 1. Este comando copia dados — NÃO apaga o banco de origem (Neon continua intacto)
> 2. Execute somente após validar o ambiente Supabase com `/test-connection`
> 3. Faça backup com `/backup-db` ANTES de executar
> 4. Confirme com o usuário a URL de DESTINO antes de prosseguir

## Uso

```
/migrate-db <URL_SUPABASE_DESTINO>
```

Exemplo:
```
/migrate-db postgresql://postgres.xyz:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

## Passo 1 — Confirmar Origem e Destino

```bash
python -c "
# Origem: secrets.toml
with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            origem = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")

destino = '$ARGUMENTS'.strip()

def safe_url(url):
    parts = url.split('@')
    cred = parts[0].split(':')
    return cred[0] + ':***@' + parts[1] if '@' in url and len(cred) > 1 else url

print('ORIGEM (Neon):', safe_url(origem))
print('DESTINO (Supabase):', safe_url(destino) if destino else 'NAO INFORMADO')
print()
if not destino:
    print('ERRO: Informe a URL do Supabase como argumento.')
    print('Uso: /migrate-db <URL_SUPABASE>')
"
```

**Peça confirmação explícita do usuário antes de continuar.**

## Passo 2 — Backup da Origem (segurança extra)

```bash
BACKUP_FILE="pre_migration_$(date +%Y%m%d_%H%M).sql"
ORIGEM=$(python -c "
with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            print(line.split('=', 1)[1].strip().strip('\"').strip(\"'\"))
")

pg_dump "$ORIGEM" --data-only --no-owner --inserts \
  -t classificacoes -t regras_ncm -t clientes \
  -f "$BACKUP_FILE"

echo "Backup da origem salvo em: $BACKUP_FILE"
```

## Passo 3 — Inicializar Tabelas no Destino

```bash
python -c "
import psycopg2

destino = '$ARGUMENTS'.strip()
conn = psycopg2.connect(destino)
cur = conn.cursor()

cur.execute('''
    CREATE TABLE IF NOT EXISTS classificacoes (
        id SERIAL PRIMARY KEY,
        cnpj_destinatario TEXT, nome_destinatario TEXT,
        cnpj_emitente TEXT, nome_emitente TEXT,
        numero_nf TEXT, ncm TEXT, cfop TEXT,
        descricao_produto TEXT, valor_total REAL,
        classificacao TEXT NOT NULL,
        confirmado_fiscal INTEGER DEFAULT 0,
        usuario TEXT, data_classificacao DATE DEFAULT CURRENT_DATE
    )
''')
cur.execute('''
    CREATE TABLE IF NOT EXISTS regras_ncm (
        id SERIAL PRIMARY KEY,
        ncm TEXT NOT NULL,
        cnpj_destinatario TEXT NOT NULL DEFAULT '',
        classificacao TEXT NOT NULL,
        descricao TEXT, criado_em DATE DEFAULT CURRENT_DATE,
        UNIQUE(ncm, cnpj_destinatario)
    )
''')
cur.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        cnpj TEXT PRIMARY KEY,
        razao_social TEXT, cnae TEXT, descricao_cnae TEXT,
        cnaes_secundarios TEXT, cnaes_secundarios_det TEXT,
        atualizado_em DATE DEFAULT CURRENT_DATE
    )
''')
conn.commit()
conn.close()
print('Tabelas criadas/verificadas no destino OK')
"
```

## Passo 4 — Importar Dados

```bash
DESTINO='$ARGUMENTS'
psql "$DESTINO" -f "$BACKUP_FILE"
echo "Importacao concluida!"
```

## Passo 5 — Validar Migração

```bash
python -c "
import psycopg2, psycopg2.extras

origem_url = ''
with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            origem_url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")

destino_url = '$ARGUMENTS'.strip()

def contar(url, tabela):
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM {tabela}')
    n = cur.fetchone()[0]
    conn.close()
    return n

print('=== Validacao da migracao ===')
print(f'{'Tabela':<20} {'Origem (Neon)':<20} {'Destino (Supabase)':<20} Status')
print('-' * 70)
ok = True
for t in ['classificacoes', 'regras_ncm', 'clientes']:
    n_orig = contar(origem_url, t)
    n_dest = contar(destino_url, t)
    status = 'OK' if n_orig == n_dest else 'DIVERGENCIA'
    if status != 'OK':
        ok = False
    print(f'{t:<20} {n_orig:<20} {n_dest:<20} {status}')

print()
print('RESULTADO:', 'MIGRACAO CONCLUIDA COM SUCESSO' if ok else 'ATENCAO: revisar divergencias')
"
```

## Próximos Passos (após migração validada)

Informe ao usuário:
1. Atualizar `.streamlit/secrets.toml` com a URL do Supabase produção
2. Testar o app localmente com o novo banco
3. Configurar os secrets no Streamlit Cloud
4. Compartilhar o novo link com a fiscal
5. Após confirmação da fiscal: parar o ngrok
