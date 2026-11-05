"""Build one CUDA extension for the TRELLIS.2 venv on Windows: python build_ext.py <package dir>
Loads the Visual Studio 2022 x64 environment, points at CUDA 12.9 and ninja, then runs pip install."""
import os, subprocess, sys
VCVARS = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
CUDA = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9"
env_dump = subprocess.run(f'"{VCVARS}" >nul && set', shell=True, capture_output=True, text=True).stdout
env = dict(line.split('=', 1) for line in env_dump.splitlines() if '=' in line and not line.startswith('='))
NINJA = r"D:\AI\Hunyuan3D2\Hunyuan3D2_WinPortable\python_standalone\Scripts"   # has ninja.exe
path = ";".join([CUDA + r"\bin", NINJA, os.path.dirname(sys.executable), env.get('PATH', '')])
env.update(CUDA_HOME=CUDA, CUDA_PATH=CUDA, PATH=path, TORCH_CUDA_ARCH_LIST="8.6", DISTUTILS_USE_SDK="1", MAX_JOBS="6",
           CL="/std:c++17 /EHsc /permissive- /Zc:__cplusplus")   # these repos pass GCC-style cxx flags; cl.exe reads CL
pkg = os.path.abspath(sys.argv[1])
r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--no-build-isolation", "--no-deps", "-v"], env=env)
sys.exit(r.returncode)
