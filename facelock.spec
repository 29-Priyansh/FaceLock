# PyInstaller spec: one folder (dist\FaceLock\FaceLock.exe), no console window.
# Build with build.ps1.

a = Analysis(
    ["run_facelock.py"],
    pathex=["."],
    datas=[
        ("models/face_detection_yunet_2023mar.onnx", "models"),
        ("models/face_recognition_sface_2021dec.onnx", "models"),    ],
    hiddenimports=["pystray._win32"],
    excludes=["pytest", "psutil", "pydoc", "PIL.ImageQt", "numpy.f2py", "numpy.distutils"],
    noarchive=False,
)

# FFmpeg is only used by OpenCV to decode video files; camera capture does not need it (~28 MB).
# Pillow's AVIF codec is never used (only the tray icon is drawn with Pillow; ~7.5 MB).
a.binaries = [b for b in a.binaries
              if "opencv_videoio_ffmpeg" not in b[0].lower() and "_avif" not in b[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaceLock",
    icon="assets/facelock.ico",
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="FaceLock", upx=False)
