"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import carb
import omni.ext
import omni.kit.app
import omni.kit.window.property
from .material_asset_widget import MaterialAssetWidget
from .mesh_asset_widget import MeshAssetWidget
from .asset_delegate import AssetDelegate


class PropertyTemplateExtension(omni.ext.IExt):
    """Standard extension support class, necessary for extension management"""

    def __init__(self, *args, **kwargs):
        super(PropertyTemplateExtension, self).__init__(*args, **kwargs)
        self._registered = False

    def on_startup(self, ext_id):
        carb.log_info("[lightspeed.property_template] Lightspeed Property Template startup")
        property_window = omni.kit.window.property.get_window()
        if property_window:
            property_window.register_widget("prim", "lss_mesh_asset", MeshAssetWidget("Shared Mesh"))
            property_window.register_widget("prim", "lss_material_asset", MaterialAssetWidget("Shared Material"))
            property_window.register_scheme_delegate("prim", "lss", AssetDelegate())
            property_window.set_scheme_delegate_layout("prim", ["path_prim", "lss"])
            self._registered = True

    def on_shutdown(self):
        carb.log_info("[lightspeed.property_template] Lightspeed Property Template shutdown")
        property_window = omni.kit.window.property.get_window()
        if self._registered and property_window:
            property_window.unregister_scheme_delegate("prim", "lss")
            property_window.unregister_widget("prim", "lss_material_asset")
            property_window.unregister_widget("prim", "lss_mesh_asset")
            self._registered = False
