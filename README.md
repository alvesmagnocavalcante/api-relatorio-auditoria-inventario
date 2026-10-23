# Relatório de Auditoria de Inventário

API local que lê a planilha Google Sheets no backend e disponibiliza as respostas
em JSON para o frontend.

O retorno de `GET /api/auditorias` preserva `items` para compatibilidade e também
expõe `values`, com chaves calculadas a partir de `"2"`. Com o intervalo padrão
`A:AA`, elas correspondem ao número da linha no Google Sheets.

Consulte a [documentação de utilização da API](API.md) para contrato, exemplos
de consumo, erros e requisitos de segurança.

## Configuração

1. Copie os valores de `relatorio_auditoria_inventario/.env.example` para o
   `.env` local do projeto.
2. Mantenha o token OAuth fora do repositório e informe seu caminho absoluto em
   `GOOGLE_SHEETS_TOKEN_FILE`.
3. O usuário que autorizou o token deve ter acesso à planilha.

## Executar localmente

```powershell
cd C:\dev\Pipelines\pipelines-carmel
python -m uvicorn relatorio_auditoria_inventario.app:app --host 127.0.0.1 --port 8000 --reload
```

Use os endereços locais:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/auditorias`
- `http://127.0.0.1:8000/docs`

## Testes

```powershell
python -m unittest relatorio_auditoria_inventario.test_app -v
```

Os testes usam mocks e não leem token nem chamam a API do Google.

## Segurança

O endpoint deve permanecer em `127.0.0.1` durante o desenvolvimento. Antes de
publicá-lo em uma rede, implemente a autenticação e autorização do sistema. As
respostas incluem e-mail e outros dados potencialmente pessoais.
