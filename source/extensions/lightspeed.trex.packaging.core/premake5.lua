-- Use folder name to build extension name and tag. Version is specified explicitly.
local ext = get_current_extension_info()

-- Link the current "target" folders into the extension target folder:
project_ext (ext)
repo_build.prebuild_link {
    { "apps", ext.target_dir.."/apps" },
    { "bin", ext.target_dir.."/bin" },
    { "data", ext.target_dir.."/data" },
    { "docs", ext.target_dir.."/docs" },
    { "lightspeed", ext.target_dir.."/lightspeed" },
}
