# Box Blur Paralelo em Python

Comparação entre uma implementação **sequencial** e uma **paralela** do filtro Box Blur em Python puro, medindo o ganho de desempenho (*speedup*) ao distribuir o processamento entre vários núcleos da CPU.

---

## Por que este trabalho?

Processamento de imagens é um caso clássico de problema **paralelizável**: cada pixel de saída depende apenas dos pixels vizinhos da imagem original, e nenhum pixel de saída depende de outro pixel de saída. Ou seja, a imagem pode ser dividida em partes e cada parte pode ser processada ao mesmo tempo, sem que uma espere pela outra.

Mesmo assim, um programa comum percorre a imagem pixel por pixel em uma única linha de execução, usando só **um** núcleo da CPU enquanto os demais ficam ociosos. Em imagens de alta resolução (5K a 8K, com 20 a 42 milhões de pixels), isso leva minutos.

O objetivo do trabalho é:

1. Implementar o mesmo algoritmo nas duas abordagens (sequencial e paralela);
2. Medir o tempo de execução de cada uma (**T_st** e **T_mt**);
3. Calcular o ganho obtido: **Speedup = T_st / T_mt**;
4. Entender, na prática, os desafios de paralelizar em Python (GIL, compartilhamento de memória, divisão de carga).

O algoritmo foi propositalmente escrito "na mão", com laços em Python puro e sem NumPy ou OpenCV, para que o custo computacional seja alto e o efeito da paralelização fique evidente.

---

## O algoritmo: Box Blur

Para cada pixel, o Box Blur calcula a **média RGB** de todos os pixels dentro de um quadrado de lado `2 × radius + 1` centrado nele. Pixels fora da imagem são ignorados (a média usa apenas os vizinhos válidos).

| Radius | Janela  | Pixels somados por pixel |
|--------|---------|--------------------------|
| 1      | 3 × 3   | 9                        |
| 2      | 5 × 5   | 25                       |
| 5      | 11 × 11 | 121                      |
| 10     | 21 × 21 | 441                      |

O custo cresce com o quadrado do raio: dobrar o raio quadruplica, aproximadamente, o trabalho.

---

## As duas abordagens

### Single-thread (`src/single-thread.py`)

Percorre a imagem de cima para baixo e da esquerda para a direita, em um único fluxo. É a referência (baseline) para medir o ganho.

### Paralela (`src/multi-thread.py`)

Em Python, **threads não aceleram código CPU-bound** por causa do GIL (Global Interpreter Lock), que permite que apenas uma thread execute bytecode Python por vez. Por isso a versão paralela usa **processos** (`ProcessPoolExecutor`), e cada processo tem seu próprio interpretador e roda de fato em um núcleo separado.

Usar processos traz um problema: eles **não compartilham memória**. Enviar a imagem para cada processo exigiria serializá-la e copiá-la várias vezes, o que é lento e gasta muita memória. A solução adotada foi:

1. **Converter a imagem em uma fita de bytes** com `image.tobytes()`, gerando um vetor linear `RGBRGBRGB...`. O pixel `(x, y)` fica no índice `(y × largura + x) × 3`.
2. **Colocar os bytes em memória compartilhada** (`multiprocessing.shared_memory.SharedMemory`): uma área de origem, que todos os workers leem simultaneamente sem cópia, e uma área de saída, onde cada worker escreve seu resultado.
3. **Dividir a imagem em faixas horizontais** de linhas, uma por worker: `linhas_por_worker = ceil(altura / workers)`.
4. Cada worker aplica o blur **apenas nas suas linhas**, lendo os vizinhos (inclusive os das faixas vizinhas) da memória de origem. Como cada um escreve em uma região exclusiva da saída, **não há condição de corrida** e não é preciso usar locks.
5. Ao final, a imagem é reconstruída a partir da memória de saída com `Image.frombytes()`.

---

## Resultados

