"""Build one CUDA extension for the TRELLIS.2 venv on Windows: python build_ext.py <package dir>
Loads the Visual Studio 2022 x64 environment (found with vswhere), points at CUDA 12.9 and the venv's ninja, then runs
pip install. The GPU target comes from TORCH_CUDA_ARCH_LIST if set, otherwise from the card in this PC
(8.6 = RTX 30 series, 8.9 = RTX 40, 12.0 = RTX 50)."""
import os, subprocess, sys
VSWHERE = os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe")
VS = subprocess.run([VSWHERE, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                     "-property", "installationPath"], capture_output=True, text=True).stdout.strip()
VCVARS = os.path.join(VS, r"VC\Auxiliary\Build\vcvars64.bat")
CUDA = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9"
env_dump = subprocess.run(f'"{VCVARS}" >nul && set', shell=True, capture_output=True, text=True).stdout
env = dict(line.split('=', 1) for line in env_dump.splitlines() if '=' in line and not line.startswith('='))
ARCH = os.environ.get("TORCH_CUDA_ARCH_LIST")
if not ARCH:
    import torch
    ARCH = "%d.%d" % torch.cuda.get_device_capability(0)
path = ";".join([CUDA + r"\bin", os.path.dirname(sys.executable), env.get('PATH', '')])   # venv Scripts has ninja.exe
env.update(CUDA_HOME=CUDA, CUDA_PATH=CUDA, PATH=path, TORCH_CUDA_ARCH_LIST=ARCH, DISTUTILS_USE_SDK="1", MAX_JOBS="6",
           CL="/std:c++17 /EHsc /permissive- /Zc:__cplusplus")   # these repos pass GCC-style cxx flags; cl.exe reads CL
pkg = os.path.abspath(sys.argv[1])
print("building", pkg, "for compute", ARCH, "with", VCVARS, flush=True)
r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--no-build-isolation", "--no-deps", "-v"], env=env)
sys.exit(r.returncode)
