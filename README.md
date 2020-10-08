## repository.anon.iptv

### About

-Watch CanalDigitaal/KPN/NLZiet/Telfort/T-Mobile/XS4ALL/Ziggo Live TV and content from anywhere in the EU

### Features

-Unofficial 3rd Party repo and plugins for Kodi

-Watch Live TV channels (dependent on your subscription)

-Replay programs from the last 7 days from all channels in your subscription

-Search Content

-Supports watching TV and listening to Radio using the PVR IPTV Simple Addon

-Supports Catchup using PVR IPTV Simple Addon in Kodi 19

### Required

-Subscription to any of the supported providers (not free)

-Kodi 18 or higher with Widevine Support (free)

### Installation
Instructions adopted from the kodi wiki, see [HOW-TO:Install add-ons from zip files](https://kodi.wiki/view/HOW-TO:Install_add-ons_from_zip_files)

-Step 1: Download the repository.anon.iptv ZIP-file from [here](https://github.com/dut-iptv/dut-iptv.github.io/raw/master/repository.anon.iptv-latest.zip)

-Step 2: To access the Add-on browser see: [How to access the Add-on browser](https://kodi.wiki/view/Add-on_manager#How_to_access_the_Add-on_browser) or [How to access the Add-on manager](https://kodi.wiki/view/Add-on_manager#How_to_access_the_Add-on_manager)

-Step 3: Select Install from zip file

-Step 4: If you have not enabled Unknown Sources, you will notified that it is disabled. If you wish to enable select Settings, if you do not wish to enable select OK. If you have already enabled Unknown sources skip to Step 7.

-Step 5: When you select Settings you will be taken to the Add-ons settings window. Enable Unknown sources if you wish to install your add-on or repository from a zip file.

-Step 6: After you enable Unknown sources you will be presented with a Warning. Make sure you read and understand this warning, then select Yes if you wish to proceed.

-Step 7: If you have selected Yes and enabled Unknown sources you can then navigate back to the Add-on browser and once again select Install from zip file

-Step 8: You will now be presented with a browser window where you can navigate to where your zip file is stored. Your zip file can be stored anywhere your device has access to and can be either on local storage or a network share.

-Step 9: Once you have navigated to the zip file you downloaded in Step 1, select it then select OK. You will be notified when the repository is installed succesfully.

-Step 10: Navigate back to the Add-on browser and select Install from repository

-Step 11: Navigate to Dutch IPTV Repository

-Step 12: Navigate to Video add-ons

-Step 13: Select one or more of the available addons to install, dependencies will automatically be installed

### Additional instructions for general Linux / OSMC

- The addons require the pycryptodomex packages, which is not included in OSMC and possibly general linux distributions

- These steps are not required for CoreELEC/LibreELEC/Windows/Android/Mac

- Execute the following commands in a terminal:

```
sudo apt-get install python-crypto
sudo apt-get install build-essential python-pip
sudo pip install -U setuptools
sudo pip install wheel
sudo pip install pycryptodomex
```

### Data Usage

-Please note that these addons automatically download new EPG guides whenever the current EPG is older than 12 hours.

-This means data usage will be between 10 - 50 MB per enabled addon per day that Kodi is run dependent on your settings (all/minimal channels).

-This data usage will happen whenever kodi is running, even when not starting/opening the addons

-Considering only installing these addons on an unmettered connection

### To-Do

-

### Thanks

-Matt Huisman for his development of the kodi addons that where used as a base for this addon

-peak3d for Inputstream Adaptive

-Team Kodi for Kodi