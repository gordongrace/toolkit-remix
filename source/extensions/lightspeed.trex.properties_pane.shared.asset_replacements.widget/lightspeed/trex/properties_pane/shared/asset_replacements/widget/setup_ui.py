"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import functools

import omni.ui as ui
from lightspeed.trex.material_properties.shared.widget import SetupUI as _MaterialPropertiesWidget
from lightspeed.trex.mesh_properties.shared.widget import SetupUI as _MeshPropertiesWidget
from lightspeed.trex.replacement.core.shared.layers import AssetReplacementLayersCore as _AssetReplacementLayersCore
from lightspeed.trex.selection_tree.shared.widget import SetupUI as _SelectionTreeWidget
from omni.flux.bookmark_tree.model.usd import UsdBookmarkCollectionModel as _UsdBookmarkCollectionModel
from omni.flux.bookmark_tree.widget import BookmarkTreeWidget as _BookmarkTreeWidget
from omni.flux.layer_tree.usd.widget import LayerModel as _LayerModel
from omni.flux.layer_tree.usd.widget import LayerTreeWidget as _LayerTreeWidget
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from omni.flux.utils.widget.collapsable_frame import (
    PropertyCollapsableFrameWithInfoPopup as _PropertyCollapsableFrameWithInfoPopup,
)


