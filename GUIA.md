# Guia do Painel Garmin

Para quem **não programa**. Explica o que cada parte faz, como usar no dia a dia
e o que fazer quando algo dá errado.

## 1. O que é

Um programa em Python que:

1. lê os **seus** dados no Garmin Connect, usando a chave pessoal oficial (Personal API);
2. guarda uma cópia no seu computador;
3. desenha o arquivo `painel.html`, que você abre no navegador.

Ele **só lê**: nunca cria, altera nem apaga nada na sua conta. Todo número vem da
Garmin; o que ela não envia aparece como "sem dado". O painel mostra números, sem
diagnóstico e sem conselho de treino.

## 2. Mapa dos arquivos

| Arquivo | Para que serve | Você mexe? |
|---|---|---|
| `painel.html` | O painel, para abrir no navegador | Só abrir |
| `atualizar.bat` | Dois cliques: busca dados novos e abre o painel | Sim |
| `redesenhar.bat` | Refaz o visual sem internet e sem chave | Sim |
| `agendar.bat` / `remover_agendamento.bat` | Liga/desliga a atualização automática | Raramente |
| `garmin_painel.py` | O programa principal: conversa com a Garmin | Não |
| `cofre.py` | Lê a chave e o token do cofre do Windows | Não |
| `armazem.py` | Guarda os dados e faz o backup | Não |
| `formatos.py` | Formata números, datas e esportes | Não |
| `visual.py` | Desenha a página e os gráficos | Não |
| `diagnostico.py`, `configuracao.py` | Conferência geral e data de vencimento da chave | Não |
| `metas.py` | Suas metas e o progresso delas | Não |
| `dados_brutos.json` | Seus dados guardados (**dados de saúde**, sem chave) | Não |
| `backups/` | Até 5 cópias diárias do arquivo acima | Só para restaurar |
| `ultimo_log.txt` | O que a última atualização automática fez | Para olhar |

## 3. Como os dados andam

```
Cofre do Windows ──(chave)──> programa ──(token 24 h)──> Garmin (só leitura)
                                  │
                                  ├──> dados_brutos.json ──> backups/
                                  └──> painel.html ──> seu navegador
```

- A **chave** fica só no cofre do Windows (nome `garmin-personal-api-key`). Nunca em arquivo.
- O **token** é uma senha temporária (vale 24 h) que a Garmin devolve em troca da chave.
  Fica no cofre (`garmin-personal-api-token`) para ser reaproveitado.

## 3.1 Comandos do dia a dia

Abra o PowerShell **dentro da pasta do painel** (no Explorador, clique na barra de
endereço, digite `powershell` e Enter) e use:

| Quero... | Comando |
|---|---|
| Atualizar e abrir o painel | `py garmin_painel.py` (ou dois cliques em `atualizar.bat`) |
| Redesenhar sem consultar a Garmin | `py garmin_painel.py --so-visual` |
| Conferir se está tudo certo | `py garmin_painel.py --diagnostico` |
| Avisar antes de a chave vencer | `py garmin_painel.py --chave-vence 2027-02-09` |
| Ver mais dias | `py garmin_painel.py --dias 60` |
| Guardar os dados fora do OneDrive | `py garmin_painel.py --pasta-dados "C:\PainelGarmin"` |
| Definir uma meta sua | `py garmin_painel.py --meta km-mes=50` (veja as opções abaixo) |
| Apagar uma meta | `py garmin_painel.py --remover-meta km-mes` |
| Buscar mais histórico (para os recordes) | `py garmin_painel.py --historico 365` (demora na primeira vez) |
| Apagar o token guardado | `py garmin_painel.py --esquecer-token` |

A data de vencimento da chave aparece em
https://connect.garmin.com/app/settings/personalApiToken . Informe-a uma vez com
`--chave-vence`: a partir de 14 dias antes, o painel mostra uma faixa de aviso.

### Metas, comparação e recordes

- **Metas** são **suas**: você define o valor, e o painel mostra quanto já foi feito (soma das
  corridas enviadas pela Garmin). Opções: `km-semana`, `corridas-semana`, `km-mes`, `horas-mes`.
  Exemplo: `py garmin_painel.py --meta km-mes=50`. A marca dourada na barra é o fim da meta.
- **Comparação** (cartão "Esta semana × semana passada × média"): a semana atual vai até hoje;
  a média é das últimas 4 semanas completas (semana sem corrida conta como 0).
- **Recordes** usam todo o histórico guardado. No começo ele cobre só ~30 dias; rode
  `py garmin_painel.py --historico 365` uma vez para ampliar (pode levar alguns minutos).
- **Peso, hidratação e SpO2** aparecem se a Garmin enviar esses dados. Sem balança conectada, o gráfico
  de peso some e o programa avisa. Pesos acima de 300 são tratados como gramas.

## 4. Se algo der errado

Comece **sempre** por `py garmin_painel.py --diagnostico`. Ele diz o que está errado.

| O que aparece | Provável causa | O que fazer |
|---|---|---|
| `Não achei a chave no Gerenciador de Credenciais` | A chave não está guardada (ou foi apagada) | Guarde de novo (seção 6) |
| `A Garmin respondeu 401` | Chave vencida, apagada ou trocada | Crie outra chave e guarde de novo |
| `A Garmin respondeu 429` | Pedidos demais em pouco tempo | Espere alguns minutos e tente de novo |
| `Sem conexão com a Garmin` | Sem internet | Verifique a conexão |
| `py não é reconhecido` | Python não instalado | Instale o Python (python.org) e marque "Add to PATH" |
| Faixa "Dados antigos" no painel | Faz mais de 13 horas sem atualizar | Dois cliques em `atualizar.bat`; confira o agendamento |
| Um gráfico não aparece | A Garmin não enviou aquele dado no período | Normal: o programa avisa qual foi |
| `ultimo_log.txt` com ERRO | A atualização automática falhou | Rode `--diagnostico` |

