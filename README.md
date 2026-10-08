# IMAGE PROCESSING

## How to run

### Create a virtual environment

```bash
py -m venv .venv
```

### Install dependencies with

```bash
pip install -r requirements.txt
```

### Run scripts with

```bash
py .\src\single-thread.py --image 5k --radius 2
py .\src\multi-thread.py -i 5k -r 2 -w 4
```

Parameters:

- `-i` or `--image`: image name (`5k`, `6k`, or `8k`)
- `-r` or `--radius`: blur radius
- `-w` or `--workers`: number of processes to use

The output is saved in the `outputs` folder (created automatically):

```bash
outputs\5k_r2_single.jpg
outputs\5k_r2_multi_w4.jpg
```