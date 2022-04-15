"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
from pathlib import Path

import carb
import numpy as np
from PIL import Image


class LightspeedOctahedralConverter:
    @staticmethod
    def convert_dx_file_to_octahedral(dx_path, oth_path):
        if not Path(dx_path).exists():
            carb.log_error("convert_dx_to_octahedral called on non-existant path: " + dx_path)
            return
        with Image.open(dx_path) as image_file:
            img = np.array(image_file)
            img_int = LightspeedOctahedralConverter.convert_dx_to_octahedral(img)
            Image.fromarray(img_int, "RGB").save(oth_path)

    @staticmethod
    def convert_ogl_file_to_octahedral(ogl_path, oth_path):
        if not Path(ogl_path).exists():
            carb.log_error("convert_ogl_to_octahedral called on non-existant path: " + ogl_path)
            return
        with Image.open(ogl_path) as image_file:
            img = np.array(image_file)
            img_int = LightspeedOctahedralConverter.convert_ogl_to_octahedral(img)
            Image.fromarray(img_int, "RGB").save(oth_path)

    @staticmethod
    def convert_dx_to_octahedral(image):
        normals = LightspeedOctahedralConverter._pixels_to_normals(image)
        octahedrals = LightspeedOctahedralConverter._convert_to_octahedral(normals)
        return LightspeedOctahedralConverter._octahedrals_to_pixels(octahedrals)

    @staticmethod
    def convert_ogl_to_octahedral(image):
        dx_image = LightspeedOctahedralConverter._ogl_to_dx(image)
        return LightspeedOctahedralConverter.convert_dx_to_octahedral(dx_image)

    @staticmethod
    def _pixels_to_normals(image):
        image = image[:, :, 0:3].astype("float32") / 255
        image = image * 2.0 - 1.0
        return image / np.linalg.norm(image, axis=2)[:, :, np.newaxis]

    @staticmethod
    def _octahedrals_to_pixels(octahedrals):
        image = np.floor(octahedrals * 255 + 0.5).astype("uint8")
        return np.pad(image, ((0, 0), (0, 0), (0, 1)), mode="constant")

    @staticmethod
    def _ogl_to_dx(image):
        # flip the g channel to convert to DX style
        image[:, :, (1)] = 255 - image[:, :, (1)]
        return image

    @staticmethod
    def _convert_to_octahedral(image):
        # convert from 3 channel to 2 channel normal map
        # vectorized implementation.

        # p = v.xy / (abs(v.x) + abs(v.y) + abs(v.z));
        abs_values = np.absolute(image)
        snorm_octahedrals = image[:, :, 0:2] / np.expand_dims(abs_values.sum(2), axis=2)
        result = snorm_octahedrals.copy()
        result[:, :, 0] = snorm_octahedrals[:, :, 0] + snorm_octahedrals[:, :, 1]
        result[:, :, 1] = snorm_octahedrals[:, :, 0] - snorm_octahedrals[:, :, 1]

        # snormOctahedral = (v.z >= 0.0) ? p : octWrap(p);
        needs_wrap_mask = image[:, :, 2] < 0.0
        # put abs(pixel.yx) into the result
        snorm_octahedrals[needs_wrap_mask] = abs_values[needs_wrap_mask, 1::-1]

        # create mask of lines with x < 0 and z < 0
        needs_xflip_mask = image[needs_wrap_mask, 0] < 0.0

        # create mask of lines with y < 0 and z < 0
        needs_yflip_mask = image[needs_wrap_mask, 1] < 0.0

        # use those masks to flip the y and x components of snorm_octahedrals
        snorm_octahedrals[needs_xflip_mask, 0] = -1.0 * snorm_octahedrals[needs_xflip_mask, 0]
        snorm_octahedrals[needs_yflip_mask, 1] = -1.0 * snorm_octahedrals[needs_yflip_mask, 1]

        # return snormOctahedral * 0.5 + 0.5;
        return result * 0.5 + 0.5