"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""

import asyncio
import contextlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import carb
import carb.tokens
import numpy as np
import omni.usd
from lightspeed.common import constants
from PIL import Image


class ColorToNormalCore:
    @staticmethod
    def perform_conversion(texture, output_texture):
        # Get the paths to the nvtt process for format conversion and pix2pix for access to the nueral net driver
        if os.path.exists(output_texture):
            carb.log_info("Skipping " + texture + " since " + output_texture + " already exists.")
            return
        if not output_texture.lower().endswith(".dds") and not output_texture.lower().endswith(".png"):
            carb.log_info("Output texture " + output_texture + "must be either png or dds format.")
            return
        nvtt_path = constants.NVTT_PATH
        converter_path = Path(constants.PIX2PIX_TEST_SCRIPT_PATH)
        converter_dir = Path(constants.PIX2PIX_ROOT_PATH)
        # Copy the neural net data files over to the driver if they don't already exist
        neural_net_data_path = Path(constants.PIX2PIX_CHECKPOINTS_PATH).joinpath("Color_NormalDX")
        if not neural_net_data_path.exists():
            shutil.copytree(str(Path(__file__).parent.joinpath("tools", "Color_NormalDX")), neural_net_data_path)
        # Set up the path to where the neural net driver leaves the results of the conversion
        result_path = Path(constants.PIX2PIX_RESULTS_PATH).joinpath(
            "Color_NormalDX", "test_latest", "images", "texture_fake_B.png"
        )
        # Create temp dir and set up texture name/path
        original_texture_name = Path(texture).stem
        temp_dir = tempfile.TemporaryDirectory().name
        test_path = Path(temp_dir).joinpath("test", "texture", "texture.png")
        test_path.parent.mkdir(parents=True, exist_ok=True)
        carb.log_info("Converting: " + texture)
        # Convert the input image to a PNG if it already isn't
        if not texture.lower().endswith(".png"):
            png_texture_path = Path(temp_dir).joinpath(original_texture_name + ".png")
            convert_png_process = subprocess.Popen(
                [str(nvtt_path), texture, "--output", str(png_texture_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            convert_png_process.wait()
            # use PILLOW as a fallback if nvtt fails
            if png_texture_path.exists():
                with contextlib.suppress(NotImplementedError):
                    with Image.open(texture) as im:
                        im.save(png_texture_path, "PNG")
        else:
            png_texture_path = texture
        # Double the width of the input image so that the neural net driver thinks there's a known result for comparison
        # This can be just empty since it's not used in any way, but is the required input format
        try:
            with Image.open(png_texture_path) as im:
                width, height = im.size
                im = im.crop((0, 0, width * 2, height))
                im.save(test_path, "PNG")
        except NotImplementedError:
            return
        # Create the dirtectory for the output and delete the results directory if it exists
        Path(output_texture).parent.mkdir(parents=True, exist_ok=True)
        if result_path.exists():
            result_path.unlink()
        # Configure environment to find kit's python.pipapi libraries
        python_path = carb.tokens.get_tokens_interface().resolve("${python}")
        separator = ";" if platform.system() == "Windows" else ":"
        pythonpath_env = separator.join(sys.path)[1:]  # strip leading colon
        new_env = os.environ.copy()
        new_env["PYTHONPATH"] = pythonpath_env
        # Perform the conversion
        conversion_process = subprocess.Popen(
            [
                python_path,
                str(converter_path),
                "--dataroot",
                temp_dir,
                "--name",
                "Color_NormalDX",
                "--model",
                "pix2pix",
                "--num_test",
                "1",
                "--gpu_ids",
                "-1",
                "--preprocess",
                "scale_width",
                "--load_size",
                "1024",
            ],
            cwd=str(converter_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env=new_env,
        )
        conversion_process.wait()
        # The resulting normal map isn't guarenteed to have perfectly normal vector values, so we need to normalize it
        # Then convert to octohedral encoding
        with Image.open(str(result_path)) as im:
            normal_map_array = (np.asarray(im) / 255)[:, :, 0:3]
            normal_map_array = (normal_map_array * 2) - 1
            squared_array = np.square(normal_map_array)
            summed_array = np.sum(squared_array, axis=2)
            sqrted_array = np.sqrt(summed_array)
            repeated_array = np.repeat(sqrted_array[:, :, np.newaxis], 3, axis=2)
            normalized_array = normal_map_array / repeated_array
            # Invert Red!
            normalized_array[:, :, 0] = -1 * normalized_array[:, :, 0]
            rescaled_array = ((normalized_array + 1) / 2) * 255
            rounded_array = np.round(rescaled_array)
            hemi_sphere_array = 2 * ((np.asarray(rounded_array) / 255)[:, :, 0:3]) - 1
            hemi_mag = np.sqrt(
                np.square(hemi_sphere_array[:, :, 0][:, :, np.newaxis])
                + np.square(hemi_sphere_array[:, :, 1][:, :, np.newaxis])
                + np.square(hemi_sphere_array[:, :, 2][:, :, np.newaxis])
            )
            hemi_sphere_array = hemi_sphere_array / np.repeat(hemi_mag, 3, axis=2)
            p = hemi_sphere_array[:, :, (0, 1)] * (
                1
                / (
                    np.absolute(hemi_sphere_array[:, :, 0][:, :, np.newaxis])
                    + np.absolute(hemi_sphere_array[:, :, 1][:, :, np.newaxis])
                    + hemi_sphere_array[:, :, 2][:, :, np.newaxis]
                )
            )
            unorm_oct_array = (
                np.clip(
                    np.dstack(
                        (
                            p[:, :, 0][:, :, np.newaxis] + p[:, :, 1][:, :, np.newaxis],
                            p[:, :, 0][:, :, np.newaxis] - p[:, :, 1][:, :, np.newaxis],
                        )
                    ),
                    -1,
                    1,
                )
                * 0.5
                + 0.5
            )
            unorm_oct_array = np.insert(unorm_oct_array, 2, 0, axis=2)
            out_im = Image.fromarray(np.uint8((unorm_oct_array * 255).round()))
            out_im.save(str(result_path))
        # Convert to DDS if necessary, and generate mips (note dont use the temp dir for this)
        if output_texture.lower().endswith(".dds"):
            compress_mip_process = subprocess.Popen(
                [
                    str(nvtt_path),
                    str(result_path),
                    "--format",
                    constants.TEXTURE_COMPRESSION_LEVELS[constants.MATERIAL_INPUTS_NORMALMAP_TEXTURE],
                    "--output",
                    output_texture,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            compress_mip_process.wait()
        else:
            shutil.copy(str(result_path), output_texture)

    @staticmethod
    @omni.usd.handle_exception
    async def async_perform_upscale(texture, output_texture):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ColorToNormalCore.perform_upscale, texture, output_texture)
