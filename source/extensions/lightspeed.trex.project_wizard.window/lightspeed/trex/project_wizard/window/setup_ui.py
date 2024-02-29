"""
* Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import asyncio
from functools import partial
from typing import Dict, Optional

import carb.settings
import omni.kit.app
from lightspeed.error_popup.window import ErrorPopup as _ErrorPopup
from lightspeed.trex.project_wizard.core import SETTING_JUNCTION_NAME as _SETTING_JUNCTION_NAME
from lightspeed.trex.project_wizard.core import ProjectWizardCore as _ProjectWizardCore
from lightspeed.trex.project_wizard.core import ProjectWizardKeys as _ProjectWizardKeys
from lightspeed.trex.project_wizard.start_page.widget import WizardStartPage as _WizardStartPage
from lightspeed.trex.utils.widget import TrexMessageDialog as _TrexMessageDialog
from omni import ui, usd
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from omni.flux.wizard.widget import WizardModel as _WizardModel
from omni.flux.wizard.window import WizardWindow as _WizardWindow


class ProjectWizardWindow:
    def __init__(self, context_name: str = "", width: int = 700, height: int = 400):
        self._default_attrs = {
            "_context_name": None,
            "_wizard_core": None,
            "_wizard_window": None,
            "_wizard_completed_sub": None,
            "_setup_finished_sub": None,
        }
        for attr, value in self._default_attrs.items():
            setattr(self, attr, value)

        self._context_name = context_name
        self._wizard_core = _ProjectWizardCore()

        self._wizard_window = _WizardWindow(
            _WizardModel(_WizardStartPage(context_name=self._context_name)),
            title="RTX Remix Project Wizard",
            width=width,
            height=height,
            flags=ui.WINDOW_FLAGS_NO_DOCKING
            | ui.WINDOW_FLAGS_NO_COLLAPSE
            | ui.WINDOW_FLAGS_NO_SCROLLBAR
            | ui.WINDOW_FLAGS_NO_SCROLL_WITH_MOUSE
            | ui.WINDOW_FLAGS_NO_MOVE
            | ui.WINDOW_FLAGS_NO_RESIZE,
        )

        self._wizard_completed_sub = self._wizard_window.widget.subscribe_wizard_completed(self._on_wizard_completed)

    @usd.handle_exception
    async def __reset_setup_finished_sub(self):
        await omni.kit.app.get_app().next_update_async()
        self._setup_finished_sub = None

    def _on_wizard_completed(self, payload: Dict):
        def _do():
            self._setup_finished_sub = self._wizard_core.subscribe_run_finished(
                partial(self._on_setup_completed, payload)
            )
            self._wizard_core.setup_project(payload)

        isettings = carb.settings.get_settings()
        force_junction = isettings.get(_SETTING_JUNCTION_NAME)  # junction doesn't need admin right

        if (
            any(
                [
                    self._wizard_core.need_project_directory_symlink(schema=payload),
                    self._wizard_core.need_deps_directory_symlink(schema=payload),
                ]
            )
            and not force_junction
        ):
            _TrexMessageDialog(
                title="Elevated Privileges Required",
                message=(
                    'You will be prompted with a "User Account Control" window.\n\n'
                    "RTX Remix requires elevated privileges to symlink your project in your game install directory.\n\n"
                    "Without elevated privileges the project creation will fail."
                ),
                disable_cancel_button=True,
                ok_handler=_do,
            )
        else:
            _do()

    def _on_setup_completed(self, payload: Dict, success: bool, error: Optional[str]):
        if not success:
            _ErrorPopup(
                "Project Creation Error Occurred",
                "An error occurred while creating the project.",
                details=error,
                window_size=(400, 250),
            ).show()
            return
        usd.get_context(self._context_name).open_stage(str(payload.get(_ProjectWizardKeys.PROJECT_FILE.value, "")))
        # reset in async after 1 frame because we can't reset a sub from the sub itself
        asyncio.ensure_future(self.__reset_setup_finished_sub())

    def show_project_wizard(self, reset_page: bool = True):
        self._wizard_window.show_wizard(reset_page=reset_page)

    def destroy(self):
        _reset_default_attrs(self)
