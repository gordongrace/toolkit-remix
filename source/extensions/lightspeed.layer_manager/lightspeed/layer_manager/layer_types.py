"""
* Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
*
* NVIDIA CORPORATION and its licensors retain all intellectual property
* and proprietary rights in and to this software, related documentation
* and any modifications thereto.  Any use, reproduction, disclosure or
* distribution of this software and related documentation without an express
* license agreement from NVIDIA CORPORATION is strictly prohibited.
"""
from enum import Enum


class LayerType(Enum):
    autoupscale = "autoupscale"
    capture_baker = "capture_baker"
    capture = "capture"
    replacement = "replacement"
    workfile = "workfile"


class LayerTypeKeys(Enum):
    layer_type = "lightspeed_layer_type"
