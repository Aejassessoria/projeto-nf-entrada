# Seed DB — Popular Banco com Regras NCM Iniciais

Popula um banco de dados NOVO com as regras NCM padrão do arquivo `data/ncm_rules_seed.json`. Use apenas em bancos recém-criados (Supabase teste ou produção).

## AVISO IMPORTANTE

> Este comando insere dados no banco. Use SOMENTE em bancos novos e vazios.
> Antes de executar, confirme qual banco será populado.

## Verificação Prévia

```bash
python -c "
import json, os

# Verifica o arquivo seed
seed_path = 'data/ncm_rules_seed.json'
if not os.path.exists(seed_path):
    print('ERRO: arquivo', seed_path, 'nao encontrado')
    exit(1)

with open(seed_path) as f:
    rules = json.load(f)

print(f'Arquivo seed encontrado: {len(rules)} regras NCM')
for r in rules[:3]:
    print(f'  NCM {r.get(\"ncm\")}: {r.get(\"classificacao\")} - {r.get(\"descricao\", \"\")}')
print('  ...')
"
```

Confirme o banco de destino:

```bash
python -c "
try:
    with open('.streamlit/secrets.toml') as f:
        for line in f:
            if 'DATABASE_URL' in line:
                url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                parts = url.split('@')
                host = parts[1].split('/')[0] if '@' in url else '?'
                print('Banco de destino (host):', host)
except:
    print('Sem DATABASE_URL em secrets.toml')
"
```

**Confirme com o usuário antes de prosseguir se o banco está correto.**

## Verificar se já existem regras (evitar duplicatas)

```bash
python -c "
import psycopg2, psycopg2.extras

with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            db_url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")

conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM regras_ncm')
n = cur.fetchone()[0]
conn.close()
print(f'Regras NCM existentes no banco: {n}')
if n > 0:
    print('ATENCAO: banco ja tem regras. Seed pode criar duplicatas.')
    print('Use apenas em bancos completamente vazios.')
"
```

## Executar Seed (somente se banco estiver vazio)

```bash
python -c "
import json, psycopg2, psycopg2.extras

with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            db_url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")

with open('data/ncm_rules_seed.json') as f:
    rules = json.load(f)

conn = psycopg2.connect(db_url)
cur = conn.cursor()

inseridos = 0
for r in rules:
    try:
        cur.execute('''
            INSERT INTO regras_ncm (ncm, cnpj_destinatario, classificacao, descricao)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ncm, cnpj_destinatario) DO NOTHING
        ''', (r['ncm'], '', r['classificacao'], r.get('descricao', '')))
        inseridos += cur.rowcount
    except Exception as e:
        print(f'Erro na regra NCM {r.get(\"ncm\")}: {e}')

conn.commit()
conn.close()
print(f'Seed concluido: {inseridos} regras inseridas de {len(rules)} total')
"
```

## Resultado Esperado

Informe:
- Quantas regras foram inseridas
- Se houve conflitos (regras já existentes ignoradas)
- Status: **SEED CONCLUIDO** / **ERRO**
