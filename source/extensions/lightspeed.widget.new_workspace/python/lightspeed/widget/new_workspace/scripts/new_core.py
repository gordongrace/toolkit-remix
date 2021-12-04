"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""

import functools

import carb.settings
import omni.kit.commands
import omni.kit.viewport
import omni.usd
from pathlib import Path

from lightspeed.layer_manager.scripts.core import LayerManagerCore, LayerType
from lightspeed.layer_manager.scripts.layers.replacement import LSS_LAYER_GAME_NAME

import typing

if typing.TYPE_CHECKING:
    from lightspeed.widget.content_viewer.scripts.core import ContentData


class NewGameWorkspaceCore:
    def __init__(self):
        self.__default_attr = {"_stage_event_sub": None}
        for attr, value in self.__default_attr.items():
            setattr(self, attr, value)

        self._layer_manager = LayerManagerCore()

        self.__fns_to_execute_on_event = []

    def load_game_workspace(self, path, callback=None):
        context = omni.usd.get_context()
        context.new_stage_with_callback(functools.partial(self.__load_game_workspace, path, callback=callback))

    def __load_game_workspace(self, path, result: bool, error: str, callback=None):
        if callback:
            self.__fns_to_execute_on_event.append(callback)
        context = omni.usd.get_context()
        context.open_stage(path)
        self._layer_manager.set_edit_target_layer(LayerType.replacement)

    def create_game_workspace(
        self, capture_data, use_existing_layer, existing_enhancement_layer_path, game, callback=None
    ):
        context = omni.usd.get_context()
        context.new_stage_with_callback(
            functools.partial(
                self.__create_game_workspace,
                capture_data,
                use_existing_layer,
                existing_enhancement_layer_path,
                game,
                callback=callback,
            )
        )

    def __create_game_workspace(
        self,
        capture_data: "ContentData",
        use_existing_layer: bool,
        enhancement_layer_path: str,
        game: "ContentData",
        result: bool,
        error: str,
        callback=None,
    ):
        if callback:
            self.__fns_to_execute_on_event.append(callback)
        self._setup_stage_event()
        carb.log_info("Create game workspace")
        # first we add the capture layer
        self._layer_manager.insert_sublayer(capture_data.path, LayerType.capture)
        self._layer_manager.lock_layer(LayerType.capture)

        # add the replacement layer if exist

        layer_instance = self._layer_manager.get_layer_instance(LayerType.replacement)
        if layer_instance is None:
            carb.log_error(f"Can't find a layer schema type {LayerType.ego_configuration.value}")
            return
        layer_instance.set_custom_layer_data({LSS_LAYER_GAME_NAME: game.title})
        if use_existing_layer:
            self._layer_manager.insert_sublayer(enhancement_layer_path, LayerType.replacement)
        else:  # if not, we create it
            self._layer_manager.create_new_sublayer(LayerType.replacement, path=enhancement_layer_path)

    def _setup_stage_event(self):
        """We listen to stage event when we are running but turn it off otherwise"""
        self._stage_event_sub = (
            omni.usd.get_context()
            .get_stage_event_stream()
            .create_subscription_to_pop(self._on_stage_event, name="Load Game Workspace Core")
        )

    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.ASSETS_LOADED):
            if self.__fns_to_execute_on_event:
                for fn_to_execute_on_event in self.__fns_to_execute_on_event:
                    fn_to_execute_on_event()
            self._stage_event_sub = None
            self.__fns_to_execute_on_event = []

    def destroy(self):
        self.__fns_to_execute_on_event = []
        for attr, value in self.__default_attr.items():
            m_attr = getattr(self, attr)
            if isinstance(m_attr, list):
                m_attrs = m_attr
            else:
                m_attrs = [m_attr]
            for m_attr in m_attrs:
                destroy = getattr(m_attr, "destroy", None)
                if callable(destroy):
                    destroy()
                del m_attr
                setattr(self, attr, value)
