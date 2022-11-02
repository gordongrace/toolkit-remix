"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import functools
import multiprocessing
import os
import re
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import carb
import omni.client
import omni.usd
from lightspeed.common import ReferenceEdit, constants
from lightspeed.layer_manager.core import LayerManagerCore, LayerType
from lightspeed.tool.octahedral_converter import LightspeedOctahedralConverter
from omni.kit.window.popup_dialog import MessageDialog
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils

from .asset_hasher import LightspeedAssetHasher


class LightspeedPostProcessExporter:
    def __init__(self, context_name: str = ""):
        self._context_name = context_name
        self._nvtt_path = Path(constants.NVTT_PATH)
        self.__layer_manager = LayerManagerCore(self._context_name)
        self._asset_hasher = None

    def _remove_extra_attr(self, prim: Usd.Prim):
        white_list = {
            "normals",
            "points",
            "doubleSided",
            "orientation",
            "invertedUvs",
            "material:binding",
            # below values are kept for kit compatibility, but not needed by dxvk_rt
            "faceVertexCounts",
            "faceVertexIndices",
            "primvars:st",
            "primvars:st:indices",
            "subdivisionScheme",  # needed for smooth normals when using vertex interpolation
        }

        attr_to_remove = []
        for attr in prim.GetAttributes():
            if attr.GetName() not in white_list and "xformOp" not in attr.GetName():
                attr_to_remove.append(attr.GetName())

        for attr in attr_to_remove:
            prim.RemoveProperty(attr)

    def _process_uvs(self, prim: Usd.Prim):
        # get the primvars API of the prim
        gp_pv = UsdGeom.PrimvarsAPI(prim)
        # get the primvars attribute of the UVs
        st_prim_var = gp_pv.GetPrimvar("st")

        if st_prim_var:
            # [AJAUS] Because USD and Directx8/9 assume different texture coordinate origins,
            # invert the vertical texture coordinate
            flattened_uvs = st_prim_var.ComputeFlattened()
            inverted_uvs = []
            for uv_value in flattened_uvs:
                inverted_uvs.append(Gf.Vec2f(uv_value[0], -uv_value[1]))

            prim.CreateAttribute("invertedUvs", Sdf.ValueTypeNames.Float2Array, False).Set(inverted_uvs)

    def _triangulate_mesh(self, prim: Usd.Prim):
        # indices and faces converted to triangles
        mesh = UsdGeom.Mesh(prim)
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        faces = mesh.GetFaceVertexCountsAttr().Get()

        triangles = []
        if not indices or not faces:
            return triangles

        indices_offset = 0
        new_face_counts = []

        subsets = []

        # need to update geom subset face lists
        display_predicate = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        children_iterator = iter(Usd.PrimRange(mesh.GetPrim(), display_predicate))
        for child_prim in children_iterator:
            if child_prim.IsA(UsdGeom.Subset):
                subset = UsdGeom.Subset.Get(omni.usd.get_context(self._context_name).get_stage(), child_prim.GetPath())
                subsets.append(
                    {
                        "subset": subset,
                        "old_faces": set(subset.GetIndicesAttr().Get()),  # set of old face indices in this subset
                        "new_faces": [],  # the new face index list
                    }
                )

        for old_face_index, face_count in enumerate(faces):
            start_index = indices[indices_offset]
            for face_index in range(face_count - 2):
                for subset in subsets:
                    if old_face_index in subset["old_faces"]:
                        subset["new_faces"].append(len(new_face_counts))
                new_face_counts.append(3)
                index1 = indices_offset + face_index + 1
                index2 = indices_offset + face_index + 2
                triangles.append(start_index)
                triangles.append(indices[index1])
                triangles.append(indices[index2])
            indices_offset += face_count

        for subset in subsets:
            subset["subset"].GetIndicesAttr().Set(subset["new_faces"])

        mesh.GetFaceVertexIndicesAttr().Set(triangles)
        mesh.GetFaceVertexCountsAttr().Set(new_face_counts)
        return triangles

    def _align_vertex_data(self, prim: Usd.Prim):
        # get the mesh schema API from the Prim
        mesh_schema = UsdGeom.Mesh(prim)

        face_vertex_indices = mesh_schema.GetFaceVertexIndicesAttr().Get()
        points = mesh_schema.GetPointsAttr().Get()

        primvar_api = UsdGeom.PrimvarsAPI(prim)
        geom_tokens = [UsdGeom.Tokens.faceVarying, UsdGeom.Tokens.varying, UsdGeom.Tokens.vertex]
        primvars = [
            {
                "primvar": primvar,
                "values": primvar.ComputeFlattened(),
                "fixed_values": [],
                "interpolation": primvar.GetInterpolation(),
            }
            for primvar in primvar_api.GetPrimvars()
            if primvar.GetInterpolation() in geom_tokens
        ]

        fixed_indices = range(0, len(face_vertex_indices))
        fixed_points = []
        fixed_points = [points[face_vertex_indices[i]] for i in fixed_indices]

        for primvar in primvars:
            if primvar["interpolation"] == UsdGeom.Tokens.vertex:
                primvar["fixed_values"] = [primvar["values"][face_vertex_indices[i]] for i in fixed_indices]

        fixed_normals = []
        normals_interp = mesh_schema.GetNormalsInterpolation()
        normals = mesh_schema.GetNormalsAttr().Get()
        if normals_interp == UsdGeom.Tokens.vertex and normals:
            # Normals are currently in the (old) vertex order.  need to expand them to be 1 normal per vertex per face
            fixed_normals = [normals[face_vertex_indices[i]] for i in fixed_indices]
            mesh_schema.GetNormalsAttr().Set(fixed_normals)
        else:
            # Normals are already in 1 normal per vertex per face, need to set it to vertex so that triangulation
            # doesn't break it.
            mesh_schema.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

        mesh_schema.GetFaceVertexIndicesAttr().Set(fixed_indices)
        mesh_schema.GetPointsAttr().Set(fixed_points)
        for primvar in primvars:
            if primvar["interpolation"] == UsdGeom.Tokens.vertex:
                primvar["values"] = primvar["fixed_values"]
            primvar["primvar"].Set(primvar["values"])
            primvar["primvar"].BlockIndices()
            primvar["primvar"].SetInterpolation(UsdGeom.Tokens.vertex)

    def _process_subsets(self, prim: Usd.Prim):
        mesh_schema = UsdGeom.Mesh(prim)
        face_vertex_indices = mesh_schema.GetFaceVertexIndicesAttr().Get()
        display_predicate = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
        children_iterator = iter(Usd.PrimRange(prim, display_predicate))
        for child_prim in children_iterator:
            if child_prim.IsA(UsdGeom.Subset):
                subset = UsdGeom.Subset.Get(omni.usd.get_context(self._context_name).get_stage(), child_prim.GetPath())
                face_indices = subset.GetIndicesAttr().Get()
                vert_indices = []
                for face_index in face_indices:
                    vert_indices.append(face_vertex_indices[face_index * 3 + 0])
                    vert_indices.append(face_vertex_indices[face_index * 3 + 1])
                    vert_indices.append(face_vertex_indices[face_index * 3 + 2])
                child_prim.CreateAttribute("triangleIndices", Sdf.ValueTypeNames.IntArray).Set(vert_indices)

    def _process_mesh_prim(self, prim: Usd.Prim):
        # processing steps:
        # * Strip unused attributes
        # * Align all per vertex data
        #   * computeFlattened for all primvars
        #   * split all faces to have their own vertices
        #     * faceVertexIndices should become 0,1,...,n
        #     * all primvars should get index arrays matchign faceVertexIndices
        # * triangulate any faces with > 3 vertices
        #   * triangles that came from the same face will share verts
        #   * geom subsets will be updated to point to the correct faces
        # * create inverted UVs
        # * add triangleIndices for geom subsets

        # strip out  attributes that the runtime doesn't support
        self._remove_extra_attr(prim)

        # Runtime only supports a single array of verts, with each vertex having position, normal, uv, etc.
        # Thus, we need to make all of the per-vertex data arrays the same length and ordering. As FaceVarying
        # primvars can have the most information (3 points of data per triangle), all data arrays have to be
        # expanded to match that.
        self._align_vertex_data(prim)

        # split any non-triangle faces into triangles (updates indices of all indexed data)
        # As this introduces new faces, this must also update any geom subsets.
        self._triangulate_mesh(prim)

        # Make a new attribute for dxvk_rt compatible uvs:
        # 3 uvs per triangle, in the same order as the positions, with the uv.y coordinate inverted.
        self._process_uvs(prim)

        # subsets store face indices, but dxvk_rt needs triangle indices.
        self._process_subsets(prim)

    def _process_shader_prim_convert_tangent_space(
        self, prim, progress_fn, executor=None, process_texture=True, set_usd=True, futures=None
    ):
        # convert tangent space normal maps to octahedral
        if executor is None:
            progress_fn()
        if futures is None:
            futures = {}
        normal_map_encoding_attr = prim.GetAttribute(constants.MATERIAL_INPUTS_NORMALMAP_ENCODING)
        normal_map_attr = prim.GetAttribute(constants.MATERIAL_INPUTS_NORMALMAP_TEXTURE)
        layer = prim.GetStage().GetEditTarget().GetLayer()
        if (  # noqa PLR1702
            normal_map_attr
            and normal_map_encoding_attr
            and normal_map_encoding_attr.HasValue()
            and normal_map_attr.HasValue
        ):
            encoding = normal_map_encoding_attr.Get()
            if encoding != constants.NormalMapEncodings.OCTAHEDRAL.value:
                # need to re-encode normal map
                normal_path = normal_map_attr.Get()
                if normal_path:
                    abs_path = Path(normal_path.resolvedPath)
                    rel_path = omni.client.make_relative_url(layer.identifier, str(abs_path))
                    new_abs_path = abs_path.with_name(abs_path.stem + "_OTH" + abs_path.suffix)
                    new_rel_path = rel_path.rpartition(".")[0] + "_OTH." + rel_path.rpartition(".")[-1]
                    new_abs_dds_path = new_abs_path.with_suffix(".dds")
                    if process_texture:
                        # only convert if the final converted dds doesn't exist, or the source's hash differs from the
                        # stored hash.
                        needs_convert = (not new_abs_dds_path.exists()) or self._asset_hasher.should_process_asset(
                            abs_path
                        )
                        already_queued = futures.get(abs_path, None) is not None
                        if needs_convert and not already_queued:
                            carb.log_info("converting normal map to octahedral: " + str(rel_path))
                            self._asset_hasher.update_asset_hash(abs_path)
                            if encoding == constants.NormalMapEncodings.TANGENT_SPACE_DX.value:
                                if executor is not None:

                                    def do(old_path, new_path):  # noqa PLC0130
                                        progress_fn()
                                        LightspeedOctahedralConverter.convert_dx_file_to_octahedral(old_path, new_path)

                                    futures[abs_path] = executor.submit(
                                        functools.partial(do, str(abs_path), str(new_abs_path))
                                    )
                                else:
                                    LightspeedOctahedralConverter.convert_dx_file_to_octahedral(
                                        str(abs_path), str(new_abs_path)
                                    )
                            elif encoding == constants.NormalMapEncodings.TANGENT_SPACE_OGL.value:
                                if executor is not None:

                                    def do(old_path, new_path):  # noqa PLC0130
                                        progress_fn()
                                        LightspeedOctahedralConverter.convert_ogl_file_to_octahedral(old_path, new_path)

                                    futures.append(
                                        executor.submit(functools.partial(do, str(abs_path), str(new_abs_path)))
                                    )
                                else:
                                    LightspeedOctahedralConverter.convert_ogl_file_to_octahedral(
                                        str(abs_path), str(new_abs_path)
                                    )

                    if set_usd:
                        normal_map_attr.Set(str(new_rel_path))
                        normal_map_encoding_attr.Set(constants.NormalMapEncodings.OCTAHEDRAL.value)

    def _sanitize_mdl_paths(self, prim, progress_fn):
        """
        Sanitize mdl paths to a good path. We want something like "Aperture.mdl", not "./Aperture.mdl" or
        "../../Aperture.mdl" or "c:/hello/Aperture.mdl"
        We do that as post process because if the current stage is read only, we can't sanitize anything
        """
        progress_fn()
        attr = prim.GetAttribute("info:mdl:sourceAsset")
        value = str(attr.Get())
        if value.startswith("@"):
            value = value[1:]
        if value.endswith("@"):
            value = value[:-1]
        # remove the number and folder path
        new_value = os.path.basename(re.sub(r"_\d+.mdl", ".mdl", value))
        attr.Set(new_value)

    def _process_shader_prim_compress_dds(
        self,
        prim,
        progress_fn,
        process_texture=True,
        set_usd=True,
        result=None,
        result_shader_prim_compress_dds_outputs=None,
    ):
        # compress png textures to dds
        if result is None:
            result = []
        if result_shader_prim_compress_dds_outputs is None:
            result_shader_prim_compress_dds_outputs = []
        progress_fn()
        layer = prim.GetStage().GetEditTarget().GetLayer()
        for attr_name, texture_format_info in constants.TEXTURE_INFO.items():
            attr = prim.GetAttribute(attr_name)
            if attr and attr.Get():
                abs_path_str = attr.Get().resolvedPath

                abs_path = Path(abs_path_str)
                rel_path = omni.client.make_relative_url(layer.identifier, abs_path_str)
                rel_dds_path = rel_path.rpartition(".")[0] + ".dds"

                if set_usd:
                    attr.Set(str(rel_dds_path))

                if not process_texture:
                    continue

                dds_path = None
                if not abs_path_str:
                    # it means that the png is not here anymore, that why USD can't resolve the path
                    # we will try to find if the dds fom the deleted png exist
                    stacks = attr.GetPropertyStack(Usd.TimeCode.Default())
                    for stack in stacks:
                        virtual_abs_path = stack.layer.ComputeAbsolutePath(rel_path)
                        dds_path = Path(f"{virtual_abs_path.rpartition('.')[0]}.dds")
                        if dds_path.exists():
                            break
                        dds_path = None
                else:
                    dds_path = abs_path.with_suffix(".dds")

                # Only add a conversion task if:
                #   The dds_path is set
                #   There isn't already a task for this dds_path
                #   Either:
                #     A dds doesn't exist at that path
                #     The hash of the source asset that created the dds doesn't match the hash of the existing .png
                if (
                    dds_path
                    and str(dds_path) not in result_shader_prim_compress_dds_outputs
                    and (not dds_path.exists() or self._asset_hasher.should_process_asset(abs_path))
                ):  # noqa SIM102
                    self._asset_hasher.update_asset_hash(abs_path)
                    carb.log_info("Converting PNG to DDS: " + str(rel_path))

                    texture_flags = texture_format_info.to_nvtt_flag_array()

                    line = [str(abs_path), "--output", str(dds_path)] + texture_flags
                    result.append(line)
                    result_shader_prim_compress_dds_outputs.append(str(dds_path))

                # NOTE: not safe to delete the original png until after the dds files are actually created and all prims
                # have been updated to point at those dds files.

    async def _on_processor_error(self, context, export_replacement_layer, message):
        carb.log_error(constants.BAD_EXPORT_LOG_PREFIX + message)

        if export_replacement_layer is not None:
            custom_layer_data = export_replacement_layer.get_sdf_layer().customLayerData
            custom_layer_data[constants.EXPORT_STATUS_NAME] = constants.EXPORT_STATUS_POSTPROCESS_ERRORS
            export_replacement_layer.get_sdf_layer().customLayerData = custom_layer_data

            await context.save_stage_async()

        def on_okay_clicked(dialog: MessageDialog):
            dialog.hide()

        dialog = MessageDialog(
            width=600,
            message=message,
            ok_handler=on_okay_clicked,
            ok_label="Okay",
            disable_cancel_button=True,
        )
        dialog.show()

    def _file_in_folder(self, file_path, folder_path):
        abs_file_path = os.path.abspath(file_path)
        abs_folder_path = os.path.abspath(folder_path)
        return abs_file_path.startswith(abs_folder_path)

    @omni.usd.handle_exception  # noqa C901
    async def process(self, export_file_path, progress_text_callback, progress_callback):
        carb.log_info("Processing: " + export_file_path)

        context = omni.usd.get_context(self._context_name)

        # TODO: Crash, use async function instead, waiting OM-42168
        # success = context.open_stage(export_file_path)
        result, _ = await context.open_stage_async(export_file_path)
        if not result:
            await self._on_processor_error(
                context,
                None,
                f"Post Process could not open the collected stage.\nStage was expected at {export_file_path}",
            )
            return

        export_stage = context.get_stage()

        # TODO: Remove this section once the collector properly handles sublayer paths [OM-60283]
        export_replacement_sdf_layer = self.__layer_manager.get_layer(LayerType.replacement)
        sublayers = []
        for path in export_replacement_sdf_layer.subLayerPaths:
            sublayers.append("./SubUSDs/" + os.path.basename(str(path)))
        export_replacement_sdf_layer.subLayerPaths = sublayers

        # flatten all layers
        export_replacement_layer = self.__layer_manager.get_layer_instance(LayerType.replacement)
        if export_replacement_layer is None:
            await self._on_processor_error(context, None, "Can't find the replacement layer.")
            return
        export_replacement_layer.flatten_sublayers()

        # Verify export_stage only contains references that are inside of the gameReadyAssets folder
        game_ready_assets_folder = Path(export_file_path).parent
        (all_layers, all_assets, unresolved_paths) = UsdUtils.ComputeAllDependencies(export_file_path)
        for layer in all_layers:
            if not self._file_in_folder(layer.identifier, game_ready_assets_folder):
                await self._on_processor_error(
                    context,
                    export_replacement_layer,
                    "Post Process found layer reference outside of GameReadyAssets folder.\n"
                    + f"expected {layer.identifier} to be inside of {game_ready_assets_folder}.",
                )
                return
        for asset in all_assets:
            if not asset.endswith(".mdl") and not self._file_in_folder(asset, game_ready_assets_folder):
                await self._on_processor_error(
                    context,
                    export_replacement_layer,
                    "Post Process found asset reference outside of GameReadyAssets folder.\n"
                    + f"expected {asset} to be inside of {game_ready_assets_folder}.",
                )
                return
        if unresolved_paths:
            carb.log_warn("Post Processing found unresolved references before running:" + str(unresolved_paths))

        self._asset_hasher = LightspeedAssetHasher(game_ready_assets_folder / "manifest.pkl")

        # process meshes
        # TraverseAll because we want to grab overrides
        all_geos = [prim_ref for prim_ref in export_stage.TraverseAll() if UsdGeom.Mesh(prim_ref)]
        failed_processes = []
        processed_mesh_prim_layer_paths = []
        processed_mesh_prim_layer_paths_same_usd = []
        # TODO a crash in one geo shouldn't prevent processing the rest of the geometry

        length = len(all_geos)
        for i, geo_prim in enumerate(all_geos):
            # we only work on meshes that have USD reference path(s) and process the USD reference 1 time
            ref_node = geo_prim.GetPrimIndex().rootNode.children[0]
            # if a prim's nested under several references, chase it all the way to the bottom.
            while ref_node.children:
                ref_node = ref_node.children[0]
            ref_asset_path = ref_node.layerStack.layers[0]
            ref_asset_path_value = ref_asset_path.realPath
            ref_asset_and_prim_path = f"{ref_asset_path_value}, {ref_node.path}"

            # if the reference is inside another reference and it was already processed,
            # we don't need to reprocess it.
            stack = geo_prim.GetPrimStack()
            ref_asset_and_prim_path_same_usd = None
            if stack:
                # this will give the usd reference path of the prim, even if the prim is a ref in a ref in a ref...
                ref_asset_path_value_same_usd = stack[-1].layer.realPath
                prim_path_same_usd = stack[-1].path
                ref_asset_and_prim_path_same_usd = f"{ref_asset_path_value_same_usd}, {prim_path_same_usd}"
                if ref_asset_and_prim_path_same_usd in processed_mesh_prim_layer_paths_same_usd:
                    continue

            if not ref_asset_path_value or ref_asset_and_prim_path in processed_mesh_prim_layer_paths:
                continue
            carb.log_info(f"Post Processing Mesh: {geo_prim.GetPath()}")
            progress_text_callback(f"Post Processing Mesh:\n{geo_prim.GetPath()}")
            progress_callback(float(i) / length)
            await omni.kit.app.get_app().next_update_async()
            try:
                # apply edits to the geo prim in it's source usd, not in the top level replacements.usd
                with ReferenceEdit(geo_prim):
                    self._process_mesh_prim(geo_prim)
                    processed_mesh_prim_layer_paths.append(ref_asset_and_prim_path)
                    if ref_asset_and_prim_path_same_usd:
                        processed_mesh_prim_layer_paths_same_usd.append(ref_asset_and_prim_path_same_usd)
            except Exception as e:  # noqa
                failed_processes.append(str(geo_prim.GetPath()))
                carb.log_error("Exception when post-processing mesh: " + str(geo_prim.GetPath()))
                carb.log_error(f"{e}")
                carb.log_error(f"{traceback.format_exc()}")

        # process materials
        # TraverseAll because we want to grab overrides
        all_shaders = [prim_ref for prim_ref in export_stage.TraverseAll() if prim_ref.IsA(UsdShade.Shader)]
        # TODO a crash in one shader shouldn't prevent processing the rest of the materials
        max_cpu = multiprocessing.cpu_count() - 8
        if max_cpu <= 0:
            max_cpu = 1
        length = len(all_shaders)

        def _update_progress(i_progress, length_progress, prim_path, progress_prefix):
            carb.log_info(f"{progress_prefix} {prim_path}")
            progress_text_callback(f"{progress_prefix}\n{prim_path}")
            if length_progress == 0:
                progress_callback(1.0)
            else:
                progress_callback(float(i_progress) / length_progress)

        def _process_shader(process_shader_fn: Callable[[Usd.Prim], None], progress_prefix):
            # the first step is to do all process in multicore without to touch USD
            # the second step is to apply the result into USD
            for i, shader_prim in enumerate(all_shaders):
                try:
                    if export_replacement_layer.get_sdf_layer().GetPrimAtPath(shader_prim.GetPath()):
                        # top level replacements already has opinions about this shader, so apply edits in replacements.
                        process_shader_fn(
                            shader_prim,
                            functools.partial(_update_progress, i, length, shader_prim.GetPath(), progress_prefix),
                        )
                    else:
                        # Shader is just referenced from another USD, so apply edits to the source usd
                        with ReferenceEdit(shader_prim):
                            process_shader_fn(
                                shader_prim,
                                functools.partial(_update_progress, i, length, shader_prim.GetPath(), progress_prefix),
                            )
                except Exception as e:  # noqa
                    failed_processes.append(str(shader_prim.GetPath()))
                    carb.log_error("Exception when post-processing shader: " + str(shader_prim.GetPath()))
                    carb.log_error(f"{e}")
                    carb.log_error(f"{traceback.format_exc()}")

        # sanitize the mdl paths
        _process_shader(
            self._sanitize_mdl_paths,
            "Sanitize MDL paths:",
        )
        await omni.kit.app.get_app().next_update_async()

        # process convert tangent without to set USD attribute. Do it in thread (we don't need multiprocess because
        # most of the time is spent during Pillow image saving. And Processing freeze)
        executor = ThreadPoolExecutor(max_workers=max_cpu)
        futures = {}
        _process_shader(
            functools.partial(
                self._process_shader_prim_convert_tangent_space,
                executor=executor,
                process_texture=True,
                set_usd=False,
                futures=futures,
            ),
            "Post Processing Shader Tangent Process:",
        )
        for _ in as_completed(futures.values()):
            # for the progress bar
            await omni.kit.app.get_app().next_update_async()
        # wait the process to be finished
        executor.shutdown(wait=True)
        await omni.kit.app.get_app().next_update_async()

        # set USD attributes for convert tangent
        _process_shader(
            functools.partial(
                self._process_shader_prim_convert_tangent_space,
                process_texture=False,
                set_usd=True,
            ),
            "Post Processing Shader Tangent set USD:",
        )
        await omni.kit.app.get_app().next_update_async()

        # read the texture to be converted to dds
        result_shader_prim_compress_dds = []
        result_shader_prim_compress_dds_outputs = []
        _process_shader(
            functools.partial(
                self._process_shader_prim_compress_dds,
                process_texture=True,
                set_usd=False,
                result=result_shader_prim_compress_dds,
                result_shader_prim_compress_dds_outputs=result_shader_prim_compress_dds_outputs,
            ),
            "Post Processing Shader compress DDS read:",
        )
        _update_progress(
            0, len(result_shader_prim_compress_dds), "Please wait", "Post Processing Shader compress DDS in progress..."
        )
        await omni.kit.app.get_app().next_update_async()
        # Using a lot of nvtt with cuda will crash the whole computer. Running just 2...
        futures = []
        executor = ThreadPoolExecutor(max_workers=4)
        for cmd in [[str(self._nvtt_path)] + cmds for cmds in result_shader_prim_compress_dds]:
            futures.append(executor.submit(subprocess.check_call, cmd))

        for i_dds, _ in enumerate(as_completed(futures)):
            # for the progress bar
            _update_progress(
                i_dds,
                len(result_shader_prim_compress_dds),
                "Please wait",
                "Post Processing Shader compress DDS in progress...",
            )
            await omni.kit.app.get_app().next_update_async()
        # wait the process to be finished
        executor.shutdown(wait=True)

        await omni.kit.app.get_app().next_update_async()
        # set the new converted dds textures
        _process_shader(
            functools.partial(
                self._process_shader_prim_compress_dds,
                process_texture=False,
                set_usd=True,
            ),
            "Post Processing Shader compress DDS set USD:",
        )

        self._asset_hasher.save_manifest()
        self._asset_hasher = None

        if failed_processes:
            message = (
                "Prims failed to export properly.  The contents of gameReadyAssets are probably invalid."
                "\nError details have been printed to the console."
                "\n\nFailing prims: \n  " + ",\n  ".join(failed_processes)
            )
            await self._on_processor_error(context, export_replacement_layer, message)
        else:
            custom_layer_data = export_replacement_layer.get_sdf_layer().customLayerData
            if custom_layer_data[constants.EXPORT_STATUS_NAME] == constants.EXPORT_STATUS_INCOMPLETE_EXPORT:
                custom_layer_data[constants.EXPORT_STATUS_NAME] = constants.EXPORT_STATUS_RELEASE_READY
                export_replacement_layer.get_sdf_layer().customLayerData = custom_layer_data

            await context.save_stage_async()