Para ler o log com acentos corretos:
`Get-Content .\ultimo_log.txt -Encoding UTF8`

## 5. Seus dados e sua privacidade

- `dados_brutos.json`, `backups/` e `painel.html` têm **dados de saúde**. Ficam só no seu
  computador e estão fora do GitHub (`.gitignore`).
- Se a pasta estiver no **OneDrive**, os arquivos sobem para a nuvem da Microsoft. Para
  evitar, use `--pasta-dados` com uma pasta fora dele.
- **Restaurar um backup:** feche o programa, copie um arquivo de `backups/` para a pasta
  principal e renomeie-o para `dados_brutos.json`.
- Se o arquivo de dados estragar, o programa **não apaga**: separa como
  `dados_brutos.corrompido-<data>.json` e recomeça do zero.

## 6. Trocar a chave (se vencer ou se quiser renovar)

1. No Garmin Connect (link acima), **apague** a chave antiga e clique em **Create Key**.
   Aceite os termos, escolha o prazo e clique em Create. **Copie a chave** e não feche a página.
2. Abra o PowerShell, cole o **bloco A** abaixo e aperte Enter. Ele só cria um comando.
3. **Copie a chave de novo** (Ctrl+C), digite `Guardar-ChaveGarmin` e aperte Enter.
   Deve aparecer `OK: chave guardada`. Depois clique em Done no site.
4. Rode `py garmin_painel.py --chave-vence AAAA-MM-DD` com a nova data.

**Nunca cole a chave em conversa, e-mail ou arquivo.**

Bloco A:

```powershell
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class GarminCredV3 {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
  public struct CREDENTIAL {
    public int Flags; public int Type; public string TargetName; public string Comment;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
    public int CredentialBlobSize; public IntPtr CredentialBlob; public int Persist;
    public int AttributeCount; public IntPtr Attributes; public string TargetAlias; public string UserName;
  }
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern bool CredWrite(ref CREDENTIAL c, int flags);
  public static int Save(string target, string secret) {
    byte[] b = System.Text.Encoding.Unicode.GetBytes(secret);
    IntPtr p = Marshal.AllocHGlobal(b.Length);
    try {
      Marshal.Copy(b, 0, p, b.Length);
      CREDENTIAL c = new CREDENTIAL();
      c.Type = 1; c.TargetName = target; c.UserName = "garmin";
      c.CredentialBlobSize = b.Length; c.CredentialBlob = p; c.Persist = 2;
      if (CredWrite(ref c, 0)) return 0;
      return Marshal.GetLastWin32Error();
    } finally { Marshal.FreeHGlobal(p); }
  }
}
"@
function Guardar-ChaveGarmin {
  $k = Get-Clipboard -Raw
  if ([string]::IsNullOrWhiteSpace($k)) { Write-Host "ERRO: a area de transferencia esta vazia. Copie a chave de novo."; return }
  $k = $k.Trim()
  if ($k.Length -lt 129 -or $k.StartsWith('function') -or $k.Contains('Add-Type')) { Write-Host "ERRO: isto nao parece a chave (tem $($k.Length) caracteres). Copie a chave de novo."; return }
  $r = [GarminCredV3]::Save('garmin-personal-api-key', $k)
  if ($r -eq 0) { Write-Host "OK: chave guardada ($($k.Length) caracteres)."; Set-Clipboard -Value ' ' }
  else { Write-Host "ERRO ao guardar. Codigo do Windows: $r" }
}
Write-Host "PRONTO: o comando Guardar-ChaveGarmin foi criado. Nada foi guardado ainda."
```

## 7. Glossário

| Termo | Significado |
|---|---|
| **Chave pessoal** | Senha longa que você cria no Garmin Connect; dá acesso de leitura aos seus dados |
| **Token** | Senha temporária (24 h) que a Garmin devolve em troca da chave |
| **Cofre / Gerenciador de Credenciais** | Lugar do Windows para guardar senhas com segurança |
| **Pace** | Tempo para percorrer 1 km (ex.: 5:00 /km) |
| **FC de repouso** | Frequência cardíaca de repouso, em batimentos por minuto (bpm) |
| **VFC (HRV)** | Variabilidade da frequência cardíaca; o painel mostra a média da noite, em ms |
| **Body Battery** | Número de 0 a 100 que a Garmin calcula para a "energia" do dia |
| **Zonas de FC** | Faixas de intensidade (Z1 a Z5) que a Garmin define para o seu coração |
| **SpO2** | Saturação de oxigênio no sangue, em %, medida pelo relógio |
| **VO2máx** | Valor que a Garmin estima para a sua capacidade aeróbica |

## 8. Para aprender o código, nesta ordem

1. `formatos.py`: funções pequenas (formatar km, hora, pace). Bom para entender Python.
2. `armazem.py`: como os dados são guardados em arquivo e atualizados aos poucos.
3. `garmin_painel.py`: o fluxo principal (`main`, depois `atualizar_armazem` e `gerar`).
4. `visual.py`: cada função `graf_...` desenha um gráfico em SVG; leia `graf_passos` primeiro.
5. `tests/test_painel.py`: mostra o programa funcionando contra um servidor falso.

## 9. Regras deste projeto

- Só a **chave oficial**; sem e-mail/senha da Garmin e sem biblioteca não oficial.
- **Só leitura**: nada na sua conta é criado, alterado ou apagado.
- **Todo número vem da Garmin**; o que não vier aparece como "sem dado" (nunca zero).
- **Sem diagnóstico e sem conselho de treino.**
- A chave **nunca** vai para arquivo, tela, GitHub ou conversa.
