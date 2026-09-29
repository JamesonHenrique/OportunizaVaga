# OPERAÇÃO — triagem, cascata de modelos, vigia e canário

Componentes determinísticos (sem LLM) que gastam menos tokens e avisam quando algo quebra.
Tudo é portável (Python + `.sh`/`.ps1`) e **fail-open**: se um deles falhar, a rodada segue como antes.

## Triagem pela descrição (`bot/vaga_check.py`)

Decide o óbvio **antes** do modelo abrir a vaga: nível, anos exigidos, modelo de trabalho e stack, a partir do texto do
anúncio e do "Nível de experiência" oficial do LinkedIn. É **conservador**: só rejeita com evidência clara; na dúvida
diz `COMPATIVEL` e o modelo decide.

```bash
python3 bot/vaga_check.py checar /tmp/anuncio.txt "Título da vaga" "Júnior"   # COMPATIVEL | INCOMPATIVEL: motivo
```

Tudo vem do **perfil** (`perfil.json`) e do `descoberta.json` opcional (exemplo em `config/descoberta.example.json`):

| Regra | De onde vem |
|---|---|
| níveis aceitos/recusados (palavras do papel: "desenvolvedor sênior", "vaga pleno") | `niveis` do perfil |
| nível oficial do LinkedIn vence o título; título sem palavra de nível só reprova em perfis de entrada (estágio/trainee/júnior) | `niveis` |
| anos exigidos (`4+ years of full-stack experience`, `experiência mínima de 3 anos`); número ≥ 10 é idade da empresa e é ignorado | `experiencia_max_anos` (`null` = sem teto) |
| presencial/híbrido explícitos, salvo se a descrição também disser "remoto" | `modelos` |
| 2+ tecnologias de fora e nenhuma do perfil | `stack_evitar` / `stack_preferida` (vazias = regra desligada) |

Uso na descoberta (`OV_DESCOBRIR=1`): cada vaga da fila passa pela triagem. LinkedIn: página pública
`jobs-guest/jobs/api/jobPosting/<id>` (descrição + nível oficial), no máximo `max_descricoes` (padrão 12, `0` desliga)
por coleta, com pausa entre requisições; Gupy: a descrição já vem na lista. Falha de rede/parse **nunca filtra**. A vaga
aprovada aparece no prompt com a marca `[descrição ok]`, e o passo **c0** do prompt manda o modelo rodar o mesmo
`vaga_check.py` nas demais vagas, antes de gerar CV. Rejeitadas entram na fila como `filtrada` com motivo `desc:...`.
Teste: `tests/test_vaga_check.sh` (os 10 casos de referência, perfil, CLI, descoberta offline).

## Cascata adaptativa de modelos (`bot/modelos-saude.py`)

A ordem da cascata em `loop.sh`/`loop.ps1` é escrita à mão, mas modelos gratuitos variam muito: na operação privada do
mantenedor (8 dias), um modelo teve 1 sucesso em 54 sessões improdutivas enquanto outro teve 57 sucessos e 0 falhas.
O script lê os `loop.log*` dos últimos 7 dias e conta, por modelo, `rodada usou o modelo X` (sucesso) contra
`no limite` / `encerrou sem navegar` / `quebrou o formato de tool-call` / `morreu apos erro` (falha):

- ordena por nota suavizada `(sucessos + 1) / (tentativas + 2)` (modelo novo começa em 0,5; empate mantém a ordem original);
- **quarentena de 7 dias** para modelo com 0 sucessos em ≥ 10 tentativas, nunca deixando menos de `MIN_ATIVOS` (2) modelos;
- recalcula no máximo a cada 6 h; **fail-open**: qualquer erro devolve a ordem original.

```bash
python3 bot/modelos-saude.py relatorio              # tabela por modelo (usou / limite / improdutiva / erro / nota)
python3 bot/modelos-saude.py ordenar M1 M2 M3      # cascata resultante, um modelo por linha
```

Estado em `<STATE_DIR>/modelos_saude.json` (`MODELOS_SAUDE_FILE` sobrescreve; `MODELOS_SAUDE_LOGS` troca o glob dos logs,
útil em testes). Desligue com `OV_MODELOS_SAUDE=0`. O modelo pago opcional (`OV_MODELO_PAGO`) continua na frente e fora
da ordenação. Teste: `tests/test_modelos_saude.sh`.
