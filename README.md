# Story diário no Instagram

Publica um story por dia, às 9h07 de Brasília, usando a API oficial do Instagram e o GitHub Actions.

## Como usar no dia a dia

1. Coloque as artes na pasta [`fila/`](fila/).
2. Numere os arquivos para definir a ordem: `001-promo.jpg`, `002-dica.jpg`, `003-video.mp4`.
3. Envie para o GitHub. A cada dia, o próximo arquivo é publicado e vai para [`publicados/`](publicados/).

**Formatos:** imagem em JPG e vídeo em MP4 ou MOV. A API não aceita PNG: arquivos nesse formato ficam na fila, mas são ignorados. O tamanho recomendado é 1080 x 1920 (vertical).

**Atenção:** este repositório é público, então qualquer pessoa pode ver as artes na fila antes de elas saírem. Não coloque nela nada que ainda precise ficar em segredo.

## Configuração inicial

Os menus da Meta mudam com frequência, então os nomes abaixo podem variar um pouco.

### 1. Conta profissional

A API não publica por conta pessoal. No app do Instagram, abra **Configurações > Tipo de conta e ferramentas**. Se a conta for pessoal, mude para **Criador** ou **Comercial**. A mudança é gratuita.

### 2. Token do Instagram

1. Acesse [developers.facebook.com/apps](https://developers.facebook.com/apps) e crie um app.
2. Adicione o caso de uso de **Instagram** e abra a configuração da **API com login do Instagram**.
3. Em **Gerar tokens de acesso**, adicione sua conta e gere o token.
4. Salve no GitHub, em **Settings > Secrets and variables > Actions > New repository secret**:
   - Nome: `INSTAGRAM_ACCESS_TOKEN`
   - Valor: o token gerado

### 3. Renovação automática do token

O token expira em 60 dias. Para renová-lo sozinho, o robô precisa de permissão para atualizar o secret:

1. No GitHub, acesse **Settings > Developer settings > Fine-grained tokens** e crie um token.
2. Em **Repository access**, selecione somente este repositório.
3. Em **Repository permissions**, defina **Secrets** como **Read and write**.
4. Escolha a validade mais longa disponível e anote a data: quando esse token vencer, a renovação falha e é preciso criar outro.
5. Salve como o secret `GH_PAT_SECRETS`.

### 4. Primeiro teste

Na aba **Actions**, abra **Publicar story** e clique em **Run workflow**:

1. Rode com `verificar`. Deve aparecer sua conta, sem publicar nada.
2. Coloque uma imagem em `fila/` e rode com `publicar`. O story sai na hora, na sua conta.

## Quando algo der errado

O GitHub avisa por e-mail quando uma execução falha, conforme suas configurações de notificação.

| Mensagem | O que fazer |
| --- | --- |
| `A fila esta vazia` | Adicione novas artes em `fila/`. |
| `Secret INSTAGRAM_ACCESS_TOKEN nao configurado` | Refaça o passo 2. |
| Erro de token, código 190 | O token expirou. Gere outro e atualize o secret. |
| `O Instagram rejeitou a midia` | Confira o formato do arquivo. Ele continua na fila e bloqueia os seguintes até ser removido ou corrigido. |

## Limitações

- **Figurinhas:** a API não publica story com link, enquete ou localização.
- **Horário:** o GitHub pode atrasar a execução e, sob carga muito alta, até pular um dia.
- **Pausas longas:** o GitHub desativa os agendamentos depois de 60 dias sem atividade no repositório. Com a fila em uso isso não acontece, porque cada publicação conta como atividade.
- **Publicação repetida:** se o story sair mas o GitHub falhar ao salvar a fila, o mesmo arquivo pode ser publicado de novo no dia seguinte. A execução com falha aparece na aba **Actions**.

## Mudar o horário

Edite a linha `cron` em [`.github/workflows/publicar-story.yml`](.github/workflows/publicar-story.yml). O horário fica em UTC, ou seja, 3 horas a mais que o de Brasília.

## Testes

```bash
python -m unittest
```
