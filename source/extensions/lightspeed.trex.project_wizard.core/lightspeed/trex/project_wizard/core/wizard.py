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
import stat
import subprocess
from distutils.dir_util import copy_tree
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

import carb
import omni.usd
from lightspeed.common import constants as _constants
from lightspeed.layer_manager.core import LayerManagerCore as _LayerManager
from lightspeed.layer_manager.core import LayerType as _LayerType
from lightspeed.trex.capture.core.shared import Setup as _CaptureCore
from lightspeed.trex.replacement.core.shared import Setup as _ReplacementCore
from omni.flux.utils.common import Event as _Event
from omni.flux.utils.common import EventSubscription as _EventSubscription
from omni.kit.usd.layers import LayerUtils as _LayerUtils

from .items import ProjectWizardSchema as _ProjectWizardSchema

if TYPE_CHECKING:
    from functools import partial


class ProjectWizardCore:
    CONTEXT_NAME = "ProjectWizard"

    def __init__(self):
        """
        Project Wizard core that creates project scaffolding according to a given schema.
        """
        self.__on_run_finished = _Event()
        self.__on_run_progress = _Event()
        self.__on_log_info = _Event()
        self.__on_log_error = _Event()

    def subscribe_run_finished(self, callback: Union["partial", Callable[[bool, Optional[str]], Any]]):
        """
        Return the object that will automatically unsubscribe when destroyed.
        """
        return _EventSubscription(self.__on_run_finished, callback)

    def subscribe_run_progress(self, callback: Callable[[float], Any]):
        """
        Return the object that will automatically unsubscribe when destroyed.
        """
        return _EventSubscription(self.__on_run_progress, callback)

    def subscribe_log_info(self, callback: Callable[[str], Any]):
        """
        Return the object that will automatically unsubscribe when destroyed.
        """
        return _EventSubscription(self.__on_log_info, callback)

    def subscribe_log_error(self, callback: Callable[[str], Any]):
        """
        Return the object that will automatically unsubscribe when destroyed.
        """
        return _EventSubscription(self.__on_log_error, callback)

    def setup_project(self, schema: Dict, dry_run: bool = False):
        r"""
        Run the project setup using the given schema.

        Args:
            schema: the schema to use for the project creation. Please see the documentation.
            dry_run: whether a dry run or a "real" run should be performed.

        Examples:
            >>> ProjectWizardCore(
            >>>    {
            >>>         "existing_project": False,
            >>>         "project_path": Path("R:\Remix\projects\MyProject\my_project.usda")
            >>>         "remix_directory": Path("R:\Remix\rtx_remix"),
            >>>         "mod_file": Path("R:\Remix\rtx_remix\mods\ExistingMod1\existing_mod_1.usda"),
            >>>         "existing_mods": [
            >>>             Path("R:\Remix\rtx_remix\mods\ExistingMod1\existing_mod_1.usda")
            >>>         ],
            >>>         "capture_file": Path("R:\Remix\rtx_remix\captures\capture_1.usda"),
            >>>    }
            >>>)
        """
        return asyncio.ensure_future(self.setup_project_async(schema, dry_run))

    @omni.usd.handle_exception
    async def setup_project_async(self, schema: Dict, dry_run: bool = False):
        """
        Asynchronous implementation of setup_project
        """
        await self.setup_project_async_with_exceptions(schema, dry_run)

    async def setup_project_async_with_exceptions(self, schema: Dict, dry_run: bool = False):
        """
        Asynchronous implementation of setup_project, but async without error handling.  This is meant for testing.
        """
        try:
            self._on_run_progress(0)
            self._log_info("Starting project setup")

            context, stage = await self._setup_usd_stage()
            self._on_run_progress(10)

            self._log_info("Setup core and validated schema")
            layer_manager = _LayerManager(self.CONTEXT_NAME)
            capture_core = _CaptureCore(self.CONTEXT_NAME)
            replacement_core = _ReplacementCore(self.CONTEXT_NAME)
            model = _ProjectWizardSchema(**schema)
            self._on_run_progress(20)

            project_directory = model.project_file.parent
            deps_directory = project_directory / _constants.REMIX_DEPENDENCIES_FOLDER
            mods_directory = deps_directory / _constants.REMIX_MODS_FOLDER
            captures_directory = deps_directory / _constants.REMIX_CAPTURE_FOLDER

            # Item validation should check that the symlinks are already valid if the remix_directory is None
            symlink_error = await self._create_symlinks(
                project_directory, deps_directory, model.remix_directory, dry_run
            )
            if symlink_error:
                self._log_error(symlink_error)
                self._on_run_finished(False, error=symlink_error)
                return
            self._on_run_progress(30)

            if model.existing_project:
                self._log_info(f"Project is ready: {model.project_file}")
                self._on_run_progress(100)
                self._on_run_finished(True)
                return

            stage = await self._create_project_layer(model.project_file, layer_manager, context, stage, dry_run)
            self._on_run_progress(40)

            if not dry_run and not stage:
                error_message = f"Could not open stage for the project file ({model.project_file})."
                self._log_error(error_message)
                self._on_run_finished(False, error=error_message)
                return

            await self._insert_capture_layer(capture_core, captures_directory, model.capture_file, dry_run)
            self._on_run_progress(50)

            await self._insert_existing_mods(
                replacement_core, model.existing_mods, model.mod_file, mods_directory, dry_run
            )
            self._on_run_progress(60)

            if model.mod_file:
                mod_file = await self._setup_existing_mod_project(
                    replacement_core, model.mod_file, project_directory, dry_run
                )
            else:
                mod_file = await self._setup_new_mod_project(replacement_core, project_directory, dry_run)
            self._on_run_progress(70)

            await self._save_authoring_layer(mod_file, stage, dry_run)
            self._on_run_progress(80)

            await self._save_project_layer(layer_manager, dry_run)
            self._on_run_progress(90)

            self._log_info(f"Project is ready: {model.project_file}")
            self._on_run_progress(100)
            self._on_run_finished(True)
        except Exception as e:  # noqa
            error_message = f"An unknown error occurred: {e}"
            self._log_error(error_message)
            self._on_run_finished(False, error=error_message)

    def _on_run_finished(self, result, error=None):
        self.__on_run_finished(result, error)

    def _on_run_progress(self, progress):
        self.__on_run_progress(progress)

    def _log_info(self, message):
        carb.log_info(message)
        self.__on_log_info(message)

    def _log_error(self, message):
        carb.log_error(message)
        self.__on_log_error(message)

    async def _setup_usd_stage(self):
        self._log_info("Setting up USD context and stage")

        if not omni.usd.get_context(self.CONTEXT_NAME):
            omni.usd.create_context(self.CONTEXT_NAME)

        context = omni.usd.get_context(self.CONTEXT_NAME)

        await context.new_stage_async()
        stage = context.get_stage()

        return context, stage

    async def _create_symlinks(self, project_directory, deps_directory, remix_directory, dry_run):
        if not deps_directory:
            return "Unable to find the path to the project dependencies"

        # Item validation should check that the symlinks are already valid if the remix_directory is None
        if not remix_directory:
            return None

        remix_mods_directory = remix_directory / _constants.REMIX_MODS_FOLDER
        remix_project_directory = remix_mods_directory / project_directory.stem

        if not deps_directory.exists():
            if not dry_run:
                subprocess.check_call(f'mklink /J "{deps_directory}" "{remix_directory}"', shell=True)
            else:
                self._log_info(f"Symlink from '{remix_directory}' to '{deps_directory}'")

        if remix_project_directory.exists():
            return f"A project with the same name already exists: '{remix_project_directory}'"

        if not dry_run:
            subprocess.check_call(f'mklink /J "{remix_project_directory}" "{project_directory}"', shell=True)
        else:
            self._log_info(f"Symlink from '{project_directory}' to '{remix_project_directory}'")

        return None

    async def _create_project_layer(self, project_file, layer_manager, context, stage, dry_run):
        self._log_info(f"Create project file: {project_file}")

        if dry_run:
            return stage

        layer_manager.create_new_sublayer(_LayerType.workfile, str(project_file), do_undo=False)
        await context.open_stage_async(str(project_file))

        return context.get_stage()

    async def _insert_capture_layer(self, capture_core, deps_captures_directory, capture_file, dry_run):
        if not capture_file:
            return

        deps_capture_file = deps_captures_directory / capture_file.name
        self._log_info(f"Add Sub-Layer to Project: {deps_capture_file}")

        if not dry_run:
            capture_core.import_capture_layer(str(deps_capture_file))

    async def _insert_existing_mods(self, replacement_core, existing_mods, mod_file, mods_directory, dry_run):
        if not existing_mods:
            return

        # Reverse the order since replacement layers will be inserted at index 0
        for mod in reversed(existing_mods):
            if mod == mod_file:
                continue

            mod_path = mods_directory / mod.parent.stem / mod.name
            self._log_info(f"Add Sub-Layer to Project: {mod_path}")

            if not dry_run:
                replacement_core.import_replacement_layer(
                    str(mod_path),
                    use_existing_layer=True,
                    set_edit_target=False,
                    replace_existing=False,
                    sublayer_position=0,
                )

    async def _setup_existing_mod_project(self, replacement_core, mod_file, project_directory, dry_run):
        self._log_info(f"Copy content of '{mod_file.parent}' to '{project_directory}'")

        copy_tree(str(mod_file.parent), str(project_directory), dry_run=dry_run)
        project_mod_file = project_directory / mod_file.name

        if not dry_run:
            project_mod_file.chmod(stat.S_IREAD | stat.S_IWRITE)
            replacement_core.import_replacement_layer(
                str(project_mod_file),
                use_existing_layer=True,
                set_edit_target=True,
                replace_existing=False,
                sublayer_position=0,
            )

        return project_mod_file

    async def _setup_new_mod_project(self, replacement_core, project_directory, dry_run):
        mod_file = project_directory / _constants.REMIX_MOD_FILE
        self._log_info(f"Create replacement layer: {mod_file}")

        if not dry_run:
            replacement_core.import_replacement_layer(
                str(mod_file),
                use_existing_layer=False,
                set_edit_target=True,
                replace_existing=False,
                sublayer_position=0,
            )

        return mod_file

    async def _save_authoring_layer(self, mod_file, stage, dry_run):
        self._log_info(f"Save Active Edit Target to Project: {mod_file}")

        if dry_run or not stage:
            return

        _LayerUtils.save_authoring_layer_to_custom_data(stage)

    async def _save_project_layer(self, layer_manager, dry_run):
        self._log_info("Save the project file content")

        if dry_run:
            return

        layer_manager.save_layer(_LayerType.workfile)