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
import omni.usd
from lightspeed.layer_manager.scripts.core import LayerManagerCore, LayerType
from pxr import Gf, Sdf, UsdGeom


class LightspeedPosProcessExporter:
    def __init__(self):
        self.__layer_manager = LayerManagerCore()

    def _remove_extra_attr(self, prim):
        used_attrs = {
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
        }

        attr_to_remove = []
        for attr in prim.GetAttributes():
            if attr.GetName() not in used_attrs:
                attr_to_remove.append(attr.GetName())

        for attr in attr_to_remove:
            carb.log_warn(
                "Warning: Lightspeed Export doesn't support attribute: '"
                + attr
                + "' found on "
                + prim.GetPath().pathString
            )
            prim.RemoveProperty(attr)

    def _process_uvs(self, prim):
        # get the primvars API of the prim
        gp_pv = UsdGeom.PrimvarsAPI(prim)
        # get the primvars attribute of the UVs
        st_prim_var = gp_pv.GetPrimvar("st")

        # [AJAUS] Because USD and Directx8/9 assume different texture coordinate origins,
        # invert the vertical texture coordinate
        flattened_uvs = st_prim_var.ComputeFlattened()
        inverted_uvs = []
        for uv in flattened_uvs:
            inverted_uvs.append(Gf.Vec2f(uv[0], -uv[1]))

        prim.CreateAttribute("invertedUvs", Sdf.ValueTypeNames.Float2Array, False).Set(inverted_uvs)

    def _process_geometry(self, mesh):
        face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()
        points = mesh.GetPointsAttr().Get()
        fixed_indices = range(0, len(face_vertex_indices))
        fixed_points = []
        for i in fixed_indices:
            fixed_points.append(points[face_vertex_indices[i]])

        mesh.GetFaceVertexIndicesAttr().Set(fixed_indices)
        mesh.GetPointsAttr().Set(fixed_points)

    def _process_subsets(self, mesh):
        subsets = UsdGeom.Subset.GetGeomSubsets(mesh)
        for subset in subsets:
            face_indices = UsdGeom.Subset(subset).GetIndicesAttr().Get()
            vert_indices = []
            for face_index in face_indices:
                vert_indices.append(face_index * 3 + 0)
                vert_indices.append(face_index * 3 + 1)
                vert_indices.append(face_index * 3 + 2)
            subset.GetPrim().CreateAttribute("triangleIndices", Sdf.ValueTypeNames.IntArray).Set(vert_indices)

    def _process_mesh_prim(self, prim):
        # strip out  attributes that the runtime doesn't support
        self._remove_extra_attr(prim)

        # TODO: Triangulate non-3 faceCounts
        # TODO: bake transformations to verts & normals so that all prims have identity transform

        # Make a new attribute for dxvk_rt compatible uvs:
        # 3 uvs per triangle, in the same order as the positions, with the uv.y coordinate inverted.
        self._process_uvs(prim)

        # get the mesh from the Prim
        mesh = UsdGeom.Mesh(prim)

        # Expand point and index data to match faceVarying primvars
        self._process_geometry(mesh)

        # subsets store face indices, but dxvk_rt needs triangle indices.
        self._process_subsets(mesh)

    def process(self, file_path):
        carb.log_info("Processing: " + file_path)

        # TODO: waiting OM-42168
        success = omni.usd.get_context().open_stage(file_path)
        if not success:
            return

        stage = omni.usd.get_context().get_stage()

        # flatten all layers
        layer_instance = self.__layer_manager.get_layer_instance(LayerType.replacement)
        if layer_instance is None:
            carb.log_error("Can't find the replacement layer")
            return
        layer_instance.flatten_sublayers()

        # process meshes
        # TraverseAll because we want to grab overrides
        all_geos = [prim_ref for prim_ref in stage.TraverseAll() if UsdGeom.Mesh(prim_ref)]
        for geo_prim in all_geos:
            self._process_mesh_prim(geo_prim)

        omni.usd.get_context().save_stage()