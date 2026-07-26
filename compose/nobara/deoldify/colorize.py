import argparse

from deoldify import device
from deoldify.device_id import DeviceId
from deoldify.visualize import get_image_colorizer

device.set(device=DeviceId.GPU0)

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("output")
parser.add_argument("--render_factor", type=int, default=35)
args = parser.parse_args()

colorizer = get_image_colorizer(artistic=True)
result = colorizer.get_transformed_image(
    args.input, render_factor=args.render_factor, watermarked=False
)
result.save(args.output)