class AssetReplacementsPane:
    def __init__(self, context_name: str):
        """Nvidia StageCraft Components Pane"""

        self._default_attr = {
            "_core": None,
            "_root_frame": None,
            "_layer_tree_widget": None,
            "_bookmark_tree_widget": None,
            "_selection_tree_widget": None,
            "_mesh_properties_widget": None,
            "_material_properties_widget": None,
            "_layer_collapsable_frame": None,
            "_bookmarks_collapsable_frame": None,
            "_selection_collapsable_frame": None,
            "_mesh_properties_collapsable_frame": None,
            "_material_properties_collapsable_frame": None,
            "_sub_tree_selection_changed": None,
            "_sub_stage_event": None,
        }
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)

        self._context_name = context_name
        self._core = _AssetReplacementLayersCore(context_name)

        self.__tree_selection_collapsed = False

        self.__create_ui()

    def __create_ui(self):
        self._root_frame = ui.Frame()
        with self._root_frame:
            with ui.ScrollingFrame(
                name="PropertiesPaneSection",
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
            ):
                with ui.VStack():
                    ui.Spacer(height=ui.Pixel(56))

                    with ui.HStack():
                        ui.Spacer(width=ui.Pixel(8), height=ui.Pixel(0))
                        with ui.VStack():
                            ui.Spacer(height=ui.Pixel(8))
                            self._layer_collapsable_frame = _PropertyCollapsableFrameWithInfoPopup(
                                "LAYERS",
                                info_text="Visual representation of the USD layers in the mod.\n\n"
                                "NOTE: USD parent layers aggregate children layers so they have stronger opinions.\n\n"
                                "- Layers can be drag/dropped to change the hierarchy\n"
                                "- The active edit target can be changed by clicking the layer icon aligned "
                                "with the layer\n"
                                "- Layers can be deleted by clicking the Delete button aligned with the "
                                "layer\n"
                                "- Layers can be locked by clicking the Lock button aligned with the layer\n"
                                "- Layers can be muted by clicking the Mute button aligned with the layer\n"
                                "- Layers can be saved by clicking the Save button if they are not locked "
                                "and muted\n"
                                "- New layers can be created by clicking the Create button at the bottom of "
                                "the widget\n"
                                "- Existing layers can be imported by clicking the Import button at the "
                                "bottom of the widget",
                                collapsed=True,
                            )
                            with self._layer_collapsable_frame:
                                model = _LayerModel(
                                    self._context_name,
                                    self._core.get_layers_exclude_remove,
                                    self._core.get_layers_exclude_lock,
                                    self._core.get_layers_exclude_mute,
                                    self._core.get_layers_exclude_edit_target,
                                    self._core.get_layers_exclude_add_child,
                                    self._core.get_layers_exclude_move,
                                )
                                self._layer_tree_widget = _LayerTreeWidget(model=model)
                            self._layer_collapsable_frame.root.set_collapsed_changed_fn(
                                functools.partial(self.__on_collapsable_frame_changed, self._layer_tree_widget)
                            )

                            ui.Spacer(height=ui.Pixel(16))

                            self._bookmarks_collapsable_frame = _PropertyCollapsableFrameWithInfoPopup(
                                "BOOKMARKS",
                                info_text="A tree of all the bookmark collections and bookmarked items.\n\n"
                                "- Creating a bookmark will automatically parent the new item to the "
                                "currently selected collection.\n"
                                "- Both Collections and Items are sorted alphabetically.\n"
                                "- Both Items and Collections can be drag/dropped to change the hierarchy.\n"
                                "- Collections can be renamed by double-clicking on them.\n"
                                "- Items can be added or removed from collections by using the add/remove "
                                "buttons aligned with the desired collection.\n"
                                "- Selecting an item in the viewport will change the bookmark selection if "
                                "the item was bookmarked.\n"
                                "- Selecting an item in the bookmarks will select the associated item in the "
                                "viewport.\n",
                                collapsed=True,
                            )
                            with self._bookmarks_collapsable_frame:
                                model = _UsdBookmarkCollectionModel(self._context_name)
                                self._bookmark_tree_widget = _BookmarkTreeWidget(model=model)
                            self._bookmarks_collapsable_frame.root.set_collapsed_changed_fn(
                                functools.partial(self.__on_collapsable_frame_changed, self._bookmark_tree_widget)
                            )

                            ui.Spacer(height=ui.Pixel(16))

                            self._selection_collapsable_frame = _PropertyCollapsableFrameWithInfoPopup(
                                "SELECTION",
                                info_text="Tree that will shows your current viewport selection.\n\n"
                                "- The top item is the 'prototype'. A prototype is what represent the asset\n"
                                "- The prototype contains USD reference(s) (linked USD file(s)).\n"
                                "- Multiple USD reference(s) can be added or removed.\n"
                                "- USD prim hierarchy of each reference can be seen.\n"
                                "- Clicking on a prim in the hierarchy will select the prin in the viewport.\n"
                                "- 'Instances' item shows where the asset is instanced in your stage.\n"
                                "- Clicking on an instance (with a prim item selected in the hierarchy) will select "
                                "it in the viewport.\n",
                                collapsed=self.__tree_selection_collapsed,
                            )
                            with self._selection_collapsable_frame:
                                self._selection_tree_widget = _SelectionTreeWidget(self._context_name)
                            self._selection_collapsable_frame.root.set_collapsed_changed_fn(
                                self.__on_selection_collapsable_frame_changed
                            )

                            ui.Spacer(height=ui.Pixel(16))

                            self._mesh_properties_collapsable_frame = _PropertyCollapsableFrameWithInfoPopup(
                                "OBJECT PROPERTIES",
                                info_text="Mesh properties of the selected mesh(es).\n\n"
                                "- Will show different property depending of the selection from the "
                                "selection panel above. If the selection panel is hiding, it will show nothing.\n"
                                "- A blue circle tells that the property has a different value than the default one.\n"
                                "- A darker background tells that the property has override(s) from layer(s).\n"
                                "- Override(s) can be removed. The list shows the stronger layer (top) to "
                                "the weaker layer (bottom).\n",
                                collapsed=False,
                            )
                            with self._mesh_properties_collapsable_frame:
                                self._mesh_properties_widget = _MeshPropertiesWidget(self._context_name)
                            self._mesh_properties_collapsable_frame.root.set_collapsed_changed_fn(
                                functools.partial(self.__on_collapsable_frame_changed, self._mesh_properties_widget)
                            )

                            ui.Spacer(height=ui.Pixel(16))

                            self._material_properties_collapsable_frame = _PropertyCollapsableFrameWithInfoPopup(
                                "MATERIAL PROPERTIES",
                                info_text="Material properties of the selected mesh(es).\n\n"
                                "- Will show material properties depending of the selection from the "
                                "selection panel above. If the selection panel is hiding, it will show nothing.\n"
                                "- A blue circle tells that the property has a different value than the default one.\n"
                                "- A darker background tells that the property has override(s) from layer(s).\n"
                                "- Override(s) can be removed. The list shows the stronger layer (top) to "
                                "the weaker layer (bottom).\n",
                                collapsed=False,
                            )
                            with self._material_properties_collapsable_frame:
                                self._material_properties_widget = _MaterialPropertiesWidget(self._context_name)
                            self._material_properties_collapsable_frame.root.set_collapsed_changed_fn(
                                functools.partial(self.__on_collapsable_frame_changed, self._material_properties_widget)
                            )

                            ui.Spacer(height=ui.Pixel(16))

        self._sub_tree_selection_changed = self._selection_tree_widget.subscribe_tree_selection_changed(
            self._on_tree_selection_changed
        )
        self._refresh_mesh_properties_widget()
        self._refresh_material_properties_widget()

    def __on_collapsable_frame_changed(self, widget, collapsed):
        widget.show(not collapsed)

    @property
    def selection_tree_widget(self):
        return self._selection_tree_widget

    def __on_selection_collapsable_frame_changed(self, collapsed):
        self.__tree_selection_collapsed = collapsed
        self._selection_tree_widget.show(not collapsed)
        # if this is collapsed, we disable the property and material widget because those panels depend from the
        # selection in the tree. Showing the last selection can lead user to mistake(s) (difference between the viewport
        # selection and the last selection).
        if collapsed:
            self._on_tree_selection_changed([])
        else:
            self._selection_tree_widget.refresh()

    def _on_tree_selection_changed(self, items):
        self._refresh_mesh_properties_widget()
        self._refresh_material_properties_widget()
        self._mesh_properties_collapsable_frame.root.rebuild()

    def _refresh_mesh_properties_widget(self):
        if self.__tree_selection_collapsed:
            items = []
        else:
            items = self._selection_tree_widget.get_selection()
        self._mesh_properties_widget.refresh(items)

    def _refresh_material_properties_widget(self):
        if self.__tree_selection_collapsed:
            items = []
        else:
            items = self._selection_tree_widget.get_selection()
        self._material_properties_widget.refresh(items)

    def refresh(self):
        self._selection_tree_widget.refresh()
        self._refresh_mesh_properties_widget()
        self._refresh_material_properties_widget()

    def show(self, value):
        # Update the widget visibility
        self._root_frame.visible = value
        self._layer_tree_widget.show(value)
        self._bookmark_tree_widget.show(value)
        self._selection_tree_widget.show(value)
        self._mesh_properties_widget.show(value)
        self._material_properties_widget.show(value)
        if value:
            self.refresh()

    def destroy(self):
        _reset_default_attrs(self)