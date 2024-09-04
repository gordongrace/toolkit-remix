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

from asyncio import ensure_future
from functools import partial

import carb
from omni import ui
from omni.flux.stage_manager.core import StageManagerCore as _StageManagerCore
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from omni.kit import app


class StageManagerWidget:
    def __init__(
        self,
        core: _StageManagerCore,
        tab_height: int = 32,
        tab_padding: int = 32,
        active_style: str = "WorkspaceBackground",
        inactive_style: str = "TransparentBackground",
    ):
        for attr, value in self.default_attr.items():
            setattr(self, attr, value)

        self._core = core
        self._tab_height = tab_height
        self._tab_padding = tab_padding
        self._active_style = active_style
        self._inactive_style = inactive_style

        self._tab_backgrounds = {}
        self._frames = {}
        self._active_interaction = -1

        self.__resize_task = None

        self.build_ui()

    @property
    def default_attr(self) -> dict[str, None]:
        return {
            "_core": None,
            "_tab_height": None,
            "_tab_padding": None,
            "_active_style": None,
            "_inactive_style": None,
            "_tabs": None,
            "_frames": None,
            "_active_interaction": None,
        }

    def build_ui(self):
        # If no interactions are enabled, display a message
        enabled_interactions = [i for i in self._core.schema.interactions if i.enabled]
        if not enabled_interactions:
            with ui.ZStack():
                ui.Rectangle(name=self._active_style)
                ui.Label("No interactions enabled.", name="TreePanelTitleItemTitle", alignment=ui.Alignment.CENTER)
            return

        # Clear the cached dictionaries
        self._tab_backgrounds.clear()
        self._frames.clear()

        # Build the widget
        with ui.ZStack():
            ui.Rectangle(name="TabBackground")
            with ui.VStack():
                # Stack the tabs horizontally
                with ui.HStack(height=0):
                    for index, interaction in enumerate(enabled_interactions):
                        with ui.ZStack(
                            width=0,
                            height=ui.Pixel(self._tab_height),
                            tooltip=interaction.tooltip,
                            mouse_released_fn=partial(self._select_tab, index),
                        ):
                            # Cache the tab widgets
                            self._tab_backgrounds[id(interaction)] = ui.Rectangle(name=self._inactive_style)
                            ui.Label(
                                interaction.display_name,
                                name="PropertiesWidgetLabel",
                                alignment=ui.Alignment.CENTER,
                            )

                for interaction in enabled_interactions:
                    # Cache the interaction widgets
                    self._frames[id(interaction)] = ui.ZStack(visible=False)
                    with self._frames[id(interaction)]:
                        ui.Rectangle(name=self._active_style)
                        interaction.build_ui()

        # Set the first tab as active
        self._select_tab(0)
        self._resize_tabs()

    def _select_tab(self, index: int, *args):
        """
        Set a given tab to be active

        Args:
            index: The interaction index to set active
            *args: 0 -> x
                   1 -> y
                   2 -> button
                   3 -> modifier
        """
        # Only trigger on button == 0 (Left Click) if coming from mouse released event
        if len(args) == 4 and args[2] != 0:
            return

        # Quick return if the active interaction is the selected tab
        if self._active_interaction == index:
            return
        self._active_interaction = index

        # Reset the widget to the original state
        for tab in self._tab_backgrounds.values():
            tab.name = self._inactive_style
        for frame in self._frames.values():
            frame.visible = False

        # Set the interaction tab and frame to active
        enabled_interactions = [i for i in self._core.schema.interactions if i.enabled]
        if index >= len(enabled_interactions):
            carb.log_warn("An invalid tab was selected.")
            return

        interaction = enabled_interactions[index]
        self._tab_backgrounds[id(interaction)].name = self._active_style
        self._frames[id(interaction)].visible = True

    def _resize_tabs(self):
        """
        Fire and forget the `_resize_tabs_deferred` asynchronous method
        """
        if self.__resize_task:
            self.__resize_task.cancel()
        self.__resize_task = ensure_future(self._resize_tabs_deferred())

    async def _resize_tabs_deferred(self):
        """
        Wait 1 frame for the widget to be drawn on screen, then resize all the tabs to be the same size as the largest
        tab rendered.
        """
        await app.get_app().next_update_async()

        if not self._tab_backgrounds:
            return

        widest_tab = max(w.computed_width for w in self._tab_backgrounds.values())
        tab_width = (ui.Workspace.get_dpi_scale() * widest_tab) + self._tab_padding

        for tab in self._tab_backgrounds.values():
            tab.width = ui.Pixel(tab_width)

    def destroy(self):
        if self.__resize_task:
            self.__resize_task.cancel()
            self.__resize_task = None

        _reset_default_attrs(self)