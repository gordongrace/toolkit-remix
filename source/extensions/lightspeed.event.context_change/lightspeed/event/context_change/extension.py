"""
* SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
* SPDX-License-Identifier: Apache-2.0
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* https://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
"""

import carb
import omni.ext
from lightspeed.events_manager import get_instance as _get_event_manager_instance
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs

from .clear_selection import EventClearSelectionOnContextChange


class EventContextChangeExtension(omni.ext.IExt):
    """Standard extension support class, necessary for extension management"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_attr = {"_context_changed": None}
        for attr, value in self.default_attr.items():
            setattr(self, attr, value)

    # noinspection PyUnusedLocal
    def on_startup(self, ext_id):
        carb.log_info("[lightspeed.event.load_edit_target] Lightspeed Event Context Change startup")
        self._context_changed = EventClearSelectionOnContextChange()
        _get_event_manager_instance().register_event(self._context_changed)

    def on_shutdown(self):
        carb.log_info("[lightspeed.event.load_edit_target] Lightspeed Events Context Change shutdown")
        _get_event_manager_instance().unregister_event(self._context_changed)
        _reset_default_attrs(self)