# ExtrairCNM

Lê PDFs de matrícula e consulta de ônus (RI Digital) e extrai o **CNM** (Código Nacional de Matrícula) e a **matrícula** de cada arquivo. O resultado sai numa planilha, pronta para cruzar com PROCV.

O CNM fica no canto superior direito das fichas, com este formato:

```
CNM:123456.2.0001234-75
```

Como a maioria dos PDFs é imagem, sem texto selecionável, o programa usa **OCR**. Tudo roda no computador de quem usa, sem internet, e os PDFs não saem da máquina.

> **Repositório privado.** Não suba PDFs aqui: são documentos de imóveis. O `.gitignore` já bloqueia `*.pdf`, `*.csv` e `*.xlsx`.

---

## Como funciona

1. Percorre os PDFs da pasta, incluindo subpastas.
2. Em cada PDF, tenta primeiro o texto embutido. Se não achar o CNM, faz OCR só no topo da página, em recortes cada vez maiores.
3. Valida o CNM pelo **dígito verificador** (módulo 97). Só aceita leituras que passam na validação. Isso evita um dígito lido errado pelo OCR.
4. Se a página 1 não der um CNM válido, por exemplo por causa de um carimbo por cima, tenta a página 2, depois a 3, até a **5** (`MAX_PAGINAS` no início do script).
5. Tira a **matrícula** dos 7 dígitos do meio do CNM, sem os zeros à esquerda (`0001234` vira `1234`).
6. Tira a **chave** dos 12 primeiros dígitos do nome do arquivo (`730271000020 - 30.10.2026 - Ônus Consulta.pdf` vira `730271000020`).

---

## Para quem vai usar (sem instalar nada)

1. Peça o `ExtrairCNM.exe` a quem mantém o projeto.
2. Coloque o `.exe` **na mesma pasta dos PDFs**.
3. Dê dois cliques. A primeira abertura demora alguns segundos, então espere.
4. Quando a janela mostrar "Pronto", aperte Enter para fechar.
5. Na mesma pasta aparecem `cnm_extraidos.xlsx` e `cnm_extraidos.csv`.

**Requisitos:** Windows 10 ou 11 de 64 bits. Não precisa de Python, de internet nem de permissão de administrador.

### Avisos comuns

| O que aparece | O que fazer |
| --- | --- |
| "O Windows protegeu o computador" | O `.exe` não tem assinatura digital. Clique em **Mais informações > Executar assim mesmo**. |
| O antivírus bloqueia | Fale com o TI. É comum em `.exe` gerado com PyInstaller. |
| Erro com `VCRUNTIME` ou DLL faltando | Instale o *Microsoft Visual C++ Redistributable x64*. |
| Janela parada logo no início | Normal na primeira abertura. Espere alguns segundos. |

---

## O resultado

O `cnm_extraidos.xlsx` tem as colunas:

| Coluna | Conteúdo |
| --- | --- |
| `chave` | 12 primeiros dígitos do nome do arquivo (número) |
| `arquivo` | nome do PDF |
| `cnm` | CNM no formato `000000.0.0000000-00` |
| `matricula` | matrícula, sem zeros à esquerda (número) |
| `status` | `OK` (passou na validação) ou `REVISAR` |
| `origem` | `texto` (texto embutido) ou `ocr` |
| `pagina` | página de onde veio o CNM |

**Sempre confira as linhas `REVISAR`.** Nelas o CNM não passou na validação, ou não foi encontrado. Se houver um valor, é a leitura duvidosa do OCR e **não deve ser usada sem conferência**.

A coluna `pagina` com valor maior que 1 indica que o CNM da primeira página não pôde ser lido.

### Usando no PROCV

`chave` e `matricula` saem como **número** no `.xlsx`. A coluna que você usa para buscar precisa ter o mesmo tipo, número com número ou texto com texto. Se um lado for texto e o outro número, o PROCV dá `#N/D`.

```
=PROCV(A2;Dados!A:D;3;0)
```

Para deixar em branco quando não houver correspondência:

```
=SEERRO(PROCV(A2;Dados!A:D;3;0);"")
```

Se o PROCV aparecer como texto e não calcular, a célula está formatada como **Texto**. Mude para **Geral**, clique na célula, aperte `F2` e depois `Enter`.

Se o mesmo número de chave aparecer em mais de um arquivo, o PROCV devolve só o primeiro. Confira esses casos à mão.

---

## Para quem mantém o projeto

### Estrutura

```
extrair_cnm.py                   script principal
requirements.txt                 dependências
.github/workflows/gerar-exe.yml  gera o .exe no GitHub Actions
.gitignore
```

### Rodar pelo Python (sem o .exe)

Requer Python 3.10 a 3.12. O Python 3.13 não foi testado com o `.exe`.

```
python -m pip install -r requirements.txt
python extrair_cnm.py .
```

O `.` é a pasta com os PDFs. Se omitir, usa a pasta atual (no `.exe`, a pasta onde ele está). Um segundo argumento opcional define o nome do CSV de saída.

### Gerar o `.exe`

**Pelo GitHub Actions** (recomendado):

1. Suba as mudanças na branch `main`, ou vá em **Actions > Gerar ExtrairCNM.exe > Run workflow**.
2. Quando o build ficar verde, abra a execução e baixe o **ExtrairCNM** em *Artifacts*.
3. O artefato expira em cerca de 90 dias. Guarde o `.exe` em outro lugar para compartilhar.

**Na sua máquina (Windows):**

```
python -m pip install pyinstaller -r requirements.txt
python -m PyInstaller --onefile --name ExtrairCNM --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pymupdf extrair_cnm.py
```

O arquivo sai em `dist\ExtrairCNM.exe`. O `.exe` fica grande, na casa de centenas de MB, porque leva o motor de OCR dentro. Rode o build só no Windows.

### Ajustes

| O que mudar | Onde |
| --- | --- |
| Quantas páginas tentar | `MAX_PAGINAS` |
| Região da página lida pelo OCR | `RECORTES` (frações da página: `x0, y0, x1, y1, zoom`) |
| Como a chave é tirada do nome | `re.match(r"\d{12}", pdf.name)` em `main()` |

### Limites conhecidos

- O OCR pode errar em carimbos que cobrem o número. A validação do dígito verificador evita aceitar leituras erradas, mas o arquivo vai para `REVISAR`.
- Só lê o topo das primeiras páginas, procurando o CNM. Não extrai outros dados do PDF.
- Quando o CNM é lido por OCR, o formato precisa ser `000000.0.0000000-00`. Outros formatos não são reconhecidos.
- O `.exe` não é assinado, então o SmartScreen e alguns antivírus podem alertar.
