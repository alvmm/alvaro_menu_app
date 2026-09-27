[app]

# (str) Title of your application
title = Menú Álvaro & Pareja

# (str) Package name
package.name = alvaromenu

# (str) Package domain (needed for android/ios packaging)
package.domain = com.alvaroypareja.menu

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all files)
source.include_exts = py,png,jpg,kv,json,txt,md,csv

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,openssl

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET, ACCESS_NETWORK_STATE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version
android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) List of Android architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) Enable AndroidX support
android.enable_androidx = True

# (bool) Automatically accept SDK licences
android.accept_sdk_license = True

# (str) The Android entry point, default is ok
# android.entrypoint = org.kivy.android.PythonActivity

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = false, 1 = true)
warn_on_root = 0

