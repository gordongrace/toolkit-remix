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
import omni.kit.app

from .ui import CaptureSwapperWindow


class CaptureSwapperWindowExtension(omni.ext.IExt):
    """Standard extension support class, necessary for extension management"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_attr = {"_window": None}
        for attr, value in self.default_attr.items():
            setattr(self, attr, value)

    def on_startup(self, ext_id):
        carb.log_info("[lightspeed.window.capture_swapper] Lightspeed Capture Swapper Window startup")
        extension_path = omni.kit.app.get_app().get_extension_manager().get_extension_path(ext_id)
        self._window = CaptureSwapperWindow(extension_path)

    def on_shutdown(self):
        carb.log_info("[lightspeed.window.capture_swapper] Lightspeed Capture Swapper Window shutdown")
        for attr, value in self.default_attr.items():
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
