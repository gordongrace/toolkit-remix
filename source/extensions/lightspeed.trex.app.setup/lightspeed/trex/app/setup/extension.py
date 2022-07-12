# Copyright (c) 2018-2020, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#
import carb
import omni.ext

from .setup_ui import SetupUI

_WINDOW = None


def get_instance():
    return _WINDOW


class TrexSetupExtension(omni.ext.IExt):
    """Create Final Configuration"""

    def __init__(self):
        self._setup = None

    def on_startup(self, ext_id):
        global _WINDOW
        carb.log_info("[lightspeed.trex.app.setup] Startup")
        self._setup_ui = SetupUI()
        _WINDOW = self._setup_ui.get_window()

    def on_shutdown(self):
        carb.log_info("[lightspeed.trex.app.setup] Shutdown")
        self._setup_ui.destroy()
        global _WINDOW
        _WINDOW = None
        self._setup_ui = None