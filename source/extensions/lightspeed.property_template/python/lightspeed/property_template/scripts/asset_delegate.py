"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
from lightspeed.common import constants
from omni.kit.window.property.property_scheme_delegate import PropertySchemeDelegate
from pxr import UsdShade


# noinspection PyMethodMayBeStatic
class AssetDelegate(PropertySchemeDelegate):
    def get_widgets(self, payload):
        widgets_to_build = []
        if self._should_enable_delegate(payload):
            widgets_to_build.append("lss_info_asset")
            widgets_to_build.append("lss_mesh_assets")
            widgets_to_build.append("lss_material_asset")
            widgets_to_build.append("attribute")
        return widgets_to_build

    def get_unwanted_widgets(self, payload):
        unwanted_widgets_to_build = []
        if self._should_enable_delegate(payload):
            unwanted_widgets_to_build = [
                "audio_listener",
                "audio_settings",
                "audio_sound",
                "backdrop",
                "camera",
                "compute_node",
                "geometry",
                "geometry_imageable",
                "kind",
                "light",
                "material",
                "material_binding",
                "media",
                "metadata",
                "nodegraph",
                "path",
                "payloads",
                "physx_custom_properties",
                "physx_invisible",
                "physx_main_frame_widget",
                "physx_rigid_body_cameras",
                "physx_update_all_drone_camera",
                "physx_update_all_follow_camera",
                "physx_update_all_velocity_camera",
                "physx_xform_cameras",
                "references",
                "renderproduct_base",
                "rendersettings_base",
                "rendervar_base",
                "shader",
                "skel",
                "tagging",
                "transform",
                "variants",
            ]
        return unwanted_widgets_to_build  # noqa R504

    def _should_enable_delegate(self, payload):
        stage = payload.get_stage()
        if stage:
            for prim_path in payload:
                prim = stage.GetPrimAtPath(prim_path)
                if prim and not self._should_enable_for_prim(prim):
                    return False
            return True
        return False

    def _should_enable_for_prim(self, prim):
        str_path = str(prim.GetPath())
        return (str_path.startswith(constants.INSTANCE_PATH) or str_path.startswith(constants.MESH_PATH)) and not (
            prim.IsA(UsdShade.Material) or prim.IsA(UsdShade.Shader)
        )
