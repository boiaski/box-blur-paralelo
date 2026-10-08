from os import cpu_count
from pathlib import Path
from argparse import ArgumentParser
from concurrent.futures import ProcessPoolExecutor
from multiprocessing.shared_memory import SharedMemory
from time import perf_counter
from typing import cast

from PIL import Image

_source_memory: SharedMemory | None = None
_output_memory: SharedMemory | None = None
_width = 0
_height = 0
_radius = 0


def start_worker(
    source_name: str,
    output_name: str,
    width: int,
    height: int,
    radius: int,
) -> None:
    global _source_memory, _output_memory, _width, _height, _radius

    _source_memory = SharedMemory(source_name)
    _output_memory = SharedMemory(output_name)
    
    _width = width
    _height = height
    _radius = radius


def process_rows(row_range: tuple[int, int]) -> None:
    if _source_memory is None or _output_memory is None:
        raise RuntimeError("Worker shared memory was not initialized.")

    source = cast(memoryview, _source_memory.buf)
    output = cast(memoryview, _output_memory.buf)
    start_y, end_y = row_range

    #? Loop top to bottom and left to right
    for y in range(start_y, end_y):
        for x in range(_width):
            red = 0
            green = 0
            blue = 0
            count = 0

            #? Loop surrounding pixels within specified radius
            for dy in range(-_radius, _radius + 1):
                for dx in range(-_radius, _radius + 1):
                    #? Neighboring pixel coordinates
                    ny = y + dy
                    nx = x + dx

                    #? Ignore pixels outside boundaries
                    is_inside = 0 <= ny < _height and 0 <= nx < _width
                    if not is_inside: continue

                    #? Get pixel values and accumulate
                    pixel_index = (ny * _width + nx) * 3

                    red += source[pixel_index]
                    green += source[pixel_index + 1]
                    blue += source[pixel_index + 2]

                    count += 1

            output_index = (y * _width + x) * 3
            output[output_index] = red // count
            output[output_index + 1] = green // count
            output[output_index + 2] = blue // count


def box_blur(image: Image.Image, radius: int, workers: int) -> Image.Image:
    width, height = image.size
    worker_count = min(workers, height)
    pixel_data = image.tobytes()
    source_memory = SharedMemory(create=True, size=len(pixel_data))
    output_memory = None

    try:
        output_memory = SharedMemory(create=True, size=len(pixel_data))
        cast(memoryview, source_memory.buf)[:] = pixel_data
        rows_per_worker = (height + worker_count - 1) // worker_count
        row_ranges = [
            (start_y, min(start_y + rows_per_worker, height))
            for start_y in range(0, height, rows_per_worker)
        ]

        with ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=start_worker,
            initargs=(source_memory.name, output_memory.name, width, height, radius),
        ) as executor:
            list(executor.map(process_rows, row_ranges))

        output_data = cast(memoryview, output_memory.buf)
        return Image.frombytes("RGB", (width, height), bytes(output_data))

    finally:
        source_memory.close()
        source_memory.unlink()

        if output_memory is not None:
            output_memory.close()
            output_memory.unlink()


def main():
    parser = ArgumentParser()
    parser.add_argument("-i", "--image", choices=("5k", "6k", "8k"), required=True)
    parser.add_argument("-r", "--radius", type=int, required=True)
    parser.add_argument("-w", "--workers", type=int, default=cpu_count() or 1)
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent.parent
    image_path = project_dir / "images" / f"{args.image}.jpg"
    radius = args.radius

    if radius < 0:
        parser.error("radius must be zero or greater")

    if args.workers < 1:
        parser.error("workers must be greater than zero")

    image = Image.open(image_path).convert("RGB")

    print(f"Imagem: {args.image}.jpg")
    print(f"Resolução: {image.width}x{image.height}")
    print(f"Radius: {radius}")
    print(f"Workers: {args.workers}\n")

    start = perf_counter()
    output = box_blur(image, radius, args.workers)
    end = perf_counter()

    elapsed = end - start
    print(f"Tempo: {elapsed:.4f} segundos")

    output_dir = project_dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{args.image}_r{radius}_multi_w{args.workers}.jpg"
    output.save(output_path)
    print(f"Imagem salva em: {output_path}")


if __name__ == "__main__": main()