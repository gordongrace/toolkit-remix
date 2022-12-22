"""
* Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
import re
import typing
from pathlib import Path
from typing import List, Optional, Union

import carb
import omni.client
import omni.kit.undo
import omni.usd
from lightspeed.common import constants
from omni.flux.utils.common import path_utils as _path_utils
from omni.flux.utils.common import reset_default_attrs as _reset_default_attrs
from pxr import Sdf, Usd, UsdGeom

if typing.TYPE_CHECKING:
    from lightspeed.trex.selection_tree.shared.widget.selection_tree.model import ItemInstanceMesh as _ItemInstanceMesh
    from lightspeed.trex.selection_tree.shared.widget.selection_tree.model import (
        ItemReferenceFileMesh as _ItemReferenceFileMesh,
    )

_DEFAULT_PRIM_TAG = "<Default Prim>"


class Setup:
    def __init__(self, context_name: str):
        self._default_attr = {}
        for attr, value in self._default_attr.items():
            setattr(self, attr, value)
        self._context_name = context_name
        self._context = omni.usd.get_context(context_name)

    def get_children_from_prim(
        self,
        prim,
        from_reference_layer_path: str = None,
        level: Optional[int] = None,
        skip_remix_ref: bool = False,
        only_prim_not_from_ref: bool = False,
    ):  # noqa PLR1710

        _level = 0

        def get_parent_ref_layers(_prim):
            refs_and_layers = omni.usd.get_composed_references_from_prim(_prim)
            result = []
            if refs_and_layers:
                for (ref, layer) in refs_and_layers:
                    if not ref.assetPath:
                        continue
                    result.append(omni.client.normalize_url(layer.ComputeAbsolutePath(ref.assetPath)))
            parent = _prim.GetParent()
            if parent and parent.IsValid():
                result.extend(get_parent_ref_layers(parent))
            return result

        def traverse_instanced_children(_prim, _level, _skip_remix_ref=False):  # noqa R503
            if level is not None and _level == level:
                return
            _level += 1
            for child in _prim.GetFilteredChildren(Usd.PrimAllPrimsPredicate):
                # it can happen that we added the same reference multiple time. But USD can't do that.
                # As a workaround, we had to create a xform child and add the reference to it.
                # Check the children and find the attribute that define that
                is_remix_ref = False
                if _skip_remix_ref:
                    is_remix_ref = child.GetAttribute(constants.IS_REMIX_REF_ATTR)
                    if is_remix_ref.IsValid():
                        _level -= 1

                layer_stack = [omni.client.normalize_url(stack.layer.realPath) for stack in child.GetPrimStack()]
                if only_prim_not_from_ref and set(layer_stack).intersection(set(get_parent_ref_layers(_prim))):
                    yield from traverse_instanced_children(child, _level, _skip_remix_ref=_skip_remix_ref)
                    continue

                if (
                    from_reference_layer_path is not None
                    and not only_prim_not_from_ref
                    and from_reference_layer_path not in layer_stack
                ):
                    yield from traverse_instanced_children(child, _level, _skip_remix_ref=_skip_remix_ref)
                    continue
                if not is_remix_ref:
                    yield child
                yield from traverse_instanced_children(child, _level, _skip_remix_ref=_skip_remix_ref)

        return list(traverse_instanced_children(prim, _level, _skip_remix_ref=skip_remix_ref))

    def select_child_from_instance_item_and_ref(
        self, stage, from_prim, from_reference_layer_path, instance_items: List["_ItemInstanceMesh"]
    ):
        """
        Select the first prim of a ref corresponding to the selected instance items
        """
        selection = []
        for item in instance_items:
            prim = stage.GetPrimAtPath(item.path)
            if not prim.IsValid():
                continue

            # it can happen that we added the same reference multiple time. But USD can't do that.
            # As a workaround, we had to create a xform child and add the reference to it.
            # Check the children and find the attribute that define that
            to_break = False
            for child in prim.GetChildren():
                is_remix_ref = child.GetAttribute(constants.IS_REMIX_REF_ATTR)
                if is_remix_ref.IsValid():
                    proto_children = self.get_corresponding_prototype_prims([child])
                    for proto_child in proto_children:
                        if proto_child == str(from_prim.GetPath()):
                            prim = child
                            to_break = True
                            break
                if to_break:
                    break

            children = self.get_children_from_prim(
                prim, from_reference_layer_path=self.switch_ref_rel_to_abs_path(stage, from_reference_layer_path)
            )
            # select the first children
            if children:
                selection.append(str(children[0].GetPath()))
        if selection:
            self.select_prim_paths(selection)

    def get_next_xform_children(self, prim, from_reference_layer_path: str = None) -> List[Usd.Prim]:
        children_prims = prim.GetChildren()
        if not children_prims:
            return []
        if from_reference_layer_path is not None:
            children_prims2 = []
            for child in children_prims:
                stacks = child.GetPrimStack()
                if from_reference_layer_path in [stack.layer.realPath for stack in stacks]:
                    children_prims2.append(child)
        else:
            children_prims2 = list(children_prims)
        if not children_prims2:
            return []
        xformable_prims = self.filter_xformable_prims(children_prims2)
        if xformable_prims:
            return xformable_prims
        # if not children, check if the sub children is a xform
        result = []
        for children_prim in children_prims2:
            result.extend(self.get_next_xform_children(children_prim))
        return result

    @staticmethod
    def prim_is_from_a_capture_reference(prim) -> bool:
        stacks = prim.GetPrimStack()
        if stacks:
            for stack in stacks:
                layer_path = Path(stack.layer.realPath)
                if constants.CAPTURE_FOLDER in layer_path.parts and constants.MESHES_FOLDER in layer_path.parts:
                    # this is a mesh from the capture folder
                    return True
        return False

    def filter_xformable_prims(self, prims: List[Usd.Prim]):
        return [prim for prim in prims if UsdGeom.Xformable(prim)]

    def filter_scope_prims(self, prims: List[Usd.Prim]):
        return [prim for prim in prims if UsdGeom.Scope(prim)]

    def filter_imageable_prims(self, prims: List[Usd.Prim]):
        return [prim for prim in prims if UsdGeom.Imageable(prim)]

    def get_corresponding_prototype_prims(self, prims) -> List[str]:
        """Give a list of instance prims (inst_/*), and get the corresponding prims inside the prototypes (mesh_/*)"""
        paths = []
        for prim in prims:
            if not prim.IsValid():
                continue

            stage = prim.GetStage()
            path = re.sub(constants.REGEX_INSTANCE_TO_MESH_SUB, rf"{constants.MESH_PATH}\2", str(prim.GetPath()))
            if not stage.GetPrimAtPath(path).IsValid():
                continue
            paths.append(path)
        return paths

    def get_corresponding_prototype_prims_from_path(self, paths) -> List[str]:
        """Give a list of instance prims (inst_/*), and get the corresponding prims inside the prototypes (mesh_/*)"""
        stage = self._context.get_stage()
        prims = [stage.GetPrimAtPath(path) for path in paths]
        return self.get_corresponding_prototype_prims(prims)

    def reset_asset(self, prim):
        pass

    def get_selected_prim_paths(self) -> List[Union[str]]:
        return self._context.get_selection().get_selected_prim_paths()

    def select_prim_paths(self, paths: List[Union[str]]):
        current_selection = self._context.get_selection().get_selected_prim_paths()
        if sorted(paths) != sorted(current_selection):
            self._context.get_selection().set_selected_prim_paths(paths, True)

    def get_prim_from_ref_items(
        self,
        ref_items: List["_ItemReferenceFileMesh"],
        parent_items: List[Union["_ItemInstanceMesh", "_ItemReferenceFileMesh"]],
        only_xformable: bool = False,
        only_imageable: bool = False,
        level: Optional[int] = None,
        skip_remix_ref: bool = False,
    ) -> List[Usd.Prim]:
        """
        Get xformables prim that comes from the reference item and are children of the parent items.
        """
        if not ref_items:
            return []
        selected_prims = [item.prim for item in parent_items]
        if not selected_prims:
            return []
        # TODO: select only the first selection for now, and select the material that match the selected usd ref
        # path
        selected_refs = [item.ref for item in ref_items]
        selected_layers = [item.layer for item in ref_items]
        reference_path = omni.client.normalize_url(selected_layers[0].ComputeAbsolutePath(selected_refs[0].assetPath))
        children_prims = self.get_children_from_prim(
            selected_prims[0], from_reference_layer_path=reference_path, level=level, skip_remix_ref=skip_remix_ref
        )
        if not children_prims:
            return []
        if only_xformable:
            # get the first xformable from the list
            children_prims = self.filter_xformable_prims(children_prims)
        if only_imageable:
            # get the first xformable from the list
            children_prims = self.filter_imageable_prims(children_prims)
        return children_prims

    def get_scope_prims_without_imageable_children(self, prims):
        result = []
        scoped_children = self.filter_scope_prims(prims)
        for scope in scoped_children:
            scope_children = self.get_children_from_prim(scope)
            imageable_children = self.filter_imageable_prims(scope_children)
            # if this is a scope prim, and this scope prim doesn't have any imageable prim, we keep it
            if not imageable_children:
                result.append(scope)
        return result

    @staticmethod
    def switch_ref_abs_to_rel_path(stage, path):
        edit_layer = stage.GetEditTarget().GetLayer()
        # make the path relative to current edit target layer
        if not edit_layer.anonymous:
            return omni.client.make_relative_url(edit_layer.realPath, path)
        return path

    @staticmethod
    def switch_ref_rel_to_abs_path(stage, path):
        edit_layer = stage.GetEditTarget().GetLayer()
        # make the path relative to current edit target layer
        if not edit_layer.anonymous:
            return omni.client.normalize_url(edit_layer.ComputeAbsolutePath(path))
        return path

    @staticmethod
    def get_reference_prim_path_from_asset_path(
        new_asset_path: str, layer: Sdf.Layer, edit_target_layer: Sdf.Layer, ref: Sdf.Reference, can_return_default=True
    ) -> str:
        abs_new_asset_path = omni.client.normalize_url(edit_target_layer.ComputeAbsolutePath(new_asset_path))
        abs_asset_path = omni.client.normalize_url(layer.ComputeAbsolutePath(ref.assetPath))
        # if the new path is the same that the old one, and there is a prim path, we return the current prim path
        if abs_new_asset_path == abs_asset_path and ref.primPath:
            return str(ref.primPath)
        if abs_new_asset_path == abs_asset_path and not ref.primPath and can_return_default:
            return _DEFAULT_PRIM_TAG

        # Try to see if there is a default prim on the new path
        if can_return_default:
            ref_stage = Usd.Stage.Open(abs_new_asset_path)
            ref_root_prim = ref_stage.GetDefaultPrim()
            if ref_root_prim and ref_root_prim.IsValid():
                return _DEFAULT_PRIM_TAG

        # If there is not a default prim, return the previous one (the UI will check if the mesh exist)
        return str(ref.primPath)

    @staticmethod
    def ref_prim_path_is_default_prim(prim_path: str):
        return prim_path == _DEFAULT_PRIM_TAG

    @staticmethod
    def get_ref_default_prim_tag():
        return _DEFAULT_PRIM_TAG

    @staticmethod
    def is_ref_prim_path_valid(asset_path: str, prim_path: str, layer: Sdf.Layer, log_error=True):
        abs_new_asset_path = omni.client.normalize_url(layer.ComputeAbsolutePath(asset_path))
        _, entry = omni.client.stat(abs_new_asset_path)
        if not entry.flags & omni.client.ItemFlags.READABLE_FILE:
            return False
        ref_stage = Usd.Stage.Open(abs_new_asset_path)
        if prim_path == _DEFAULT_PRIM_TAG:
            ref_root_prim = ref_stage.GetDefaultPrim()
            if ref_root_prim and ref_root_prim.IsValid():
                return True
            if log_error:
                carb.log_error(f"No default prim find in {abs_new_asset_path}")
            return False
        iterator = iter(ref_stage.TraverseAll())
        for prim in iterator:
            if str(prim.GetPath()) == prim_path:
                return True
        if log_error:
            carb.log_error(f"{prim_path} can't be find in {abs_new_asset_path}")
        return False

    def add_new_reference(
        self,
        stage: Usd.Stage,
        prim_path: Sdf.Path,
        asset_path: str,
        layer: Sdf.Layer,
    ) -> Sdf.Reference:

        # it can happen that we added the same reference multiple time. But USD can't do that.
        # As a workaround, we had to create a xform child and add the reference to it.
        prim = stage.GetPrimAtPath(prim_path)
        refs_and_layers = omni.usd.get_composed_references_from_prim(prim)
        asset_path_abs = layer.ComputeAbsolutePath(asset_path)
        with omni.kit.undo.group():
            for ref, ref_layer in refs_and_layers:
                if omni.client.normalize_url(ref_layer.ComputeAbsolutePath(ref.assetPath)) == omni.client.normalize_url(
                    asset_path_abs
                ):
                    is_remix_ref = prim.GetAttribute(constants.IS_REMIX_REF_ATTR)
                    if is_remix_ref:
                        prim_path = omni.usd.get_stage_next_free_path(stage, str(prim_path), False)
                    else:
                        prim_path = omni.usd.get_stage_next_free_path(stage, str(prim_path.AppendPath("ref")), False)
                    omni.kit.commands.execute(
                        "CreatePrimCommand",
                        prim_path=prim_path,
                        prim_type="Xform",
                        select_new_prim=False,
                        context_name=self._context_name,
                    )
                    child_prim = prim.GetStage().GetPrimAtPath(prim_path)
                    child_prim.CreateAttribute(constants.IS_REMIX_REF_ATTR, Sdf.ValueTypeNames.Bool).Set(True)
                    break

            asset_path = omni.client.normalize_url(omni.client.make_relative_url(layer.identifier, asset_path))
            new_ref = Sdf.Reference(assetPath=asset_path.replace("\\", "/"), primPath=Sdf.Path())
            omni.kit.commands.execute(
                "AddReference",
                stage=stage,
                prim_path=prim_path,
                reference=new_ref,
            )
            return new_ref, prim_path

    def __anchor_reference_asset_path_to_layer(
        self, ref: Sdf.Reference, intro_layer: Sdf.Layer, anchor_layer: Sdf.Layer
    ):
        asset_path = ref.assetPath
        if asset_path:
            asset_path = intro_layer.ComputeAbsolutePath(asset_path)
            if not anchor_layer.anonymous:
                asset_path = omni.client.normalize_url(
                    omni.client.make_relative_url(anchor_layer.identifier, asset_path)
                )

            # make a copy as Reference is immutable
            ref = Sdf.Reference(
                assetPath=asset_path.replace("\\", "/"),
                primPath=ref.primPath,
                layerOffset=ref.layerOffset,
                customData=ref.customData,
            )
        return ref

    def remove_reference(
        self, stage: Usd.Stage, prim_path: Sdf.Path, ref: Sdf.Reference, intro_layer: Sdf.Layer
    ) -> Sdf.Reference:
        edit_target_layer = stage.GetEditTarget().GetLayer()
        # When removing a reference on a different layer, the deleted assetPath should be relative to edit target layer,
        # not introducing layer
        if intro_layer and intro_layer != edit_target_layer:
            ref = self.__anchor_reference_asset_path_to_layer(ref, intro_layer, edit_target_layer)
        with omni.kit.undo.group():
            # get prim
            prim = stage.GetPrimAtPath(prim_path)
            # if prim_path is mesh_*, we want to get his children and remove overrides later
            # if not, we just remove the ref xform added for duplicated refs
            prims = [prim]
            regex_is_mesh = re.compile(constants.REGEX_MESH_PATH)
            if regex_is_mesh.match(str(prim_path)):
                # we grab the children, but we skip remix ref
                prims = [
                    _prim
                    for _prim in prim.GetChildren()
                    if not _prim.GetAttribute(constants.IS_REMIX_REF_ATTR).IsValid()
                ]

            omni.kit.commands.execute(
                "RemoveReference",
                stage=stage,
                prim_path=str(prim_path),
                reference=ref,
            )

            # we should never delete /mesh_* or /light_* or /inst_*
            regex_mesh_inst_light = re.compile(constants.REGEX_MESH_INST_LIGHT_PATH)
            prims = [
                str(_prim.GetPath())
                for _prim in prims
                if _prim.IsValid() and not regex_mesh_inst_light.match(str(_prim.GetPath()))
            ]
            if prims:
                self.delete_prim(prims)

    def delete_prim(self, paths: List[str]):
        omni.kit.commands.execute(
            "DeletePrims",
            paths=paths,
            context_name=self._context_name,
        )

    def on_reference_edited(
        self,
        stage: Usd.Stage,
        prim_path: Sdf.Path,
        ref: Sdf.Reference,
        new_ref_asset_path: str,
        new_ref_prim_path: str,
        intro_layer: Sdf.Layer,
    ) -> Sdf.Reference:
        new_ref_prim_path = Sdf.Path() if new_ref_prim_path == _DEFAULT_PRIM_TAG else Sdf.Path(new_ref_prim_path)
        new_ref = Sdf.Reference(assetPath=new_ref_asset_path.replace("\\", "/"), primPath=new_ref_prim_path)

        edit_target_layer = stage.GetEditTarget().GetLayer()
        # When replacing a reference on a different layer, the replaced assetPath should be relative to
        # edit target layer, not introducing layer
        if intro_layer != edit_target_layer:
            ref = self.__anchor_reference_asset_path_to_layer(ref, intro_layer, edit_target_layer)

        if ref == new_ref:
            carb.log_info(f"Reference {ref.assetPath} was not replaced")
            return None

        omni.kit.commands.execute(
            "ReplaceReference",
            stage=stage,
            prim_path=prim_path,
            old_reference=ref,
            new_reference=new_ref,
        )
        carb.log_info(f"Reference {new_ref_asset_path} was replaced")
        return new_ref

    @staticmethod
    def is_absolute_path(path: str) -> bool:
        return _path_utils.is_absolute_path(path)

    @staticmethod
    def is_file_path_valid(path: str, layer: Sdf.Layer, log_error: bool = True) -> bool:
        return _path_utils.is_file_path_valid(path, layer=layer, log_error=log_error)

    def destroy(self):
        _reset_default_attrs(self)