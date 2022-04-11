-- Use folder name to build extension name and tag. Version is specified explicitly.
local ext = get_current_extension_info()

-- That will also link whole current "target" folder into as extension target folder:
project_ext (ext)
    os.execute 'git clone https://gitlab-master.nvidia.com/lightspeedrtx/lss-externals/lss-pytorch-CycleGAN-and-pix2pix/ ./lightspeed/common/tools/pytorch-CycleGAN-and-pix2pix'
    repo_build.prebuild_link {
        { "data", ext.target_dir.."/data" },
        { "docs", ext.target_dir.."/docs" },
        { "lightspeed", ext.target_dir.."/lightspeed" },
    }