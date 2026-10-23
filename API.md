# API do relatório de auditoria de inventário

Esta API lê as respostas de uma aba do Google Sheets e as retorna em JSON para
consumo por um sistema. A leitura é feita pelo backend; o frontend não recebe o
token OAuth do Google.

## Execução local

Na pasta `pipelines-carmel`, instale as dependências do projeto e inicie a API:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn relatorio_auditoria_inventario.app:app --host 127.0.0.1 --port 8000 --reload
```

Endereço base local: `http://127.0.0.1:8000`.

A documentação interativa do FastAPI está disponível em `/docs` e o esquema
OpenAPI em `/openapi.json`. Essas URLs e a porta acima são locais; em outro
ambiente, use o endereço definido para a implantação.

### Configuração do backend

O aplicativo carrega o arquivo `.env` da raiz de `pipelines-carmel`. Também é
possível fornecer as variáveis pelo ambiente do processo; valores já definidos no
ambiente não são sobrescritos pelo arquivo `.env`.

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `INVENTARIO_SPREADSHEET_ID` | Sim | ID da planilha no Google Sheets. |
| `INVENTARIO_WORKSHEET` | Sim | Nome exato da aba. |
| `INVENTARIO_RANGE` | Não | Intervalo da aba; padrão `A:AA`. |
| `GOOGLE_SHEETS_TOKEN_FILE` | Sim | Caminho do JSON do token OAuth autorizado. Prefira um caminho absoluto fora do repositório. |

Exemplo, usando valores fictícios para os caminhos e ID:

```dotenv
INVENTARIO_SPREADSHEET_ID=id_da_planilha
INVENTARIO_WORKSHEET=Respostas ao formulário 1
INVENTARIO_RANGE=A:AA
GOOGLE_SHEETS_TOKEN_FILE=C:/caminho-seguro/token_consulta_sheets.json
```

O token deve ter sido autorizado com o escopo
`https://www.googleapis.com/auth/spreadsheets.readonly`, por uma conta que tenha
acesso à planilha. O arquivo precisa ser legível pelo processo; se o token
expirar e tiver um `refresh_token`, o código também precisa escrever no arquivo
para salvar a renovação. A autorização inicial é interativa e não é executada
pelo endpoint. Consulte o [README](README.md) para a configuração local.

## Consultar auditorias

```http
GET /api/auditorias
```

A requisição não recebe parâmetros de consulta nem corpo. Atualmente, o endpoint
não implementa paginação, filtros, ordenação ou cache: cada chamada consulta o
intervalo configurado no Google Sheets.

### Exemplo de requisição

No PowerShell:

```powershell
$resposta = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auditorias'
$resposta.total
$resposta.items | Select-Object -First 1
```

Com curl no Windows:

```powershell
curl.exe -X GET http://127.0.0.1:8000/api/auditorias
```

### Resposta: `200 OK`

O corpo é um objeto JSON com `columns`, `items`, `values` e `total`. O exemplo
abaixo contém dados fictícios e apenas parte das colunas:

