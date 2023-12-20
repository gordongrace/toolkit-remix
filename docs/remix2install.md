# Installation Guide

## Installing and Launching RTX Remix

RTX Remix consists of two components - the **RTX Remix Runtime** and the **RTX Remix Toolkit**.  The **RTX Remix Runtime**, which is open source,  injects the path tracing into the game and bridges the gap between the original game's renderer and the RTX Toolkit.  The **RTX Remix Toolkit** allows you to modify captures created via the RTX Runtime, ingest assets, and make scene changes.  Both are required to fully remaster a game end-to-end.


## Install the RTX Remix Runtime

To install the RTX Runtime, you’ll need to download the latest application through GitHub via this link: [github.com/NVIDIAGameWorks/rtx-remix](https://github.com/NVIDIAGameWorks/rtx-remix/releases/).

> This version includes the **Runtime Bridge** and the **DXVK-Remix** applications required to run the Runtime.  You may download these applications separately through GitHub.
>  1. For the Bridge Application: [bridge-remix](https://github.com/NVIDIAGameWorks/bridge-remix).
> 2. For the DXVK-Remix application: [dxvk-remix](https://github.com/NVIDIAGameWorks/dxvk-remix/)

When you download the RTX Remix runtime, you should get a zip file with the necessary components to prep a supported game for RTX Remix. Unzipping the file, you should see a folder structure like the following:

```text
remix-0.1.0/
|--- d3d9.dll  <-- Bridge interposer
|--- ...
\--- .trex/
    |--- NvRemixBridge.exe
    |--- d3d9.dll  <-- Remix Runtime/Renderer
    \--- ...
```



## Install and Launch the RTX Remix Toolkit

1. Follow the instructions on how to Install the NVIDIA Omniverse Platform here: [Install NVIDIA Omniverse](https://docs.omniverse.nvidia.com/install-guide/latest/index.html)
2. In Omniverse Launcher, under the Exchange Tab, search for “**RTX Remix**”

![OmniverseExchange](data/images/rtxremix_008.PNG)

3. Select RTX Remix Application, (ensure that the dropdown next to the install button displays the latest release or the release you wish to download) and select the green “**INSTALL**” button to install the application

![OmniverseRemixApp](data/images/rtxremix_009.PNG)

4. After the application has been installed, the green “**INSTALL**” button will change into a grayish-white “**LAUNCH**” button.  Click the LAUNCH button to launch the** RTX Remix** application.

![InstallOmniverseRemixApp](data/images/rtxremix_010.PNG)

***
<sub> Need to leave feedback about the RTX Remix Documentation?  [Click here](https://docs.google.com/forms/d/1vym6SgptS4QJvp6ZKTN8Mu9yfd5yQc76B3KHIl-n4DQ/prefill) <sub>