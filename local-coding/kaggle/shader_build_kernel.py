"""Kaggle CPU kernel: compile PTQ1_0 matvec shader variants with REAL optimization.

The local glslc shim can't optimize (glslang has no optimizer); glslc -O ==
glslang + spirv-opt. This kernel (CPU only, no GPU quota) installs glslang-tools
+ spirv-tools, clones the fork, applies our shader payload, and compiles every
variant (f32/f16 x normal/subgroup) with glslangValidator + spirv-opt -O.

Output: /kaggle/working/spv/<variant>.<fnv1a64(expanded src)>.<vname>.spv
        /kaggle/working/manifest.json
Import locally: copy spv/* into C:/tools/bin/spv-precompiled/ and rebuild; the
shim picks them up by the same key (fnv over expanded source + variant name).
"""
import json
import os
import re
import shutil
import subprocess

PAYLOAD = __PAYLOAD__  # {"__types_glsl__": <whole types.glsl>, "<variant_id>": <comp source>}
REPO = "https://github.com/PrismML-Eng/llama.cpp"
TAG = "prism-b10709-9a9394a"
SH = "ggml/src/ggml-vulkan/vulkan-shaders"
OUT = "/kaggle/working"
CANON = "mul_mat_vec_ptq1_0.comp"

VARIANTS = {
    "f32":     {"B_TYPE": "float",      "B_TYPEV2": "vec2",    "B_TYPEV4": "vec4"},
    "f16":     {"B_TYPE": "float16_t",  "B_TYPEV2": "f16vec2", "B_TYPEV4": "f16vec4"},
    "f32_sub": {"B_TYPE": "float",      "B_TYPEV2": "vec2",    "B_TYPEV4": "vec4", "USE_SUBGROUP_ADD": "1"},
    "f16_sub": {"B_TYPE": "float16_t",  "B_TYPEV2": "f16vec2", "B_TYPEV4": "f16vec4", "USE_SUBGROUP_ADD": "1"},
}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def expand(path, depth=0):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r'\s*#include\s+"([^"]+)"', line)
            if m and depth < 16:
                out.append(expand(os.path.join(os.path.dirname(path), m.group(1)), depth + 1))
            else:
                out.append(line)
    return "".join(out)


def fnv1a64(data):
    h = 0xcbf29ce484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def main():
    import shutil
    if shutil.which("vulkaninfo"):
        r = sh(["vulkaninfo", "--summary"])
        print("vulkaninfo probe:", "PRESENT" if r.returncode == 0 else "fallo")
    else:
        print("vulkaninfo: ausente (esperado en Kaggle; solo probe)")
    r = sh(["apt-get", "update", "-qq"]) and sh(["apt-get", "install", "-y", "-qq", "glslang-tools", "spirv-tools"])
    print("apt:", "ok" if os.system("which glslangValidator spirv-opt > /dev/null 2>&1") == 0 else "FALLO")
    print(sh(["glslangValidator", "--version"]).stdout.splitlines()[:1])
    print(sh(["spirv-opt", "--version"]).stdout.splitlines()[:1])

    if not os.path.isdir("/repo"):
        sh(["git", "clone", "--depth", "1", "-b", TAG, REPO, "/repo"])
    types = PAYLOAD.pop("__types_glsl__")
    with open(f"/repo/{SH}/types.glsl", "w", encoding="utf-8") as f:
        f.write(types)

    os.makedirs(f"{OUT}/spv", exist_ok=True)
    manifest = {}
    for vid, src in sorted(PAYLOAD.items()):
        with open(f"/repo/{SH}/{CANON}", "w", encoding="utf-8") as f:
            f.write(src)
        exp = expand(f"/repo/{SH}/{CANON}")
        with open("/tmp/x.comp", "w", encoding="utf-8") as f:
            f.write(exp)
        src_h = fnv1a64(exp.replace("\r", "").encode("utf-8"))
        for vname, vdef in VARIANTS.items():
            defines = {"DATA_A_PTQ1_0": "1", "FLOAT_TYPE": "float", "FLOAT_TYPEV2": "vec2",
                       "D_TYPE": "float", **vdef}
            args = ["glslangValidator", "-V", "-S", "comp", "--target-env", "vulkan1.2"]
            args += [f"-D{k}={v}" for k, v in defines.items()]
            args += ["/tmp/x.comp", "-o", "/tmp/x.spv"]
            r = sh(args)
            if r.returncode != 0:
                manifest[f"{vid}.{src_h}.{vname}"] = {"status": "glslang_fail", "err": (r.stdout + r.stderr)[-400:]}
                print(f"[{vid}/{vname}] glslang FAIL:", (r.stdout + r.stderr)[-200:])
                continue
            used_opt = False
            r2 = sh(["spirv-opt", "-O", "/tmp/x.spv", "-o", "/tmp/x.opt.spv"])
            if r2.returncode == 0:
                shutil.copy("/tmp/x.opt.spv", f"/tmp/x.use.spv")
                used_opt = True
            else:
                shutil.copy("/tmp/x.spv", "/tmp/x.use.spv")
                print(f"[{vid}/{vname}] spirv-opt FAIL (sin -O):", (r2.stdout + r2.stderr)[-200:])
            key = f"mul_mat_vec_ptq1_0.{src_h}.{vname}.spv"
            shutil.copy("/tmp/x.use.spv", f"{OUT}/spv/{key}")
            manifest[key] = {"status": "ok", "optimized": used_opt, "variant": vid,
                             "bytes": os.path.getsize(f"{OUT}/spv/{key}")}
            print(f"[{vid}/{vname}] OK {'(spirv-opt -O)' if used_opt else '(sin opt)'}")

    with open(f"{OUT}/manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    ok = sum(1 for v in manifest.values() if v.get("status") == "ok")
    print(f"=== {ok}/{len(manifest)} spv listos en {OUT}/spv ===")


if __name__ == "__main__":
    main()
