from argparse import ArgumentParser
from pathlib import Path
from time import perf_counter
from typing import cast

from PIL import Image

def box_blur(image: Image.Image, radius: int) -> Image.Image:
    width, height = image.size

    input_pixels = image.load()
    output = Image.new("RGB", (width, height))
    output_pixels = output.load()

    if input_pixels is None or output_pixels is None:
        raise ValueError("Failed to load pixel data from the image.")

    #? Loop top to bottom and left to right
    for y in range(height):
        for x in range(width):
            red = 0
            green = 0
            blue = 0
            count = 0

            #? Loop surrounding pixels within specified radius
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    #? Neighboring pixel coordinates
                    ny = y + dy
                    nx = x + dx

                    #? Ignore pixels outside boundaries
                    is_inside = 0 <= ny < height and 0 <= nx < width
                    if not is_inside: continue

                    #? Get pixel values and accumulate
                    r, g, b = cast(tuple[int, int, int], input_pixels[nx, ny])

                    red += r
                    green += g
                    blue += b

                    count += 1

            output_pixels[x, y] = (
                red // count,
                green // count,
                blue // count
            )

    return output


def main():
    parser = ArgumentParser()
    parser.add_argument("-i", "--image", choices=("5k", "6k", "8k"), required=True)
    parser.add_argument("-r", "--radius", type=int, required=True)
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent.parent
    image_path = project_dir / "images" / f"{args.image}.jpg"
    radius = args.radius

    if radius < 0:
        parser.error("radius must be zero or greater")

    image = Image.open(image_path).convert("RGB")

    print(f"Imagem: {args.image}.jpg")
    print(f"Resolução: {image.width}x{image.height}")
    print(f"Radius: {radius}\n")

    start = perf_counter()
    output = box_blur(image, radius)
    end = perf_counter()

    elapsed = end - start
    print(f"Tempo: {elapsed:.4f} segundos")

    output_dir = project_dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{args.image}_r{radius}_single.jpg"
    output.save(output_path)
    print(f"Imagem salva em: {output_path}")


if __name__ == "__main__": main()