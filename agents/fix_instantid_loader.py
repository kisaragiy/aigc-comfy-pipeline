"""
Script to apply a comprehensive fix to comfyui_instantid node's InstantIDModelLoader.
1. Normalises image_proj and ip_adapter from .bin or .safetensors
2. Strips perceiver_resampler. prefix
3. Infers Resampler dimensions from the model weights
"""
import os, shutil

node_path = r'C:\DrawingLive\ComfyUI\custom_nodes\comfyui_instantid\InstantID.py'

# Read current file
with open(node_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Build the replacement
old_loader = '''    def load_model(self, instantid_file):
        ckpt_path = folder_paths.get_full_path("instantid", instantid_file)

        raw = comfy.utils.load_torch_file(ckpt_path, safe_load=True)

        # Normalise into {"image_proj": {...}, "ip_adapter": {...}} regardless of format.
        st_model = {"image_proj": {}, "ip_adapter": {}}

        if ckpt_path.lower().endswith(".safetensors"):
            # Flat prefix-based format (official V2 safetensors)
            for key in raw.keys():
                if key.startswith("image_proj."):
                    st_model["image_proj"][key.replace("image_proj.", "")] = raw[key]
                elif key.startswith("ip_adapter."):
                    st_model["ip_adapter"][key.replace("ip_adapter.", "")] = raw[key]
        else:
            # .bin / .pth: loaded as nested dict
            # Normalise ip_adapter key name
            adapter_src = "ip_adapter" if "ip_adapter" in raw else "adapter_modules"
            if adapter_src in raw:
                for k, v in raw[adapter_src].items():
                    st_model["ip_adapter"][k] = v

            if "image_proj" in raw:
                for k, v in raw["image_proj"].items():
                    # Strip perceiver_resampler. prefix added by some models
                    key = k.replace("perceiver_resampler.", "")
                    # Skip old-format ImageProjModel keys (proj.0.*, proj.2.*, norm.*)
                    if key.startswith("proj.") and not key.startswith("proj_in") and not key.startswith("proj_out"):
                        continue
                    if key in ("norm.weight", "norm.bias"):
                        continue
                    st_model["image_proj"][key] = v

        model = st_model

        model = InstantID(
            model,
            cross_attention_dim=1280,
            output_cross_attention_dim=model["ip_adapter"]["1.to_k_ip.weight"].shape[1],
            clip_embeddings_dim=512,
            clip_extra_context_tokens=16,
        )

        return (model,)'''

new_loader = '''    def load_model(self, instantid_file):
        ckpt_path = folder_paths.get_full_path("instantid", instantid_file)

        raw = comfy.utils.load_torch_file(ckpt_path, safe_load=True)

        # Normalise into {"image_proj": {...}, "ip_adapter": {...}} regardless of format.
        st_model = {"image_proj": {}, "ip_adapter": {}}

        if ckpt_path.lower().endswith(".safetensors"):
            # Flat prefix-based format
            for key in raw.keys():
                if key.startswith("image_proj."):
                    st_model["image_proj"][key.replace("image_proj.", "")] = raw[key]
                elif key.startswith("ip_adapter."):
                    st_model["ip_adapter"][key.replace("ip_adapter.", "")] = raw[key]
        else:
            # .bin / .pth: loaded as nested dict
            # Normalise ip_adapter key name
            adapter_src = "ip_adapter" if "ip_adapter" in raw else "adapter_modules"
            if adapter_src in raw:
                for k, v in raw[adapter_src].items():
                    st_model["ip_adapter"][k] = v

            if "image_proj" in raw:
                for k, v in raw["image_proj"].items():
                    # Strip perceiver_resampler. prefix added by some models
                    key = k.replace("perceiver_resampler.", "")
                    # Skip old-format ImageProjModel keys (proj.0.*, proj.2.*, norm.*)
                    if key.startswith("proj.") and not key.startswith("proj_in") and not key.startswith("proj_out"):
                        continue
                    if key in ("norm.weight", "norm.bias"):
                        continue
                    st_model["image_proj"][key] = v

        # Infer Resampler dimensions from the model weights
        iproj = st_model["image_proj"]
        iadpt = st_model["ip_adapter"]

        # proj_in: Linear(embedding_dim, dim)
        dim = iproj.get("proj_in.weight", iproj.get("proj.weight")).shape[0]
        embed_dim = iproj.get("proj_in.weight", iproj.get("proj.weight")).shape[1]

        # proj_out: Linear(dim, output_dim)
        out_dim = iproj.get("proj_out.weight", torch.zeros(0)).shape[0]
        if out_dim == 0:
            out_dim = iadpt.get("1.to_k_ip.weight",
                                list(iadpt.values())[0]).shape[1]

        model = st_model

        model = InstantID(
            model,
            cross_attention_dim=dim,
            output_cross_attention_dim=out_dim,
            clip_embeddings_dim=embed_dim,
            clip_extra_context_tokens=16,
        )

        return (model,)'''

# Apply replacement
if old_loader in content:
    content = content.replace(old_loader, new_loader)
    with open(node_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: InstantIDModelLoader.load_model() patched with dynamic dimensions")
else:
    print("ERROR: Could not find old loader code. Showing search result:")
    idx = content.find('def load_model(self, instantid_file)')
    if idx >= 0:
        print(content[idx:idx+1000])
    else:
        print("'def load_model' not found at all!")
