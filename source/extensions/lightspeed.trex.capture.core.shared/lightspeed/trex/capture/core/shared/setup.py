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
from pathlib import Path
from typing import List, Optional

import carb
import omni.usd
from lightspeed.common.constants import CAPTURE_FOLDER
from lightspeed.layer_manager.core import LayerManagerCore as _LayerManagerCore
from lightspeed.layer_manager.layer_types import LayerType, LayerTypeKeys
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from omni.kit.usd.layers import LayerUtils
from pxr import Sdf, Usd, UsdGeom


class Setup:
    def __init__(self, context: omni.usd.UsdContext):
        self._default_attr = {"_layer_manager": None}
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)
        self.__directory = None
        self._context = context
        self._layer_manager = _LayerManagerCore(context=context)

    @omni.usd.handle_exception
    async def ___deferred_setup_persepctive_camera(self):
        await omni.kit.app.get_app().next_update_async()

        # setup the session camera to match the capture camera
        stage = omni.usd.get_context().get_stage()
        capture_layer = self._layer_manager.get_layer(LayerType.capture)
        if capture_layer is None:
            carb.log_warn("Can't find a capture layer, won't be setting up the default camera to match game")
            return
        session_layer = stage.GetSessionLayer()
        current_edit_layer = Sdf.Find(LayerUtils.get_edit_target(stage))
        swap_edit_targets = current_edit_layer != session_layer
        try:
            if swap_edit_targets:
                LayerUtils.set_edit_target(stage, session_layer.identifier)

            carb.log_info("Setting up perspective camera from capture")
            Sdf.CopySpec(capture_layer, "/RootNode/Camera", session_layer, "/OmniverseKit_Persp")
        finally:
            if swap_edit_targets:
                LayerUtils.set_edit_target(stage, current_edit_layer.identifier)

    def __copy_metadata_from_stage_to_stage(self, stage_source, stage_destination):
        # copy over layer-meta-data from capture layer
        UsdGeom.SetStageUpAxis(stage_destination, UsdGeom.GetStageUpAxis(stage_source))
        UsdGeom.SetStageMetersPerUnit(stage_destination, UsdGeom.GetStageMetersPerUnit(stage_source))
        time_codes = stage_source.GetTimeCodesPerSecond()
        stage_destination.SetTimeCodesPerSecond(time_codes)

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