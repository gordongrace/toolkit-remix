"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import typing
from typing import Dict, List

from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from pxr import Tf, Usd

if typing.TYPE_CHECKING:
    from .model import ListModel


class USDListener:
    def __init__(self):
        """USD listener for the property widget"""
        self._default_attr = {"_listeners": {}}
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)
        self.__models: List["ListModel"] = []
        self._listeners: Dict[Usd.Stage, Tf.Listener] = {}

    def _enable_listener(self, stage: Usd.Stage):
        """Enable the USD listener to see if an attribute is changed"""
        assert stage not in self._listeners
        self._listeners[stage] = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._on_usd_changed, stage)

    def _disable_listener(self, stage: Usd.Stage):
        """Disable the USD listener"""
        if stage in self._listeners:
            self._listeners[stage].Revoke()
            self._listeners.pop(stage)

    def _on_usd_changed(self, notice, stage):
        for model in self.__models:
            if stage != model.stage:
                continue

            should_refresh = False
            all_items = None
            for resynced_path in notice.GetResyncedPaths():
                if "." in str(resynced_path):  # an attribute
                    continue
                prim = stage.GetPrimAtPath(resynced_path)
                if not prim.IsValid():
                    continue
                if all_items is None:
                    all_items = [item_prim.prim for item_prim in model.get_all_items() if hasattr(item_prim, "prim")]
                if prim not in all_items:
                    continue

                should_refresh = True
                break

            if should_refresh:
                model.refresh()

    def refresh_all(self):
        """Refresh all attributes"""
        for model in self.__models:
            model.refresh()

    def add_model(self, model: "ListModel"):
        """
        Add a model and delegate to listen to

        Args:
            model: the model to listen
        """
        if not any(f for f in self.__models if f.stage == model.stage):
            self._enable_listener(model.stage)

        self.__models.append(model)

    def remove_model(self, model: "ListModel"):
        """
        Remove a model and delegate that we were listening to

        Args:
            model: the listened model
        """
        if model in self.__models:
            self.__models.remove(model)
        if not any(f for f in self.__models if f.stage == model.stage):
            self._disable_listener(model.stage)

    def destroy(self):
        self.__models = None
        for listener in self._listeners.values():
            listener.Revoke()

        _reset_default_attrs(self)