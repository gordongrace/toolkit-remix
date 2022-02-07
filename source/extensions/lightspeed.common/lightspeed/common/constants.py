MATERIAL_INPUTS_DIFFUSE_TEXTURE = "inputs:diffuse_texture"
MATERIAL_INPUTS_NORMALMAP_TEXTURE = "inputs:normalmap_texture"
MATERIAL_INPUTS_TANGENT_TEXTURE = "inputs:tangent_texture"
MATERIAL_INPUTS_REFLECTIONROUGHNESS_TEXTURE = "inputs:reflectionroughness_texture"
MATERIAL_INPUTS_EMISSIVE_MASK_TEXTURE = "inputs:emissive_mask_texture"
MATERIAL_INPUTS_METALLIC_TEXTURE = "inputs:metallic_texture"
ROOTNODE = "/RootNode"
ROOTNODE_LOOKS = ROOTNODE + "/Looks"
ROOTNODE_INSTANCES = ROOTNODE + "/instances"
ROOTNODE_MESHES = ROOTNODE + "/meshes"
INSTANCE_PATH = ROOTNODE_INSTANCES + "/inst_"
MESH_PATH = ROOTNODE_MESHES + "/mesh_"
SHADER = "Shader"
MATERIAL = "Material"
SCOPE = "Scope"
AUTO = "auto"
LSS_FOLDER = "lss"
GAME_READY_ASSETS_FOLDER = "gameReadyAssets"
CAPTURE_FOLDER = "capture"


TEXTURE_COMPRESSION_LEVELS = {
    MATERIAL_INPUTS_DIFFUSE_TEXTURE: "bc7",
    MATERIAL_INPUTS_NORMALMAP_TEXTURE: "bc7",
    MATERIAL_INPUTS_TANGENT_TEXTURE: "bc5",
    MATERIAL_INPUTS_REFLECTIONROUGHNESS_TEXTURE: "bc4",
    MATERIAL_INPUTS_EMISSIVE_MASK_TEXTURE: "bc7",
    MATERIAL_INPUTS_METALLIC_TEXTURE: "bc4",
}

AUTOUPSCALE_LAYER_FILENAME = "autoupscale.usda"
