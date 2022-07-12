"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import asyncio

import omni.usd
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs


class Setup:
    def __init__(self, context: omni.usd.UsdContext):
        self._default_attr = {"_context": None}
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)
        self._context = context

    def create_new_work_file(self):
        self._context.new_stage_with_callback(self._on_new_stage_created)

    def _on_new_stage_created(self, result: bool, error: str):
        asyncio.ensure_future(self._deferred_startup(self._context))

    @omni.usd.handle_exception
    async def _deferred_startup(self, context):
        """Or crash"""
        await omni.kit.app.get_app_interface().next_update_async()
        # TODO, TMP
        from pxr import Gf, UsdGeom  # noqa PLC0415

        await context.new_stage_async()
        await omni.kit.app.get_app_interface().next_update_async()
        stage = context.get_stage()
        while (context.get_stage_state() in [omni.usd.StageState.OPENING, omni.usd.StageState.CLOSING]) or not stage:
            await asyncio.sleep(0.1)

        # set the camera
        camera = stage.GetPrimAtPath("/OmniverseKit_Persp")
        camera_prim = UsdGeom.Camera(camera)
        camera_prim.ClearXformOpOrder()
        # omni.kit.commands.execute("TransformPrimCommand", path="/OmniverseKit_Persp", usd_context_name=context)

        hello = UsdGeom.Xform.Define(stage, "/hello")
        translate = hello.AddXformOp(UsdGeom.XformOp.TypeTranslate, UsdGeom.XformOp.PrecisionDouble, "")
        translate.Set(Gf.Vec3f(0, 0, 0))
        rotate = hello.AddXformOp(UsdGeom.XformOp.TypeRotateXYZ, UsdGeom.XformOp.PrecisionDouble, "")
        rotate.Set(Gf.Vec3f(0, 0, 0))
        scale = hello.AddXformOp(UsdGeom.XformOp.TypeScale, UsdGeom.XformOp.PrecisionDouble, "")
        scale.Set(Gf.Vec3f(1, 1, 1))
        stage.SetDefaultPrim(hello.GetPrim())
        cube = UsdGeom.Cube.Define(stage, "/hello/world")
        cube.GetSizeAttr().Set(50)

        hello = UsdGeom.Xform.Define(stage, "/hello1")
        translate = hello.AddXformOp(UsdGeom.XformOp.TypeTranslate, UsdGeom.XformOp.PrecisionDouble, "")
        translate.Set(Gf.Vec3f(70, 0, 0))
        rotate = hello.AddXformOp(UsdGeom.XformOp.TypeRotateXYZ, UsdGeom.XformOp.PrecisionDouble, "")
        rotate.Set(Gf.Vec3f(0, 0, 0))
        scale = hello.AddXformOp(UsdGeom.XformOp.TypeScale, UsdGeom.XformOp.PrecisionDouble, "")
        scale.Set(Gf.Vec3f(1, 1, 1))
        sphere = UsdGeom.Cube.Define(stage, "/hello1/world1")
        sphere.GetSizeAttr().Set(40)
        print("hellloooo")

    def destroy(self):
        _reset_default_attrs(self)