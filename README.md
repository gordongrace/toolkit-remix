# Kit Extensions & Apps Example :package:

This repo is the gold standard for building Kit extensions and applications.

The idea is that you fork it, trim down parts you don't need and use it to develop your extensions and applications. Which then can be packaged, shared, reused.


# Setting up your new repo based off the template

To get started, you will need to do a few things:

## 1. Duplicate the template (kit-template repo)


* Fork [https://gitlab-master.nvidia.com/omniverse/kit-extensions/kit-template](https://gitlab-master.nvidia.com/omniverse/kit-extensions/kit-template) into your own space (i.e https://gitlab-master.nvidia.com/your_username result should look like below


![alt_text](data/readme_images/new_repo1.png "new_repository")


* Rename the project and it’s path to be what you want 


![alt_text](data/readme_images/new_repo2.png "new_repository")

* Transfer the project back to the kit-extensions group with it’s new name


![alt_text](data/readme_images/transfer_ownership.png "transfer_ownership")


Note that if you have permissions problems transferring back, you should ask or another maintainer to give you permissions.

Note that the new project still has a fork relationship with kit-template, which means it’s possible to submit and merge MRs across the forks. One disadvantage of this, is that when you submit a new MR, the target branch will be by default in kit-template (maybe it’s possible to change this)


## 2. Modify the build/repo/toolchain configuration files

To start with, find any occurrences of kit-template, kit_template etc and replace with your project name/
Whenever the originals in kit-template get updated, you can either: 

+ if you have a fork, can do a normal MR too, cherry-pick changes etc..
+ Alternatively just copy them over from kit-template like this: 

```
cp -R build.bat build.sh .clang-format deps/ docs/ .editorconfig format_code.bat format_code.sh .gitattributes .gitignore package.toml premake5.lua repo.bat repo.sh repo.toml setup.sh tools/ .vscode/ ../kit-usd/
```
And then merge… 


## 3. Duplicate the TeamCity project

This is mostly just a question of:
1. Navigating to [https://teamcity.nvidia.com/project/Omniverse_KitExtensions_KitTemplate?mode=builds](https://teamcity.nvidia.com/project/Omniverse_KitExtensions_KitTemplate?mode=builds)
2. Clicking _Edit Project..._, then _Actions_ > _Copy project..._ on the upper right-hand corner of the page. \
**Note:** Should you not see the _Actions_ menu at the top of the page, navigate to [https://dlrequest](https://dlrequest/GroupID/Groups/MyGroups#MyMemberships) and validate that you are a member of the `carbonite-dev` and `omniverse-dev` groups. If not, request access and once it has been granted, wait a few minutes before refreshing the TeamCity page.
3. From the _Copy Project_ modal dialog, modify the _VCS Root ID_ in order to match the name of the new project, and save it under another name. \
As a general rule of thumb, replace every instance of `KitTemplate` with the name of your project, to ensure some kind of uniqueness.
4. (Optional) You may choose to uncheck the _Copy build configurations' build counters_ option should you wish to start your new TeamCity project builds from `1`.
5. Clicking the _Copy_ button of the dialog.



# Working with your new repo

1. run `build.bat`
2. run `_build\windows-x86_64\debug\omni.app.new_exts.bat` or `_build\windows-x86_64\debug\omni.app.new_exts_mini.bat`
3. notice enabled extensions in "Extension Manager Window" of Kit. Also notice that one of them brought its own test in "Test Runner" window.

*. for running from python run `_build\windows-x86_64\debug\example.pythonapp.bat`

It downloads Kit SDK via packman ([target-deps.packman.xml](deps/target-deps.packman.xml)) or you can use your local build. During build phase extensions are built (native), staged (copied and linked) into
`_build/{platform}/{config}/extensions` folder. Then we just run Kit with custom config which sets to enable those extensions.

## What's included

### Extensions

```mermaid
graph TD

  subgraph "python"
  A3(__init__.py + python code)
  end

  subgraph cpp
  A1(__init__.py)
  A1 -- carb::Framework --> B1(omni.ext-example_cpp_ext.plugin.dll)
  end

  subgraph "mixed"
  A2(__init__.py + python code)
  A2 --import _mixed_ext--> B2(example.mixed_ext.python)
  B2 -- carb::Framework --> C2(example.mixed_ext.plugin.dll)
  end


  
  Kit[Kit] --> A1
  Kit[Kit] --> A2
  Kit[Kit] --> A3

```

Each extension is a folder(or zip archive) in the end. You can write user code in python code only, or C++ only, or both. Ultimately extension archive could contain python code, python bindings (pyd/so files) and C++ plugins (dll/so). Each binary file is platform and configuration (debug/release, optionally) specific, one archive can contain binaries for multiple platforms, we put them in separate folders and follow proper naming of python bindings (https://stackoverflow.com/a/37028661).

For more info refer to Kit documentation: http://omnidocs-internal.nvidia.com/py/index.html. 

#### example.python_ext

Example of pure python extesion

[source](source/extensions/example.python_ext)


#### example.cpp_ext

Example of native (C++ only) extension.

[source](source/extensions/example.cpp_ext)


#### example.mixed_ext

Example of mixed extension which has both C++ and python code. They interact via python bindings built and included with this extension.

[source](source/extensions/example.mixed_ext)

### Apps

Example of an app which runs only those 3 extensions in Kit (and test_runner for tests). All configs are in [source/apps](source/apps), they are linked during build (stage phase).

> `_build\windows-x86_64\debug\omni.app.new_exts.bat`
> `_build\windows-x86_64\debug\omni.app.new_exts_mini.bat`

It also includes example of running Kit from python, both default Kit and an app which runs only those 3 extensions in Kit. 

> `_build\windows-x86_64\debug\example.pythonapp.bat`

That runs default python example, to see list of examples:

> `_build\windows-x86_64\debug\example.pythonapp.bat --help`

Pass different one as first argument to run it.



## Using a Local Build of Kit SDK

To use your local build of Kit SDK, assuming it is located say at `C:/projects/kit`.

Use `repo_source` tool to link: 

> `repo source link kit-sdk c:/projects/kit/kit`

Or use GUI mode to do source linking:

> `repo source gui`

Or you can also do it manually: create a file: `deps/target-deps.packman.xml.user` containing the following lines:

```xml
<project toolsVersion="5.6">
	<dependency name="kit_sdk_${config}" linkPath="../_build/${platform}/${config}/kit">
		<source path="c:/projects/kit/kit/_build/$platform/$config" />
	</dependency>
</project>
```

To remove source link:

> `repo source unlink kit-sdk`

To remove all source links:

> `repo source clear`

## How to get your extensions into the hands of users

We publish extensions to an extension repository. There are a number of these. This can be done manually from inside Kit (Extensions Window->Burger menu->Publishing Enabled… see below) or via command line from Kit, example: \
 \
`kit.exe --ext-folder C:\eoin\code\eoin\eoin-kit-extensions --publish omni.jira `

![alt_text](data/readme_images/extension_registry_publish.png "image_tooltip")


There is a validation stage to make sure that you have added the necessary icons, changelog, correct version number etc, and publish will not complete if validation does not pass




# Appendix : Details on Build tools/RepoMan/CI system etc

## Packman
The basic package management tool used on OV, see [packman](https://gitlab-master.nvidia.com/hfannar/packman). A copy of the currently used packman lives in tools/packman in most repositories. It can be easily upgraded to newer versions
## Repo Tools "RepoMan"

These are a set of small utility libraries whose source lives in [https://gitlab-master.nvidia.com/omniverse/repo](https://gitlab-master.nvidia.com/omniverse/repo). They are dependencies of your project (you can set their versions by changing deps/repo-deps.packman.xml, or using `repo source`. The first time you build your project, the chosen versions will be downloaded into _repo.

They have a single entry point which is `./repo.sh[.bat]` in the root of your repo.  

Calling this on it's own will show a list of available tools. Each command can be explored with `--help` flag.


They are configured via a number of *.toml files in the root of your repository (mostly repo.toml)
 
What do they do? Many of them are used by Teamcity to execute various parts of the build pipeline (build/package/publish etc), but many of them can be executed locally also to perform various tasks

A simplified build pipeline as used by most tools is: 
```
build->package->test->publish
```

CI: Normally the repo tools are called via a batch file (.bat/.sh) in teamcity. As a general principle, we should be able to run the same thing locally by just calling the batch script.. Below in yellow is an example script. 

![alt_text](data/readme_images/TC_build_step.png "TC pipeline")

They live in the ./tools folder of your repo

There are many repo tools, the version of each to use is defined in deps/repo-deps.packman.xml in each repository, and the code for these is downloaded to the _repo folder

General notes:
* Some of these tools work with your local source, some of them work with packaged artefacts, some give you the option of either. Normally TC jobs will be working with packaged artefacts
* Some of them require you to specify a "config" e.g release or debug, via -c/--config usually. Some default to debug if nothing is passed
* In order to call your repo setup a success, I think you would have to be able to run your CI pipeline successfully, and successfully run at least build and test locally (ideally on multiple platforms)
* If you cannot work out why TC jobs are failing, it can be useful to log into the host after the job has completed. Ask on #ct-teamcity, they will allow you access to a host, where you can ssh in via [http://10.36.9.12:8080/guacamole-1.2.0/#/](http://10.36.9.12:8080/guacamole-1.2.0/#/)
* Not all TC jobs are equal - some stages of the pipeline are triggered by any commit to an MR, some (e.g publishing) might only happen on master
* Most build/packaging/testing etc is done separately for Windows/Linux (and now ARM) platforms, even for Python only

There are additional flags for most tools, all documented in the tool itself via --help e.g
```
repo.sh changelog --help
```

#### repo build

Basic Usage: `repo.bat build` or `build.bat` 

Simply, this will build your project. In more detail, it will:

1. pull and link dependencies (via packman),
2. setup vscode (generate python stub files and all of the other plumbing needed to get good intellisense/code completion for vscode in your project, as well as with Kit, USD etc)
3. Generate  license files
4. file copy and link
5. pip install
6. project generation
7. toolchain build call (which in the case of pure python is eally just creating some symlinks. This is equivalent to calling ./build.[.sh][.bat] from the root of the repo

**VSCode**
Kit and OV projects in general are set up to use VSCode. You’ll usually find the following in a .vscode folder in your repo (Note: Work out when these files are generated/updated.. At build time?)

*   c_cpp_properties.json
*   extensions.json
*   global-snippets.code-snippets
*   json.code-snippets
*   launch.json
*   settings.json
*   settings.template.json
*   tasks.json

to get going, Install VsCode python extension, close VsCode, run `build.bat` first time (`-s` flag is enough), open project again. Python intellisense, linter, formatting should work (we bring our own version of python).

#### repo build_doc

Basic usage: `repo.bat build_docs` or `tools/build_docs.bat`

Builds documentation from the debug build of your project. Not sure if this is used in practice with extensions 

With the template project, results will be built in `_build/docs`. Sources are in [docs](docs) folder.

Document your python code with [Google Docstring](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html), more info in: (https://gitlab-master.nvidia.com/carbon/Carbonite/blob/master/docs/Documenting.md)


#### repo publish_ext

This will publish extensions to the test extension repository which is used by ETM (Extension Test manager)to test extensions when kit sdk versions and other apps are updated (see ##ct-omni-extensions-testing-matrix

_This will normally be called by TC_ rather than locally

#### repo package

Basic usage: `repo.bat package` or `tools/package.bat`

Prepares final package (use [package.toml](package.toml) to configure)

It will build zip/7z artefacts which can be published to packman (e.g http://packman.ov.nvidia.com/packages/omniverse-kit is where kit packages end up). With extension repos, that’s not usually how we publish our extensions anymore (we’re still transitioning though) so mostly this is just used by TC to pass to successive pipeline stages. Different platforms will be built normally on their respective machine types.

Normally the different artefacts per platform/configuration are stored in _build/packages or _build/builtpackages(this is of course configurable)

Example: \
`./repo.sh package -a`


```
Creating 7z archive: '/home/eoinm/code/omniverse/kit-extensions/kit-usd/_build/packages/kit-usd-extensions@101.1.0+collection_1.0.ce3e9c61.gitlab.linux-x86_64.debug'...
Creating 7z archive: '/home/eoinm/code/omniverse/kit-extensions/kit-usd/_build/packages/kit-usd-extensions@101.1.0+collection_1.0.ce3e9c61.gitlab.linux-x86_64.release'...
```


An archive should be self contained, in the sense that if it doesn’t contain everything it needs to run the extensions, it should contain scripts to bootstrap itself or download dependencies(e.g there’s a “pull_kit_sdk.sh” script which downloads kit… this can be added to your build by including: \
`dofile("tools/autopull/premake5.lua")`..in your main premake5.lua file

#### repo publish

This will publish to packman. As above, should not generally be needed for extensions


#### repo test

Very simple entry point for running your tests (startup and unit?) locally, or on TC

This is what TC will run on the packaged build.

When you do a build, some magic in the build will generate some bat/sh scripts that will run your tests, e,g “tests-python-omni.kit.widget.collection.sh”. This is just starting up Kit, enabling the appropriate extensions, and running their test. “Repo test” is just running those scripts

As well as running tests, it will look for particular patterns in the output (stdout/stderr) to fail on, and others to ignore (configurable).

There’s an assumption that:
*   if you are running tests locally that you have a local kit build, which can be found by looking at depts/kit-sdk.packman.xml (you can update this to a local dev checkout or any kit by using repo source to modify the dependency, see below)
*   If you are running on TC, you don’t so a kit will have to be checked out

Note: `${test_root}` will be set if you run `--from-package`

Kit-template also provide examples of writing different tests. They all grouped into one test suite and defined in `repo.toml` file.

Example usage:

> `repo.bat test --config debug`


#### repo source

This allows you to link to local versions of packman dependencies

#### repo format

Basic usage: `repo.bat format` or `format_code.bat`
This will format C++ and Python code according to OV conventions (using black for Python).It can also verify formatting is correct

This is currently optional (ie run manually/locally)

#### repo update

This updates your dependencies by modifying the deps/*xml files to the latest versions (major/minor constraints can be specified)

This is a local only step

#### repo licensing

Will generate licence files for your extensions… most of this is actually handled at the build stage, so not sure where it's neede

#### repo changelog

Future work is to update this so it can automatically generate the changelogs for extensions from git commits - currently it works mostly for Kit-based applications

#### repo build_number

Used by TC only


## Config files

* `premake5.lua` - all configuration for generating platform specific build solutions. [premake5 docs](https://github.com/premake/premake-core/wiki).
* `repo.toml` - configuration of all repo tools (build, package, format etc).
* `package.toml` - lists file wildcards to include in packages



## CI/Teamcity

[Teamcity Project](https://teamcity.nvidia.com/project/Omniverse_KitExtensions_KitTemplate?mode=builds) runs on every commit. Builds both platforms, docs, runs tests. Publishing is optional (click "Run" on "publish" configuration).

It can also be easily copied in Teamcity along with forking this project on gitlab.

According to [RepoMan Guidelines](https://omniverse.gitlab-master-pages.nvidia.com/repo/repo_man/manual/overview.html#core-principles) all Teamcity entry points are in [tools/ci](tools/ci) folder.






# References

+ See [Nathan Cournia's repo tools example](https://gitlab-master.nvidia.com/omniverse/repo/repo_example)
+ See [Anton's buildsystem videos](https://drive.google.com/drive/folders/1XAmdhYQkTQlLwDqHOlxJD7k6waUxYAo7?usp=sharing) for Anton’s videos about the build systems. Topics are: 

  1. Intro
  2. Simple Extension
  3. Versioning
  4. Tags
  5. Settings
  6. Reloading
  7. Extensions Window
  8. Publishing
  9. .Kit file
  10. Build System (repo tools)
  11. Build System (premake)
  12. Build System (simple extension in premale)
  13. Build System (Advanced Extension)