Imagens usadas:

| Imagem | Resolução   | Pixels  |
|--------|-------------|---------|
| 5K     | 3733 × 5597 | ~20,9 M |
| 6K     | 4032 × 6048 | ~24,4 M |
| 8K     | 7952 × 5304 | ~42,2 M |

Ambiente de teste: CPU com 16 threads lógicas — *(preencher com o modelo da CPU)*.

### Radius 1: tempo (s) por número de workers

| Imagem | Single-thread | 2 workers | 4 workers | 8 workers | 14 workers |
|--------|--------------:|----------:|----------:|----------:|-----------:|
| 5K     | 62,44         | 24,01     | 12,64     | 7,45      | 5,57       |
| 6K     | 85,55         | 34,44     | 17,18     | 8,75      | 6,48       |
| 8K     | 156,51        | 49,09     | 24,76     | 15,56     | 10,90      |

### Radius 1: speedup (T_st / T_mt)

| Imagem | 2 workers | 4 workers | 8 workers | 14 workers |
|--------|----------:|----------:|----------:|-----------:|
| 5K     | 2,60×     | 4,94×     | 8,38×     | 11,20×     |
| 6K     | 2,48×     | 4,98×     | 9,78×     | 13,21×     |
| 8K     | 3,19×     | 6,32×     | 10,06×    | 14,36×     |

### Radius 2: tempo (s)

| Imagem | Single-thread | 2 workers | Speedup |
|--------|--------------:|----------:|--------:|
| 5K     | 150,76        | 64,84     | 2,33×   |
| 6K     | 169,21        | 72,47     | 2,33×   |
| 8K     | 346,30        | 151,11    | 2,29×   |

### Raios maiores (5K, 14 workers)

| Radius | Tempo (s) |
|--------|----------:|
| 5      | 60,89     |
| 10     | 224,95    |

Dados brutos em [`docs/results.xlsx`](docs/results.xlsx).

### Análise

- O tempo cai de forma consistente à medida que se adicionam workers. Com 14 workers, a imagem 8K com radius 1 passa de **~2,6 minutos para ~11 segundos**.
- O ganho é maior em imagens maiores, porque o custo fixo de criar os processos e a memória compartilhada fica diluído em mais trabalho útil.
- Alguns speedups ficaram **acima do número de workers** (por exemplo, 2,60× com 2 workers). Isso indica que a versão paralela não é mais rápida apenas pelo paralelismo: ela também lê os pixels direto de um buffer de bytes (`memoryview`), enquanto a versão sequencial usa o acesso por pixel do Pillow (`image.load()`), que é mais lento. Para isolar o ganho do paralelismo, o ideal é comparar a versão paralela com ela mesma usando 1 worker.
- Com raios maiores, o custo por pixel cresce com o quadrado do raio, como esperado.

---

## Como executar

### Criar e ativar o ambiente virtual

```bash
py -m venv .venv
.venv\Scripts\activate
```

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Executar

```bash
py .\src\single-thread.py --image 5k --radius 2
py .\src\multi-thread.py -i 5k -r 2 -w 4
```

Parâmetros:

- `-i` ou `--image`: imagem (`5k`, `6k` ou `8k`)
- `-r` ou `--radius`: raio do blur (≥ 0)
- `-w` ou `--workers`: número de processos (apenas na versão paralela; padrão: número de núcleos lógicos)

A imagem resultante é salva na pasta `outputs` (criada automaticamente):

```bash
outputs\5k_r2_single.jpg
outputs\5k_r2_multi_w4.jpg
```

---

## Estrutura

```
image-processing/
├── docs/
│   └── results.xlsx        # tempos medidos
├── images/                 # imagens de entrada (5K, 6K, 8K)
├── src/
│   ├── single-thread.py    # versão sequencial
│   └── multi-thread.py     # versão paralela (processos + SharedMemory)
├── requirements.txt
└── README.md
```