```json
{
  "columns": [
    { "key": "hotel", "label": "Hotel" },
    { "key": "comentarios", "label": "Comentários:" },
    { "key": "comentarios_2", "label": "Comentários:" }
  ],
  "items": [
    {
      "hotel": "Hotel A",
      "comentarios": "Primeiro comentário",
      "comentarios_2": "Segundo comentário"
    },
    {
      "hotel": "Hotel B",
      "comentarios": "",
      "comentarios_2": "Sem observações"
    }
  ],
  "values": {
    "2": {
      "hotel": "Hotel A",
      "comentarios": "Primeiro comentário",
      "comentarios_2": "Segundo comentário"
    },
    "3": {
      "hotel": "Hotel B",
      "comentarios": "",
      "comentarios_2": "Sem observações"
    }
  },
  "total": 2
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `columns` | Lista de objetos | Colunas obtidas da primeira linha do intervalo. `label` contém o cabeçalho original e `key` é a chave normalizada usada nas respostas. |
| `items` | Lista de objetos | Linhas de dados em ordem de retorno, com chaves correspondentes a `columns[].key`. |
| `values` | Objeto de objetos | Os mesmos dados de `items`, indexados por strings `"2"`, `"3"` e assim por diante. |
| `total` | Inteiro | Quantidade de objetos em `items`. |

As chaves de `values` são posições calculadas a partir de `2`, não identificadores
estáveis. Elas coincidem com o número físico da linha apenas quando o intervalo
começa na linha 1. Inserir ou excluir linhas pode alterar essas posições. Um
intervalo configurado a partir de outra linha também continuará sendo numerado a
partir de `"2"`.

Cabeçalhos são normalizados para letras minúsculas, sem acentos, com separadores
em `_`. Para cabeçalhos repetidos, são adicionados sufixos como `_2` e `_3`.
Alterações nos cabeçalhos ou na sua ordem podem alterar essas chaves; use
`columns` para associar cada chave ao texto exibido.

Os valores são retornados como **strings formatadas pelo Google Sheets**;
datas e pontuações não são convertidas automaticamente para tipos de data ou
número. Células ausentes no fim de uma linha são preenchidas com `""`. A
primeira linha do intervalo é tratada como cabeçalho; valores além do número de
colunas desse cabeçalho são descartados.

Se o intervalo estiver vazio, a resposta será:

```json
{ "columns": [], "items": [], "values": {}, "total": 0 }
```

`items` e `values` duplicam o conteúdo no corpo da resposta. Escolha um dos dois
para consumo no frontend; mantenha a compatibilidade enquanto ambos existirem.

### Exemplo no frontend

Este exemplo pressupõe que o frontend e a API estejam na **mesma origem**:

```javascript
async function carregarAuditorias() {
  const response = await fetch('/api/auditorias');

  if (!response.ok) {
    throw new Error(`Falha ao consultar auditorias: HTTP ${response.status}`);
  }

  const { columns, items, total } = await response.json();
  return { columns, items, total };
}
```

Para um frontend em outra origem, o navegador aplicará CORS. A aplicação atual
não configura CORS; use uma mesma origem por meio de um proxy ou configure uma
política restrita às origens autorizadas antes da integração.

### Respostas de erro

| Código | Corpo `detail` | Situação |
| --- | --- | --- |
| `503` | `Integração ainda não configurada.` | Variável obrigatória ausente ou arquivo de token não encontrado. |
| `502` | `Falha ao consultar dados no Google Sheets.` | Falha tratada ao validar/renovar o token ou erro HTTP retornado pela API Google. |
| `500` | Erro interno | Outras falhas não tratadas pela aplicação. Consulte os logs do servidor sem expor credenciais ou dados pessoais. |

Exemplo de erro tratado:

```json
{ "detail": "Falha ao consultar dados no Google Sheets." }
```

Para investigar uma resposta `502`, confira nos logs e no ambiente se o token é
válido, se a conta autorizada possui acesso à planilha e se o ID, a aba e o
intervalo estão corretos. Se necessário, gere novamente o token de forma
interativa. Não envie o conteúdo do token nos logs, no frontend ou em chamados.

## Verificar o processo

```http
GET /health
```

Resposta `200 OK`:

```json
{ "status": "ok" }
```

Esse endpoint verifica somente se a aplicação responde. Ele **não** valida o
token, a rede, a permissão ou a disponibilidade do Google Sheets.

## Segurança e implantação

- A API atual **não possui autenticação nem autorização de usuários**. Mantenha-a
  em `127.0.0.1` no desenvolvimento; antes de expô-la em uma rede, implemente
  os controles de acesso do sistema.
- As respostas podem conter e-mails e outros dados pessoais. Restrinja quem pode
  acessá-las e evite registrá-las integralmente em logs.
- O token OAuth fica exclusivamente no backend, fora do Git e do código entregue
  ao navegador. A API do sistema não exige que o consumidor envie esse token.
- A coluna `FOTOS`, se contiver links, retorna apenas os valores presentes nas
  células. A API não baixa arquivos nem concede acesso aos recursos vinculados.

## Testes automatizados

```powershell
python -m unittest relatorio_auditoria_inventario.test_app -v
```

Os testes existentes usam mocks e não validam o acesso real ao Google Sheets.
Para validar a integração, execute `GET /api/auditorias` com a configuração e o
token do ambiente, sem publicar o resultado ou os segredos.
