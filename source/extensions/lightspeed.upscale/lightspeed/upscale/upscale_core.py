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
import os.path
import subprocess
import tempfile

import carb
from lightspeed.common import constants
from lightspeed.layer_manager.scripts.core import LayerManagerCore, LayerType
from PIL import Image
from pxr import Sdf, Tf, Usd, UsdShade


class LightspeedUpscalerCore:
    # todo: this should be async job!
    @staticmethod
    def perform_upscale(texture, output_texture):
        # setup script paths'
        if os.path.exists(output_texture):
            carb.log_info("Skipping " + texture + " since " + output_texture + " already exists.")
            return
        script_path = os.path.dirname(os.path.abspath(__file__))
        nvtt_path = script_path + ".\\tools\\nvtt\\nvtt_export.exe"
        esrgan_tool_path = script_path + ".\\tools\\realesrgan-ncnn-vulkan-20210901-windows\\realesrgan-ncnn-vulkan.exe"
        # create temp dir and get texture name/path
        original_texture_name = os.path.splitext(os.path.basename(texture))[0]
        output_texture_name = os.path.splitext(os.path.basename(output_texture))[0]
        output_texture_path = os.path.dirname(os.path.abspath(output_texture))
        temp_dir = tempfile.TemporaryDirectory()
        # begin real work
        carb.log_info("Upscaling: " + texture)
        # convert to png
        if texture.lower().endswith(".dds"):
            png_texture_path = os.path.join(temp_dir.name, original_texture_name + ".png")
            carb.log_info("  - converting to png, out: " + png_texture_path)
            convert_png_process = subprocess.Popen([nvtt_path, texture, "--output", png_texture_path], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            convert_png_process.wait()
            # use PILLOW as a fallback if nvtt fails
            if not os.path.exists(png_texture_path):
                with contextlib.suppress(NotImplementedError):
                    with Image.open(texture) as im:
                        im.save(png_texture_path, "PNG")
        else:
            png_texture_path = texture
        # perform upscale
        os.makedirs(os.path.dirname(output_texture), exist_ok=True)
        upscaled_texture_path = os.path.join(output_texture_path, output_texture_name + ".png")
        carb.log_info("  - running neural networks, out: " + upscaled_texture_path)
        upscale_process = subprocess.Popen([esrgan_tool_path, "-i", png_texture_path, "-o", upscaled_texture_path], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        upscale_process.wait()
        # check for alpha channel and upscale it if it exists
        try:
            with Image.open(png_texture_path) as memory_image:
                if memory_image.mode == "RGBA":
                    alpha_path = os.path.join(temp_dir.name, original_texture_name + "_alpha.png")
                    upscaled_alpha_path = os.path.join(temp_dir.name, original_texture_name + "_upscaled4x_alpha.png")
                    memory_image.split()[-1].save(alpha_path)
                    upscale_process = subprocess.Popen([esrgan_tool_path, "-i", alpha_path, "-o", upscaled_alpha_path], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    upscale_process.wait()
                    with Image.open(upscaled_alpha_path).convert("L") as upscaled_alpha_image:
                        with Image.open(upscaled_texture_path) as upscaled_memory_image:
                            upscaled_memory_image.putalpha(upscaled_alpha_image)
                            upscaled_memory_image.save(upscaled_texture_path, "PNG")
        except FileNotFoundError:
            carb.log_info("File not found error!")
            pass
        # convert to DDS, and generate mips (note dont use the temp dir for this)
        carb.log_info("  - compressing and generating mips, out: " + output_texture)
        compress_mip_process = subprocess.Popen(
            [nvtt_path, upscaled_texture_path, "--format", "bc7", "--output", output_texture],  stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        compress_mip_process.wait()
        temp_dir.cleanup()

    @staticmethod
    def lss_collect_capture_diffuse_textures():
        layer_manager = LayerManagerCore()
        capture_layer = layer_manager.get_layer(LayerType.capture)
        capture_stage = Usd.Stage.Open(capture_layer.realPath)
        collected_prim_paths = list()
        collected_asset_absolute_paths = list()
        collected_asset_relative_paths = list()

        for prim in capture_stage.GetPrimAtPath(constants.ROOTNODE_LOOKS).GetChildren():
            if (
                not prim.GetChild(constants.SHADER)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE).Get()
            ):
                continue
            absolute_asset_path = (
                prim.GetChild(constants.SHADER)
                .GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                .Get()
                .resolvedPath
            )
            rel_path = os.path.relpath(absolute_asset_path, os.path.dirname(capture_layer.realPath))
            collected_prim_paths.append(prim.prim.GetPath())
            collected_asset_absolute_paths.append(absolute_asset_path)
            collected_asset_relative_paths.append(rel_path)
        return collected_prim_paths, collected_asset_absolute_paths, collected_asset_relative_paths

    @staticmethod
    async def lss_async_batch_perform_upscale(asset_absolute_paths, output_asset_absolute_paths, progress_callback=None):
        loop = asyncio.get_event_loop()
        assert(len(asset_absolute_paths) == len(output_asset_absolute_paths))
        total = len(asset_absolute_paths)
        for i in range(len(asset_absolute_paths)):
            # perform upscale and place the output textures next to the enhancements layer location
            await loop.run_in_executor(None, LightspeedUpscalerCore.perform_upscale, asset_absolute_paths[i], output_asset_absolute_paths[i])
            if progress_callback:
                progress_callback((i + 1) / total)

    @staticmethod
    def lss_blocking_batch_perform_upscale(asset_absolute_paths, output_asset_absolute_paths, progress_callback=None):
        assert(len(asset_absolute_paths) == len(output_asset_absolute_paths))
        total = len(asset_absolute_paths)
        for i in range(len(asset_absolute_paths)):
            # perform upscale and place the output textures next to the enhancements layer location
            LightspeedUpscalerCore.perform_upscale(asset_absolute_paths[i], output_asset_absolute_paths[i])
            if progress_callback:
                progress_callback((i + 1) / total)

    @staticmethod
    def lss_generate_populate_and_child_autoupscale_layer(prim_paths, asset_relative_paths):
        layer_manager = LayerManagerCore()
        # get/setup layers
        replacement_layer = layer_manager.get_layer(LayerType.replacement)
        # create/open and populate auto-upscale layer, placing it next to the enhancements layer
        enhancement_usd_dir = os.path.dirname(replacement_layer.realPath)
        auto_upscale_stage_filename = "autoupscale.usda"
        auto_upscale_stage_relative_path = os.path.join(".", auto_upscale_stage_filename)
        auto_upscale_stage_absolute_path = os.path.join(enhancement_usd_dir, auto_upscale_stage_filename)
        try:
            auto_stage = Usd.Stage.Open(auto_upscale_stage_absolute_path)
        except Tf.ErrorException:
            auto_stage = Usd.Stage.CreateNew(auto_upscale_stage_absolute_path)
        auto_stage.DefinePrim(constants.ROOTNODE)
        auto_stage.DefinePrim(constants.ROOTNODE_LOOKS, constants.SCOPE)

        # add the auto-upscale layer to the replacement layer as a sublayer
        # this property is supposed to be read-only, but the setter in the C++ lib are missing in the python lib
        if auto_upscale_stage_relative_path not in replacement_layer.subLayerPaths:
            index_above_capture_usd = max(0, len(replacement_layer.subLayerPaths) - 1)
            replacement_layer.subLayerPaths.insert(index_above_capture_usd, auto_upscale_stage_relative_path)
            replacement_layer.Save()

        assert(len(prim_paths) == len(asset_relative_paths))
        for index in range(len(prim_paths)):
            prim_path = prim_paths[index]
            asset_relative_path = asset_relative_paths[index]
            UsdShade.Material.Define(auto_stage, prim_path)
            shader = UsdShade.Shader.Define(auto_stage, prim_path + "/" + constants.SHADER)
            Usd.ModelAPI(shader).SetKind(constants.MATERIAL)
            shader_prim = shader.GetPrim()
            attr = shader_prim.CreateAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE, Sdf.ValueTypeNames.Asset)
            attr.Set(asset_relative_path)
            attr.SetColorSpace(constants.AUTO)
        auto_stage.GetRootLayer().Save()

    @staticmethod
    async def lss_async_batch_upscale_capture_layer(progress_callback=None):
        prim_paths, asset_absolute_paths, asset_relative_paths = LightspeedUpscalerCore.lss_collect_capture_diffuse_textures()
        output_asset_abolute_paths = [path.replace(os.path.splitext(path)[1], "_upscaled4x.dds") for path in asset_absolute_paths]
        output_asset_relative_paths = [path.replace(os.path.splitext(path)[1], "_upscaled4x.dds") for path in asset_relative_paths]
        await LightspeedUpscalerCore.lss_async_batch_perform_upscale(asset_absolute_paths, output_asset_abolute_paths, progress_callback)
        LightspeedUpscalerCore.lss_generate_populate_and_child_autoupscale_layer(prim_paths, output_asset_relative_paths)

    @staticmethod
    async def batch_upscale_capture_layer(specific_prims=None, progress_callback=None):
        layer_manager = LayerManagerCore()
        # get/setup layers
        replacement_layer = layer_manager.get_layer(LayerType.replacement)
        capture_layer = layer_manager.get_layer(LayerType.capture)
        capture_stage = Usd.Stage.Open(capture_layer.realPath)
        # create/open and populate auto-upscale layer, placing it next to the enhancements layer
        enhancement_usd_dir = os.path.dirname(replacement_layer.realPath)

        # if no specific prims are defined, then use the entire capture layer
        if specific_prims is None:
            specific_prims = capture_stage.GetPrimAtPath(constants.ROOTNODE_LOOKS).GetChildren()

        total = len(specific_prims)
        count = 0

        upscale_paths = []

        for prim in specific_prims:
            if (
                not prim.GetChild(constants.SHADER)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE).Get()
            ):
                continue
            absolute_asset_path = (
                prim.GetChild(constants.SHADER)
                .GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                .Get()
                .resolvedPath
            )
            if absolute_asset_path.lower().endswith(".dds") or absolute_asset_path.lower().endswith(".png"):
                # manipulate paths
                rel_path = os.path.relpath(absolute_asset_path, os.path.dirname(capture_layer.realPath))
                upscale_rel_path = rel_path.replace(os.path.splitext(rel_path)[1], "_upscaled4x.dds")
                output_tex_path = os.path.join(os.path.dirname(replacement_layer.realPath), upscale_rel_path)
                capture_usd_directory = os.path.dirname(capture_layer.realPath)
                original_texture_path = os.path.join(capture_usd_directory, rel_path)
                upscale_paths.append((original_texture_path, output_tex_path))

        loop = asyncio.get_event_loop()
        for paths in upscale_paths:
            # perform upscale and place the output textures next to the enhancements layer location
            await loop.run_in_executor(None, LightspeedUpscalerCore.perform_upscale, paths[0], paths[1])
            count = count + 1
            if progress_callback:
                progress_callback(count / total)

        auto_upscale_stage_filename = "autoupscale.usda"
        auto_upscale_stage_relative_path = os.path.join(".", auto_upscale_stage_filename)
        auto_upscale_stage_absolute_path = os.path.join(enhancement_usd_dir, auto_upscale_stage_filename)
        try:
            auto_stage = Usd.Stage.Open(auto_upscale_stage_absolute_path)
        except Tf.ErrorException:
            auto_stage = Usd.Stage.CreateNew(auto_upscale_stage_absolute_path)
        auto_stage.DefinePrim(constants.ROOTNODE)
        auto_stage.DefinePrim(constants.ROOTNODE_LOOKS, constants.SCOPE)

        # add the auto-upscale layer to the replacement layer as a sublayer
        # this property is supposed to be read-only, but the setter in the C++ lib are missing in the python lib
        if auto_upscale_stage_relative_path not in replacement_layer.subLayerPaths:
            index_above_capture_usd = max(0, len(replacement_layer.subLayerPaths) - 1)
            replacement_layer.subLayerPaths.insert(index_above_capture_usd, auto_upscale_stage_relative_path)
            replacement_layer.Save()

        for prim in specific_prims:
            if (
                not prim.GetChild(constants.SHADER)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                or not prim.GetChild(constants.SHADER).GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE).Get()
            ):
                continue
            absolute_asset_path = (
                prim.GetChild(constants.SHADER)
                .GetAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE)
                .Get()
                .resolvedPath
            )
            if absolute_asset_path.lower().endswith(".dds") or absolute_asset_path.lower().endswith(".png"):
                # manipulate paths
                rel_path = os.path.relpath(absolute_asset_path, os.path.dirname(capture_layer.realPath))
                upscale_rel_path = rel_path.replace(os.path.splitext(rel_path)[1], "_upscaled4x.dds")
                output_tex_path = os.path.join(os.path.dirname(replacement_layer.realPath), upscale_rel_path)
                capture_usd_directory = os.path.dirname(capture_layer.realPath)
                original_texture_path = os.path.join(capture_usd_directory, rel_path)
                UsdShade.Material.Define(auto_stage, prim.GetPath())
                origin_shader = prim.GetChild(constants.SHADER)
                shader = UsdShade.Shader.Define(auto_stage, origin_shader.GetPath())
                Usd.ModelAPI(shader).SetKind(constants.MATERIAL)
                shader_prim = shader.GetPrim()
                attr = shader_prim.CreateAttribute(constants.MATERIAL_INPUTS_DIFFUSE_TEXTURE, Sdf.ValueTypeNames.Asset)
                attr.Set(upscale_rel_path)
                attr.SetColorSpace(constants.AUTO)

        auto_stage.GetRootLayer().Save()
