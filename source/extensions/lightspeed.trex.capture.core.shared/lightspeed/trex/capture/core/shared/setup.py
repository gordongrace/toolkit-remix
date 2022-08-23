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
import functools
from pathlib import Path
from typing import List, Optional

import carb
import omni.client
import omni.usd
from lightspeed.common.constants import CAPTURE_FOLDER
from lightspeed.layer_manager.core import LayerManagerCore as _LayerManagerCore
from lightspeed.layer_manager.layer_types import LayerType, LayerTypeKeys
from lightspeed.upscale.core import UpscalerCore
from omni.flux.utils.common import async_wrap as _async_wrap
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from PIL import Image
from pxr import Gf, Sdf, Usd, UsdGeom


class Setup:
    def __init__(self, context: omni.usd.UsdContext):
        self._default_attr = {"_layer_manager": None}
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)
        self.__directory = None
        self._context = context
        self._layer_manager = _LayerManagerCore(context=context)

    def get_layer(self):
        return self._layer_manager.get_layer(LayerType.capture)

    @omni.usd.handle_exception
    async def ___deferred_setup_persepctive_camera(self):
        await omni.kit.app.get_app().next_update_async()

        # setup the session camera to match the capture camera
        stage = self._context.get_stage()
        capture_layer = self._layer_manager.get_layer(LayerType.capture)
        if capture_layer is None:
            carb.log_warn("Can't find a capture layer, won't be setting up the default camera to match game")
            return
        session_layer = stage.GetSessionLayer()
        with contextlib.suppress(Exception):
            with Usd.EditContext(stage, session_layer):
                carb.log_info("Setting up perspective camera from capture")
                camera_path = "/OmniverseKit_Persp"
                Sdf.CopySpec(capture_layer, "/RootNode/Camera", session_layer, camera_path)

                camera_prim = stage.GetPrimAtPath(camera_path)
                xf_tr = camera_prim.GetProperty("xformOp:translate")
                translate = xf_tr.Get()
                zlen = Gf.Vec3d(translate[0], translate[1], translate[2]).GetLength()
                center_of_interest = Gf.Vec3d(0, 0, -zlen)
                camera_prim.CreateAttribute(
                    "omni:kit:centerOfInterest", Sdf.ValueTypeNames.Vector3d, True, Sdf.VariabilityUniform
                ).Set(center_of_interest)

    def __copy_metadata_from_stage_to_stage(self, stage_source, stage_destination):
        # copy over layer-meta-data from capture layer
        with Usd.EditContext(stage_destination, stage_destination.GetRootLayer()):
            UsdGeom.SetStageUpAxis(stage_destination, UsdGeom.GetStageUpAxis(stage_source))
            UsdGeom.SetStageMetersPerUnit(stage_destination, UsdGeom.GetStageMetersPerUnit(stage_source))
            time_codes = stage_source.GetTimeCodesPerSecond()
            stage_destination.SetTimeCodesPerSecond(time_codes)

    @staticmethod
    def is_path_valid(path: str) -> bool:
        if not path or not path.strip():
            carb.log_error(f"{path} is not valid")
            return False
        _, entry = omni.client.stat(path)
        if not (entry.flags & omni.client.ItemFlags.CAN_HAVE_CHILDREN):  # noqa PLC0325
            carb.log_error(f"{path} is not a directory")
            return False
        return True

    @staticmethod
    def get_game_icon_from_folder(folder_path: str) -> Optional[str]:
        icons = list(Path(folder_path).glob("*_icon.bmp"))
        return str(icons[0]) if icons else None

    @staticmethod
    def get_upscaled_game_icon_from_folder(folder_path: str) -> Optional[str]:
        default_icon = Setup.get_game_icon_from_folder(folder_path)
        if not default_icon:
            return None
        # look for the upscaled icon
        upscaled = default_icon.replace("_icon.bmp", "_upscaled_icon.png")
        upscaled_path = Path(upscaled)
        if not upscaled_path.exists():
            # first we convert the bmp to png without alpha
            png_file = default_icon.replace("_icon.bmp", "_icon.png")
            im1 = Image.open(default_icon)
            im1 = im1.convert("RGB")
            im1.save(png_file)
            im1.close()
            # we upscale
            UpscalerCore().perform_upscale(png_file, str(upscaled_path))
        return str(upscaled_path)

    @omni.usd.handle_exception
    async def deferred_get_upscaled_game_icon_from_folder(self, folder_path: str, callback):  # noqa PLW0238
        wrapped_fn = _async_wrap(functools.partial(self.get_upscaled_game_icon_from_folder, folder_path))
        result = await wrapped_fn()
        callback(result)

    def import_capture_layer(self, path: str):
        carb.log_info(f"Import capture layer {path}")
        # copy over layer-meta-data from capture layer
        stage = self._context.get_stage()
        capture_stage = Usd.Stage.Open(path)
        self.__copy_metadata_from_stage_to_stage(capture_stage, stage)

        # delete existing one is exist
        self._layer_manager.remove_layer(LayerType.capture)
        # add the capture layer
        self._layer_manager.insert_sublayer(
            path, LayerType.capture, add_custom_layer_data=False, set_as_edit_target=False
        )
        self._layer_manager.lock_layer(LayerType.capture)
        asyncio.ensure_future(self.___deferred_setup_persepctive_camera())

    def set_directory(self, path: str):
        self.__directory = path

    def get_directory(self) -> str:
        return self.__directory

    def is_capture_file(self, path: str) -> bool:
        layer = Sdf.Layer.FindOrOpen(path)
        if not layer:
            return False
        if layer.customLayerData.get(LayerTypeKeys.layer_type.value) == LayerType.capture.value:
            return True
        return False

    def get_game_name(self, path: str) -> str:
        return self._layer_manager.get_game_name_from_path(path)

    def _check_directory(self) -> bool:
        if not self.__directory:
            carb.log_error("Please set the current directory")
            return False
        if Path(self.__directory).name != CAPTURE_FOLDER:
            carb.log_error(f"{self.__directory} is not a capture directory")
            return False
        return True

    @property
    def capture_files(self) -> List[str]:
        if not self._check_directory():
            return []
        return sorted(
            [
                str(file)
                for file in Path(self.__directory).iterdir()
                if file.is_file() and file.suffix in [".usd", ".usda", ".usdc"] and self.is_capture_file(str(file))
            ],
            reverse=True,
        )

    def get_capture_image(self, path: str) -> Optional[str]:
        image_path = Path(path).parent.joinpath(".thumbs", f"{Path(path).name}.dds")
        return str(image_path) if image_path.exists() else None

    def destroy(self):
        _reset_default_attrs(self)
