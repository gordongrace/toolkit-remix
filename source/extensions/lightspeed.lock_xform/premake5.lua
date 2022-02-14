-- Use folder name to build extension name and tag. Version is specified explicitly.
local ext = get_current_extension_info()

-- That will also link whole current "target" folder into as extension target folder:
project_ext (ext)
    repo_build.prebuild_link {
        {"python/lightspeed/", ext.target_dir.."/lightspeed"},
        -- { "data", ext.target_dir.."/data" },
        -- { "docs", ext.target_dir.."/docs" },
        -- { "example", ext.target_dir.."/example" },
    }