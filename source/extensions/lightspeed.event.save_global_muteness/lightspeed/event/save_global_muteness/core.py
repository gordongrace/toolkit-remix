"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import carb.settings
import omni.kit.usd.layers as _layers
import omni.usd
from lightspeed.events_manager.i_ds_event import ILSSEvent
from lightspeed.trex.utils.common import ignore_function_decorator as _ignore_function_decorator
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs

_CONTEXT = "/exts/lightspeed.event.save_global_muteness/context"


class EventLayersSaveCustomDataCore(ILSSEvent):
    def __init__(self):
        super().__init__()
        self.default_attr = {"_subscription_layer": None, "_subscription_stage": None}
        for attr, value in self.default_attr.items():
            setattr(self, attr, value)
        settings = carb.settings.get_settings()
        self._context_name = settings.get(_CONTEXT) or ""
        self._context = omni.usd.get_context(self._context_name)

    @property
    def name(self) -> str:
        """Name of the event"""
        return "LayerSaveCustomDataCore"

    def _install(self):
        """Function that will create the behavior"""
        self._install_layer_listener()

    def _install_layer_listener(self):
        self._uninstall_layer_listener()
        self._subscription_stage = self._context.get_stage_event_stream().create_subscription_to_pop(
            self.__on_load_event, name="Recent file loaded"
        )
        layers = _layers.get_layers()
        self._subscription_layer = layers.get_event_stream().create_subscription_to_pop(
            self.__on_layer_event, name="LayerChange"
        )

    def _uninstall(self):
        """Function that will delete the behavior"""
        self._uninstall_layer_listener()

    def _uninstall_layer_listener(self):
        self._subscription_layer = None
        self._subscription_stage = None

    def __on_load_event(self, event):
        if event.type in [int(omni.usd.StageEventType.OPENED)]:
            layers = _layers.get_layers()
            layers_state = layers.get_layers_state()
            # by default, we want to save the muteness into the stage
            layers_state.set_muteness_scope(True)

    @_ignore_function_decorator(attrs=["_ignore_on_event"])
    def __on_layer_event(self, event):
        payload = _layers.get_layer_event_payload(event)
        if not payload:
            return
        if payload.event_type == _layers.LayerEventType.MUTENESS_STATE_CHANGED:
            # because we are in a global muteness scope, we need to save the root layer to save the state of the
            # muteness. Kit doesn't detect by default when we changed the scope + muted a layer. So we set the stage
            # as pending edit.
            self._context.set_pending_edit(True)

    def destroy(self):
        self._uninstall()
        _reset_default_attrs(self)
