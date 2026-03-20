#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
import zipfile
import json
import uuid
import uuid as uuid_lib

# Colors for terminal output
class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[36m'
    GRAY = '\033[37m'
    ENDC = '\033[0m'

def status_message(msg_type, message):
    if msg_type == "completion":
        print(f"{Colors.GREEN}[+] {Colors.GRAY}{message}{Colors.ENDC}")
    elif msg_type == "process":
        print(f"{Colors.YELLOW}[•] {Colors.GRAY}{message}{Colors.ENDC}")
    elif msg_type == "critical":
        print(f"{Colors.RED}[X] {Colors.GRAY}{message}{Colors.ENDC}")
    elif msg_type == "error":
        print(f"{Colors.RED}[ERROR] {Colors.GRAY}{message}{Colors.ENDC}")
    elif msg_type == "info":
        print(f"{Colors.BLUE}{message}{Colors.ENDC}")
    elif msg_type == "plain":
        print(f"{Colors.GRAY}{message}{Colors.ENDC}")

def setup_phase(args):
    # 1. Dependency checks - only need Pillow (PIL) now
    try:
        from PIL import Image
        status_message("completion", "Pillow (PIL) is available. No external image tools needed.")
    except ImportError:
        status_message("error", "Python Pillow library is required. Install with: pip install Pillow")
        sys.exit(1)

    # 2. Input validation
    input_pack = args.input_pack
    if not os.path.isfile(input_pack):
        status_message("error", f"Input resource pack is not in this directory or does not exist.")
        sys.exit(1)
    status_message("process", f"Input file detected.")

    # 3. User configuration overrides
    attachable_material = args.attachable_material
    block_material = args.block_material
    fallback_pack = args.fallback_pack

    status_message("plain", f"\nGenerating Bedrock 3D resource pack with settings:")
    status_message("plain", f"{Colors.GRAY}Input pack to merge: {Colors.BLUE}{args.merge_input}")
    status_message("plain", f"{Colors.GRAY}Attachable material: {Colors.BLUE}{attachable_material}")
    status_message("plain", f"{Colors.GRAY}Block material: {Colors.BLUE}{block_material}")
    status_message("plain", f"{Colors.GRAY}Fallback pack URL: {Colors.BLUE}{fallback_pack}\n")

    # Persistent Vanilla Cache path
    vanilla_cache_dir = "vanilla_cache"
    os.makedirs(vanilla_cache_dir, exist_ok=True)

    status_message("process", f"Setting up conversion environment for (Python Parity Version)")
    
    for f in ["config.json", "pack.mcmeta", "pack.png"]:
        if os.path.exists(f): os.remove(f)
    for d in ["pack", "scratch_files", "target"]:
        if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)
        
    os.makedirs("target/rp", exist_ok=True)
    os.makedirs("scratch_files", exist_ok=True)
    
    # 4. Handle default assets (Vanilla Cache)
    default_assets_zip = args.default_assets if args.default_assets else "default_assets.zip"
    if os.path.exists(default_assets_zip):
        # Only extract if vanilla_cache/assets does not exist
        if not os.path.exists(os.path.join(vanilla_cache_dir, "assets")):
            status_message("process", f"Extracting {default_assets_zip} into persistent cache...")
            with zipfile.ZipFile(default_assets_zip, 'r') as zip_ref:
                # Find top-level assets folder
                top_level = None
                for name in zip_ref.namelist():
                    if "/assets/" in name or name.startswith("assets/"):
                        if "/assets/" in name:
                             top_level = name.split("/assets/")[0] + "/"
                        break
                
                if top_level:
                    for item in zip_ref.namelist():
                        if item.startswith(top_level):
                            relative_path = item[len(top_level):]
                            if not relative_path: continue
                            target_path = os.path.join(vanilla_cache_dir, relative_path)
                            if item.endswith('/'):
                                os.makedirs(target_path, exist_ok=True)
                            else:
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                with zip_ref.open(item) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                else:
                    zip_ref.extractall(vanilla_cache_dir)
            status_message("completion", "Vanilla assets cached.")
        else:
            status_message("info", "Using existing vanilla assets from cache.")

    # 5. Decompress input pack into fresh 'pack' folder
    status_message("process", "Decompressing input pack...")
    extract_dir = "pack"
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(input_pack, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
            
    status_message("completion", "Input pack decompressed")

    # 5. Check pack.mcmeta
    if not os.path.isfile(os.path.join(extract_dir, "pack.mcmeta")):
        status_message("error", "Invalid resource pack! The pack.mcmeta file does not exist.")
        sys.exit(1)

    # Note: Kaizer config logic has been deliberately bypassed as requested by user.
    # We will assume mapping V1 and animations enabled for everything.
    
    # 6. Generate manifest.json
    os.makedirs("./target/rp", exist_ok=True)
    manifest = {
        "format_version": 2,
        "header": {
            "description": "Adds 3D items for use with a Geyser proxy",
            "name": "Geyser 3D Resource Pack",
            "uuid": str(uuid.uuid4()),
            "version": [1, 0, 0],
            "min_engine_version": [1, 18, 3]
        },
        "modules": [{
            "description": "Adds 3D items for use with a Geyser proxy",
            "type": "resources",
            "uuid": str(uuid.uuid4()),
            "version": [1, 0, 0]
        }]
    }
    with open("./target/rp/manifest.json", "w") as f:
        json.dump(manifest, f, separators=(',', ':'))
    status_message("completion", "manifest.json generated")
    
    # 7. Generate disable animation
    disable_anim = {
        "format_version": "1.8.0",
        "animations": {
            "animation.geyser_custom.disable": {
                "loop": True,
                "override_previous_animation": True,
                "bones": {
                    "geyser_custom": {"scale": 0}
                }
            }
        }
    }
    os.makedirs("./target/rp/animations", exist_ok=True)
    with open("./target/rp/animations/animation.geyser_custom.disable.json", "w") as f:
        json.dump(disable_anim, f, separators=(',', ':'))
    
    # 8. Check for old vs new items
    old_format_dir = "./pack/assets/minecraft/models/item"
    new_format_dir = "./pack/assets/minecraft/items"
    has_items = False
    
    if os.path.isdir(old_format_dir) or os.path.isdir(new_format_dir):
        if os.path.isdir(old_format_dir):
            status_message("completion", "Minecraft namespace item folder found (OLD format: models/item).")
        if os.path.isdir(new_format_dir):
            status_message("completion", "Minecraft namespace items folder found (NEW format 1.21.4+: items).")
        has_items = True

import urllib.request
import glob
import math

def download_scratch_files():
    os.makedirs("scratch_files", exist_ok=True)
    status_message("process", "Downloading Geyser item mappings...")
    try:
        urllib.request.urlretrieve("https://raw.githubusercontent.com/GeyserMC/mappings/master/items.json", "scratch_files/item_mappings.json")
        urllib.request.urlretrieve("https://raw.githubusercontent.com/Kas-tle/java2bedrockMappings/main/item_texture.json", "scratch_files/item_texture.json")
    except Exception as e:
        status_message("error", f"Failed to download mapping files: {e}")
        sys.exit(1)

def find_asset(rel_path):
    """Helper to find asset in custom pack or vanilla cache."""
    if rel_path.startswith("./"): rel_path = rel_path[2:]
    if rel_path.startswith("pack/"): rel_path = rel_path[5:]
    
    p1 = os.path.join("pack", rel_path)
    if os.path.exists(p1): return p1
    p2 = os.path.join("vanilla_cache", rel_path)
    if os.path.exists(p2): return p2
    return p1

def filter_unwanted_folders():
    status_message("process", "Filtering out unwanted asset folders...")
    unwanted = ["./pack/assets/betterhud", "./pack/assets/nameplates", "./pack/assets/modelengine"]
    for uw in unwanted:
        if os.path.exists(uw):
            # shutil.rmtree(uw, ignore_errors=True)
            status_message("info", f"Matched directory (not deleted): {uw}")


def parse_old_format(mappings, texture_maps, filter_items=None):
    status_message("process", "Processing OLD format (models/item)...")
    config_entries = {}
    geyser_id_counter = 1
    
    files = glob.glob("./pack/assets/*/models/item/*.json")
    for filepath in files:
        f_parts = os.path.normpath(filepath).split(os.sep)
        try:
            assets_idx = f_parts.index("assets")
            ns_item = f_parts[assets_idx + 1]
        except:
            continue
        item_base = os.path.basename(filepath).replace(".json", "")
        item_name = f"{ns_item}:{item_base}"

        # Filter check
        if filter_items is not None:
            if item_base not in filter_items and item_name not in filter_items:
                continue


        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            continue
            
        overrides = data.get("overrides", [])
        if not overrides:
            continue
            
        # Get Max Damage
        max_damage = 1
        item_map = mappings.get(item_name, {})
        if not item_map and ns_item == "minecraft":
            item_map = mappings.get(f"minecraft:{item_base}", {})
        
        if "max_damage" in item_map:
            max_damage = item_map["max_damage"]


        # Get Bedrock Icon
        bedrock_icon = texture_maps.get(item_name, {"icon": "camera", "frame": 0})
        
        for override in overrides:
            pred = override.get("predicate", {})
            if "damage" not in pred and "damaged" not in pred and "custom_model_data" not in pred:
                continue
                
            damage_val = math.ceil(pred["damage"] * max_damage) if "damage" in pred else None
            unbreakable_val = True if pred.get("damaged") == 0 else None
            cmd_val = pred.get("custom_model_data")

            model_ref = override.get("model", "")
            if not model_ref: continue

            if ":" in model_ref:
                ns, mdl = model_ref.split(":")
            else:
                ns, mdl = "minecraft", model_ref
                
            model_path_rel = f"assets/{ns}/models/{mdl}.json"
            model_path_full = find_asset(model_path_rel)
            model_name = mdl.split("/")[-1]
            model_path_dir = "/".join(mdl.split("/")[:-1])
            
            entry = {
                "item": item_name,
                "bedrock_icon": bedrock_icon,
                "nbt": {},
                "path": model_path_full,
                "namespace": ns,
                "model_path": model_path_dir,
                "model_name": model_name,
                "generated": False,
                "geyserID": f"gmdl_{geyser_id_counter}"
            }
            if damage_val is not None: entry["nbt"]["Damage"] = damage_val
            if unbreakable_val is not None: entry["nbt"]["Unbreakable"] = unbreakable_val
            if cmd_val is not None: entry["nbt"]["CustomModelData"] = cmd_val
            
            config_entries[entry["geyserID"]] = entry
            geyser_id_counter += 1
            
    return config_entries, geyser_id_counter

def extract_model_from_new_format(node):
    if isinstance(node, str):
        return node
    elif isinstance(node, dict):
        typ = node.get("type", "").replace("minecraft:", "")
        if typ == "model" and isinstance(node.get("model"), str):
            return node["model"]
        elif typ == "condition":
            return extract_model_from_new_format(node.get("on_false", node.get("on_true", {})))
        elif typ == "select":
            cases = node.get("cases", [])
            fb = node.get("fallback")
            if fb: return extract_model_from_new_format(fb)
            if cases: return extract_model_from_new_format(cases[0].get("model", {}))
        elif typ == "range_dispatch":
            entries = node.get("entries", [])
            fb = node.get("fallback")
            if fb: return extract_model_from_new_format(fb)
            if entries: return extract_model_from_new_format(entries[0].get("model", {}))
        elif typ == "composite":
            models = node.get("models", [])
            if models: return extract_model_from_new_format(models[0])
    return None

def parse_new_format(geyser_id_counter, filter_items=None):
    status_message("process", "Processing NEW format (items/)...")
    config_entries = {}
    
    files = glob.glob("./pack/assets/*/items/*.json")
    for filepath in files:
        f_parts = os.path.normpath(filepath).split(os.sep)
        try:
            assets_idx = f_parts.index("assets")
            ns_item = f_parts[assets_idx + 1]
        except:
            continue
        item_base = os.path.basename(filepath).replace(".json", "")
        item_name = f"{ns_item}:{item_base}"

        # Filter check
        if filter_items is not None:
            if item_base not in filter_items and item_name not in filter_items:
                continue


        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            continue
            
        model_node = data.get("model", {})
        typ = model_node.get("type", "").replace("minecraft:", "")
        prop = model_node.get("property", "").replace("minecraft:", "")
        
        if typ == "range_dispatch" and prop == "custom_model_data":
            entries = model_node.get("entries", [])
            for entry in entries:
                cmd = int(entry.get("threshold", 0))
                m_ref = extract_model_from_new_format(entry.get("model", {}))
                
                if m_ref and m_ref.strip():
                    if ":" in m_ref:
                        ns, mdl = m_ref.split(":")
                    else:
                        ns, mdl = "minecraft", m_ref
                        
                    model_path_rel = f"assets/{ns}/models/{mdl}.json"
                    model_path_full = find_asset(model_path_rel)
                    model_name = mdl.split("/")[-1]
                    model_path_dir = "/".join(mdl.split("/")[:-1])
                    
                    entry_dict = {
                        "item": item_name,
                        "nbt": {"CustomModelData": cmd},
                        "path": model_path_full,
                        "namespace": ns,
                        "model_path": model_path_dir,
                        "model_name": model_name,
                        "generated": False,
                        "geyserID": f"gmdl_new_{geyser_id_counter}"
                    }
                    config_entries[entry_dict["geyserID"]] = entry_dict
                    geyser_id_counter += 1
                    
    return config_entries, geyser_id_counter

import hashlib
import subprocess

def hash_string(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:7]

def resolve_parental(config):
    status_message("process", "Validating file existence and resolving parent models...")
    
    # Filter non-existent files
    valid_config = {}
    for gid, entry in config.items():
        if os.path.exists(entry["path"]):
            valid_config[gid] = entry
            
    # Add hashes
    for gid, entry in valid_config.items():
        pred_str = f"{entry['item']}_c{entry['nbt'].get('CustomModelData', 'None')}_d{entry['nbt'].get('Damage', 'None')}_u{entry['nbt'].get('Unbreakable', 'None')}"
        entry["entry_hash"] = hash_string(pred_str)
        entry["path_hash"] = hash_string(entry["path"])
        entry["geometry"] = f"geo_{entry['entry_hash']}"
        entry["bedrock_path_hash"] = f"gmdl_{entry['path_hash']}"
        
    status_message("info", f"DEBUG: {len(valid_config)} entries remain after file validation.")
    
    # Resolve Parents
    for gid, entry in valid_config.items():
        if entry["generated"]: continue
            
        current_path = entry["path"]
        elements, textures, display = None, None, None
        is_generated_parent = False
        
        # Known "generated" parent patterns
        generated_patterns = [
            "./pack/assets/minecraft/models/builtin/generated.json",
            "./pack/assets/minecraft/models/item/generated.json",
            "./pack/assets/minecraft/models/block/generated.json",
        ]
        
        while current_path and (not elements or not textures or not display):
            if current_path in generated_patterns:
                is_generated_parent = True
                break
            
            # If parent file doesn't exist, check if it's a generated-like pattern
            if not os.path.exists(current_path):
                # Check if the missing parent contains "generated"
                if "generated" in current_path:
                    is_generated_parent = True
                break
                
            try:
                with open(current_path, 'r', encoding='utf-8') as f:
                    model_data = json.load(f)
            except:
                break
                
            if not elements and "elements" in model_data: elements = model_data["elements"]
            if not textures and "textures" in model_data: textures = model_data["textures"]
            if not display and "display" in model_data: display = model_data["display"]
            
            parent_ref = model_data.get("parent")
            if parent_ref:
                if ":" in parent_ref:
                    p_ns, p_mdl = parent_ref.split(":")
                else:
                    p_ns, p_mdl = "minecraft", parent_ref
                current_path = find_asset(f"assets/{p_ns}/models/{p_mdl}.json")
            else:
                current_path = None
                
        # Handle 2D Generated - ANY entry with textures but no elements is 2D
        # (All standard Minecraft parents like handheld/stick ultimately inherit from generated)
        if textures and not elements:
            # Resolve texture_0 path
            first_tex = list(textures.values())[0] if textures else None
            if first_tex:
                if ":" in first_tex:
                    t_ns, t_id = first_tex.split(":")
                else:
                    t_ns, t_id = "minecraft", first_tex
                texture_0_path = f"./pack/assets/{t_ns}/textures/{t_id}.png"
                if os.path.exists(texture_0_path):
                    # Copy texture to target RP (matches shell script behavior)
                    ns = entry["namespace"]
                    mp = entry["model_path"]
                    mn = entry["model_name"]
                    dest_dir = f"./target/rp/textures/{ns}/{mp}"
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(texture_0_path, f"{dest_dir}/{mn}.png")
                    
            entry["elements"] = None 
            entry["textures"] = textures
            entry["display"] = display if display else {}
            entry["is_2d"] = True
            entry["generated"] = True
        elif elements and textures:
            entry["elements"] = elements
            entry["textures"] = textures
            entry["display"] = display if display else {}
            entry["is_2d"] = False
        else:
            # Missing critical info
            entry["invalid"] = True
            
    # Remove invalidate entries
    final_config = {k: v for k, v in valid_config.items() if not v.get("invalid")}
    return final_config

# Isometric block icon generation removed per user request

import re
from PIL import Image as PILImage

def generate_spritesheet(image_paths, output_name):
    """Pure-Python spritesheet generator using Pillow (replaces spritesheet-js)."""
    images = []
    for p in sorted(image_paths):
        try:
            img = PILImage.open(p).convert("RGBA")
            images.append((p, img))
        except Exception:
            continue
    
    if not images:
        return
    
    # Simple row-packing: place images side-by-side, all same height
    max_h = max(img.size[1] for _, img in images)
    total_w = sum(img.size[0] for _, img in images)
    
    atlas = PILImage.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
    frames = {}
    x_offset = 0
    
    for path, img in images:
        atlas.paste(img, (x_offset, 0))
        frames[path] = {
            "frame": {"x": x_offset, "y": 0, "w": img.size[0], "h": img.size[1]}
        }
        x_offset += img.size[0]
    
    atlas.save(f"{output_name}.png", "PNG")
    atlas_json = {
        "frames": frames,
        "meta": {
            "size": {"w": total_w, "h": max_h}
        }
    }
    with open(f"{output_name}.json", "w") as f:
        json.dump(atlas_json, f)

def build_atlases(config):
    status_message("process", "Generating texture list for atlas...")
    os.makedirs("scratch_files/spritesheet", exist_ok=True)
    
    # Step 1: Collect ALL existing textures from custom pack AND vanilla cache
    all_pack_textures = set()
    for base_dir in ["pack", "vanilla_cache"]:
        if not os.path.exists(base_dir): continue
        for root, dirs, files in os.walk(os.path.join(base_dir, "assets")):
            for fname in files:
                if fname.endswith('.png'):
                    full = os.path.join(root, fname).replace("\\", "/")
                    if '/textures/' in full:
                        all_pack_textures.add(full)
    
    # Step 2: Extract texture sets from ALL models (including generated)
    # This matches the shell script: jq -s '[.[] | (.textures // {}) | [.[]?] | unique]'
    per_model_textures = []  # list of lists of texture paths
    
    for gid, entry in config.items():
        if entry["generated"]: continue  # Only 3D models have atlas textures
        
        tex_dict = entry.get("textures", {})
        model_textures = []
        for v in tex_dict.values():
            if ":" in v:
                ns, tid = v.split(":")
            else:
                ns, tid = "minecraft", v
            t_path = find_asset(f"assets/{ns}/textures/{tid.replace('#', '')}.png")
            model_textures.append(t_path)
        
        if model_textures:
            per_model_textures.append(list(set(model_textures)))
    
    # Step 3: mapatlas union-merge algorithm (matches shell's jq mapatlas function)
    # Start with a seed atlas containing just the fallback texture
    unique_texture_sets = [[find_asset("assets/minecraft/textures/0.png")]]
    
    for tex_set in per_model_textures:
        unique_set = list(set(tex_set))
        
        # Find all existing atlas sets that intersect with this model's textures
        matching_indices = []
        for idx, u_set in enumerate(unique_texture_sets):
            if any(t in u_set for t in unique_set):
                matching_indices.append(idx)
        
        if matching_indices:
            # Merge all matching sets + new textures into one set
            merged = set(unique_set)
            for idx in matching_indices:
                merged.update(unique_texture_sets[idx])
            
            # Remove the old matching sets (reverse order to keep indices valid)
            for idx in sorted(matching_indices, reverse=True):
                unique_texture_sets.pop(idx)
            
            # Add the merged set
            unique_texture_sets.append(list(merged))
        else:
            # New atlas group
            unique_texture_sets.append(unique_set)
    
    # Make all sets contain unique paths
    unique_texture_sets = [list(set(s)) for s in unique_texture_sets]
    
    total_atlases = len(unique_texture_sets)
    status_message("process", f"Generating {total_atlases} sprite sheets using Pillow...")
    
    # Step 4: For each atlas, intersect with existing pack textures + fallback
    # Matches shell: (.[1][idx] - (.[1][idx] - .[0])) + fallback
    for idx, u_set in enumerate(unique_texture_sets):
        status_message("process", f"Generating sprite sheet {idx} of {total_atlases-1}")
        
        # Intersect atlas textures with actual pack textures
        existing = [t for t in u_set if t in all_pack_textures]
        
        # If any texture in atlas is missing, add fallback 0.png
        if len(existing) < len(u_set):
            fallback = find_asset("assets/minecraft/textures/0.png")
            if fallback not in existing and os.path.exists(fallback):
                existing.append(fallback)
        
        if not existing:
            # Create a placeholder if completely empty
            fallback = find_asset("assets/minecraft/textures/0.png")
            if os.path.exists(fallback):
                existing = [fallback]
        
        generate_spritesheet(existing, f"scratch_files/spritesheet/{idx}")
    
    # Step 5: Assign atlas_index to each non-generated entry
    for gid, entry in config.items():
        if entry["generated"]:
            entry["atlas_index"] = 0
            continue
            
        tex_dict = entry.get("textures", {})
        model_textures = set()
        for v in tex_dict.values():
            if ":" in v:
                ns, tid = v.split(":")
            else:
                ns, tid = "minecraft", v
            t_path = find_asset(f"assets/{ns}/textures/{tid.replace('#', '')}.png")
            model_textures.add(t_path)
        
        # Find which atlas this model belongs to
        found = False
        for idx, u_set in enumerate(unique_texture_sets):
            if any(t in u_set for t in model_textures):
                entry["atlas_index"] = idx
                found = True
                break
        
        if not found:
            entry["atlas_index"] = 0
        
    return unique_texture_sets

def roundit(val):
    return round(val * 10000) / 10000

def geom_element_array(elements, textures, atlas_meta, atlas_frames):
    bedrock_elements = []
    
    def get_texture_path(tex_var):
        if tex_var.startswith("#"): tex_var = tex_var[1:]
        tex_ref = textures.get(tex_var, list(textures.values())[0] if textures else "")
        if ":" in tex_ref:
            ns, tid = tex_ref.split(":")
        else:
            ns, tid = "minecraft", tex_ref
        return find_asset(f"assets/{ns}/textures/{tid}.png")
        
    def get_frame(tex_path):
        t_frame = atlas_frames.get(tex_path, {}).get("frame", {"x": 0, "y": 0, "w": 16, "h": 16})
        
        # Calculate scaling relative to the atlas.
        # CRITICAL: Use t_frame["w"] for both width and height scaling!
        # This matches the shell script and properly crops vertical animated strips
        # to their first square frame, preventing them from being squished.
        scale_w = t_frame["w"] / 16.0
        scale_h = t_frame["w"] / 16.0
        
        tx = t_frame["x"]
        ty = t_frame["y"]
        return t_frame, scale_w, scale_h, tx, ty
        
    for el in elements:
        o = el.get("origin", [0,0,0])
        f_val = el.get("from", [0,0,0])
        t_val = el.get("to", [0,0,0])
        rot = el.get("rotation", {})
        
        origin = [roundit(-t_val[0] + 8), roundit(f_val[1]), roundit(f_val[2] - 8)]
        size = [roundit(t_val[0] - f_val[0]), roundit(t_val[1] - f_val[1]), roundit(t_val[2] - f_val[2])]
        
        rotation = None
        if rot:
            axis = rot.get("axis")
            ang = float(rot.get("angle", 0))
            if axis == "x": rotation = [-ang, 0, 0]
            elif axis == "y": rotation = [0, -ang, 0]
            elif axis == "z": rotation = [0, 0, ang]
            
        pivot = None
        if rot and "origin" in rot:
            r_or = rot["origin"]
            pivot = [roundit(-r_or[0] + 8), roundit(r_or[1]), roundit(r_or[2] - 8)]
            
        faces = el.get("faces", {})
        bedrock_uv = {}
        
        a_w, a_h = atlas_meta.get("size", {}).get("w", 16), atlas_meta.get("size", {}).get("h", 16)
        
        for face_name in ["north", "south", "east", "west", "up", "down"]:
            if face_name in faces:
                face = faces[face_name]
                tex_path = get_texture_path(face.get("texture", ""))
                frame, _, _, _, _ = get_frame(tex_path)
                uv = face.get("uv", [0,0,16,16])
                
                fn0 = (((uv[0] * frame["w"] * 0.0625) + frame["x"]) * (16.0 / a_w))
                fn1 = (((uv[1] * frame["w"] * 0.0625) + frame["y"]) * (16.0 / a_h))
                fn2 = (((uv[2] * frame["w"] * 0.0625) + frame["x"]) * (16.0 / a_w))
                fn3 = (((uv[3] * frame["w"] * 0.0625) + frame["y"]) * (16.0 / a_h))
                
                x_sign = min(max(-1, fn2 - fn0), 1)
                y_sign = min(max(-1, fn3 - fn1), 1)
                
                if face_name in ["up", "down"]:
                    bedrock_uv[face_name] = {
                        "uv": [roundit(fn2 - (0.016 * x_sign)), roundit(fn3 - (0.016 * y_sign))],
                        "uv_size": [roundit((fn0 - fn2) + (0.016 * x_sign)), roundit((fn1 - fn3) + (0.016 * y_sign))]
                    }
                else:
                    bedrock_uv[face_name] = {
                        "uv": [roundit(fn0 + (0.016 * x_sign)), roundit(fn1 + (0.016 * y_sign))],
                        "uv_size": [roundit((fn2 - fn0) - (0.016 * x_sign)), roundit((fn3 - fn1) - (0.016 * y_sign))]
                    }
                    
        bedrock_el = {"origin": origin, "size": size, "uv": bedrock_uv}
        if rotation: bedrock_el["rotation"] = rotation
        if pivot: bedrock_el["pivot"] = pivot
        
        bedrock_elements.append(bedrock_el)
        
    return bedrock_elements

def get_pivot_groups(bedrock_elements):
    groups = []
    unique_rot_pivots = []
    for el in bedrock_elements:
        if "rotation" in el and "pivot" in el:
            rp = (tuple(el["rotation"]), tuple(el["pivot"]))
            if rp not in unique_rot_pivots:
                unique_rot_pivots.append(rp)
                
    for idx, (rot, piv) in enumerate(unique_rot_pivots):
        cubes = [el for el in bedrock_elements if el.get("rotation") == list(rot) and el.get("pivot") == list(piv)]
        # remove rot/pivot from element as it belongs to the parent bone
        for c in cubes:
            c.pop("rotation", None)
            
        groups.append({
            "name": f"rot_{idx+1}",
            "parent": "geyser_custom_z",
            "pivot": list(piv),
            "rotation": list(rot),
            "cubes": cubes
        })
    return groups

def convert_models_and_animations(config, args):
    status_message("process", "Compiling models, animations, and attachables natively...")
    
    for gid, entry in config.items():
            
        atlas_idx = entry.get("atlas_index", 0)
        
        if not entry["generated"]:
            try:
                with open(f"scratch_files/spritesheet/{atlas_idx}.json", "r") as f:
                    atlas_data = json.load(f)
                    atlas_meta = atlas_data.get("meta", {})
                    atlas_frames = atlas_data.get("frames", {})
            except:
                atlas_meta, atlas_frames = {}, {}
                
            bedrock_elements = geom_element_array(entry["elements"], entry["textures"], atlas_meta, atlas_frames)
        else:
            bedrock_elements = []
        
        # Bedrock Geometry
        binding = "c.item_slot == 'head' ? 'head' : q.item_slot_to_bone_name(c.item_slot)"
        geometry_bones = [
            {"name": "geyser_custom", "binding": binding, "pivot": [0, 8, 0]},
            {"name": "geyser_custom_x", "parent": "geyser_custom", "pivot": [0, 8, 0]},
            {"name": "geyser_custom_y", "parent": "geyser_custom_x", "pivot": [0, 8, 0]},
        ]
        
        if entry["is_2d"]:
             geometry_bones.append({
                "name": "geyser_custom_z",
                "parent": "geyser_custom_y",
                "pivot": [0, 8, 0],
                "texture_meshes": [{"texture": "default", "position": [0, 8, 0], "rotation": [90, 0, -180], "local_pivot": [8, 0.5, 8]}]
            })
        else:
            base_cubes = [c for c in bedrock_elements if "rotation" not in c]
            geometry_bones.append({
                "name": "geyser_custom_z",
                "parent": "geyser_custom_y",
                "pivot": [0, 8, 0],
                "cubes": base_cubes
            })
            
            p_groups = get_pivot_groups(bedrock_elements)
            geometry_bones.extend(p_groups)
            
        geom = {
            "format_version": "1.21.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": "geometry.geyser_custom." + entry["geometry"],
                    "texture_width": 16,
                    "texture_height": 16,
                    "visible_bounds_width": 4,
                    "visible_bounds_height": 4.5,
                    "visible_bounds_offset": [0, 0.75, 0]
                },
                "bones": geometry_bones
            }]
        }
        
        ns, mpath, mname = entry["namespace"], entry["model_path"], entry["model_name"]
        os.makedirs(f"./target/rp/models/blocks/{ns}/{mpath}", exist_ok=True)
        with open(f"./target/rp/models/blocks/{ns}/{mpath}/{mname}.json", "w") as f:
            json.dump(geom, f, separators=(',', ':'))

        # Animations
        os.makedirs(f"./target/rp/animations/{ns}/{mpath}", exist_ok=True)
        display = entry["display"]
        
        def safe_get(dGroup, key, def_val=None):
            if dGroup in display and key in display[dGroup]:
                return display[dGroup][key]
            return def_val
            
        mname_lower = mname.lower()
        is_wing = any(k in mname_lower for k in ["wing", "back", "backpack"])
        
        anim_json = {
            "format_version": "1.8.0",
            "animations": {
                f"animation.geyser_custom.{entry['geometry']}.thirdperson_main_hand": {
                    "loop": True,
                    "bones": {
                        "geyser_custom_x": {
                            "rotation": [-safe_get("thirdperson_righthand", "rotation", [0,0,0])[0], 0, 0] if "thirdperson_righthand" in display and "rotation" in display["thirdperson_righthand"] else None,
                            "position": [-safe_get("thirdperson_righthand", "translation", [0,0,0])[0], safe_get("thirdperson_righthand", "translation", [0,0,0])[1], safe_get("thirdperson_righthand", "translation", [0,0,0])[2]] if "thirdperson_righthand" in display and "translation" in display["thirdperson_righthand"] else None,
                            "scale": safe_get("thirdperson_righthand", "scale")
                        } if "thirdperson_righthand" in display else None,
                        "geyser_custom_y": {"rotation": [0, -safe_get("thirdperson_righthand", "rotation", [0,0,0])[1], 0]} if "thirdperson_righthand" in display and "rotation" in display["thirdperson_righthand"] else None,
                        "geyser_custom_z": {"rotation": [0, 0, safe_get("thirdperson_righthand", "rotation", [0,0,0])[2]]} if "thirdperson_righthand" in display and "rotation" in display["thirdperson_righthand"] else None,
                        "geyser_custom": {
                            "rotation": [90, 0, 0],
                            "position": [0, 13, -3]
                        }
                    }
                },
                f"animation.geyser_custom.{entry['geometry']}.thirdperson_off_hand": {
                    "loop": True,
                    "bones": {
                        "geyser_custom_x": {
                            "rotation": [-safe_get("thirdperson_lefthand", "rotation", [0,0,0])[0], 0, 0] if "thirdperson_lefthand" in display and "rotation" in display["thirdperson_lefthand"] else None,
                            "position": [safe_get("thirdperson_lefthand", "translation", [0,0,0])[0], safe_get("thirdperson_lefthand", "translation", [0,0,0])[1], safe_get("thirdperson_lefthand", "translation", [0,0,0])[2]] if "thirdperson_lefthand" in display and "translation" in display["thirdperson_lefthand"] else None,
                            "scale": safe_get("thirdperson_lefthand", "scale")
                        } if "thirdperson_lefthand" in display else None,
                        "geyser_custom_y": {"rotation": [0, -safe_get("thirdperson_lefthand", "rotation", [0,0,0])[1], 0]} if "thirdperson_lefthand" in display and "rotation" in display["thirdperson_lefthand"] else None,
                        "geyser_custom_z": {"rotation": [0, 0, safe_get("thirdperson_lefthand", "rotation", [0,0,0])[2]]} if "thirdperson_lefthand" in display and "rotation" in display["thirdperson_lefthand"] else None,
                        "geyser_custom": {
                            "rotation": [90, 0, 0],
                            "position": [0, 13, -3]
                        }
                    }
                },
                f"animation.geyser_custom.{entry['geometry']}.head": {
                    "loop": True,
                    "bones": {
                        "geyser_custom_x": {
                            "rotation": [-safe_get("head", "rotation", [0,0,0])[0], 0, 0] if "head" in display and "rotation" in display["head"] else None,
                            "position": [-safe_get("head", "translation", [0,0,0])[0] * 0.625, safe_get("head", "translation", [0,0,0])[1] * 0.625, safe_get("head", "translation", [0,0,0])[2] * 0.625] if "head" in display and "translation" in display["head"] else None,
                            "scale": [v * 0.625 for v in safe_get("head", "scale", [1,1,1])] if "head" in display and "scale" in display["head"] else 0.625
                        },
                        "geyser_custom_y": {"rotation": [0, -safe_get("head", "rotation", [0,0,0])[1], 0]} if "head" in display and "rotation" in display["head"] else None,
                        "geyser_custom_z": {"rotation": [0, 0, safe_get("head", "rotation", [0,0,0])[2]]} if "head" in display and "rotation" in display["head"] else None,
                        "geyser_custom": {
                            "position": [0, 19.9, 0]
                        }
                    }
                },
                f"animation.geyser_custom.{entry['geometry']}.firstperson_main_hand": {
                    "loop": True,
                    "bones": {
                        "geyser_custom": {
                            "rotation": [90, 60, -40],
                            "position": [4, 10, 4],
                            "scale": 1.5
                        },
                        "geyser_custom_x": {
                            "position": [-safe_get("firstperson_righthand", "translation", [0,0,0])[0], safe_get("firstperson_righthand", "translation", [0,0,0])[1], -safe_get("firstperson_righthand", "translation", [0,0,0])[2]] if not is_wing and "translation" in display.get("firstperson_righthand", {}) else ([-1.5, 3.25, 0.5] if not is_wing else None),
                            "rotation": [-safe_get("firstperson_righthand", "rotation", [0,0,0])[0], 0, 0] if not is_wing and "rotation" in display.get("firstperson_righthand", {}) else ([-9, 0, 0] if not is_wing else None),
                            "scale": safe_get("firstperson_righthand", "scale") if not is_wing else None
                        },
                        "geyser_custom_y": {"rotation": [0, -safe_get("firstperson_righthand", "rotation", [0,0,0])[1], 0]} if "firstperson_righthand" in display and "rotation" in display["firstperson_righthand"] else None,
                        "geyser_custom_z": {"rotation": [0, 0, safe_get("firstperson_righthand", "rotation", [0,0,0])[2]]} if "firstperson_righthand" in display and "rotation" in display["firstperson_righthand"] else None
                    }
                },
                f"animation.geyser_custom.{entry['geometry']}.firstperson_off_hand": {
                    "loop": True,
                    "bones": {
                        "geyser_custom": {
                            "rotation": [90, 60, -40] if is_wing else [0, 180, 0],
                            "position": [4, 10, 4] if is_wing else [-16, 14, 14],
                            "scale": 1.5 if is_wing else 1.1
                        },
                        "geyser_custom_x": {
                            "position": [safe_get("firstperson_lefthand", "translation", [0,0,0])[0], safe_get("firstperson_lefthand", "translation", [0,0,0])[1], -safe_get("firstperson_lefthand", "translation", [0,0,0])[2]] if not is_wing and "translation" in display.get("firstperson_lefthand", {}) else ([5.5, 10.0, -3.75] if not is_wing else None),
                            "rotation": [-safe_get("firstperson_lefthand", "rotation", [0,0,0])[0], 0, 0] if not is_wing and "rotation" in display.get("firstperson_lefthand", {}) else ([9.47, 0, 0] if not is_wing else None),
                            "scale": safe_get("firstperson_lefthand", "scale") if not is_wing else None
                        },
                        "geyser_custom_y": {"rotation": [0, -safe_get("firstperson_lefthand", "rotation", [0,0,0])[1], 0]} if "firstperson_lefthand" in display and "rotation" in display["firstperson_lefthand"] else None,
                        "geyser_custom_z": {"rotation": [0, 0, safe_get("firstperson_lefthand", "rotation", [0,0,0])[2]]} if "firstperson_lefthand" in display and "rotation" in display["firstperson_lefthand"] else None
                    }
                }
            }
        }
        
        # Clean null values
        def clean_nulls(d):
            if isinstance(d, dict): return {k: clean_nulls(v) for k, v in d.items() if v is not None}
            if isinstance(d, list): return [clean_nulls(v) for v in d if v is not None]
            return d
        anim_json = clean_nulls(anim_json)
        
        with open(f"./target/rp/animations/{ns}/{mpath}/animation.{mname}.json", "w") as f:
            json.dump(anim_json, f, separators=(',', ':'))

        # Attachable
        os.makedirs(f"./target/rp/attachables/{ns}/{mpath}", exist_ok=True)
        attachable = {
            "format_version": "1.10.0",
            "minecraft:attachable": {
                "description": {
                    "identifier": f"geyser_custom:{entry['path_hash']}",
                    "materials": {"default": "entity_alphatest_one_sided", "enchanted": "entity_alphatest_one_sided"},
                    "textures": {
                        "default": f"textures/{ns}/{mpath}/{mname}" if entry["is_2d"] else f"atlas_{atlas_idx}",
                        "enchanted": "textures/misc/enchanted_item_glint"
                    },

                    "geometry": {"default": f"geometry.geyser_custom.{entry['geometry']}"},
                    "scripts": {
                        "pre_animation": ["v.main_hand = c.item_slot == 'main_hand';", "v.off_hand = c.item_slot == 'off_hand';", "v.head = c.item_slot == 'head';"],
                        "animate": [
                            {"thirdperson_main_hand": "v.main_hand && !c.is_first_person"},
                            {"thirdperson_off_hand": "v.off_hand && !c.is_first_person"},
                            {"thirdperson_head": "v.head && !c.is_first_person"},
                            {"firstperson_main_hand": "v.main_hand && c.is_first_person"},
                            {"firstperson_off_hand": "v.off_hand && c.is_first_person"},
                            {"firstperson_head": "c.is_first_person && v.head"}
                        ]
                    },
                    "animations": {
                        "thirdperson_main_hand": f"animation.geyser_custom.{entry['geometry']}.thirdperson_main_hand",
                        "thirdperson_off_hand": f"animation.geyser_custom.{entry['geometry']}.thirdperson_off_hand",
                        "thirdperson_head": f"animation.geyser_custom.{entry['geometry']}.head",
                        "firstperson_main_hand": f"animation.geyser_custom.{entry['geometry']}.firstperson_main_hand",
                        "firstperson_off_hand": f"animation.geyser_custom.{entry['geometry']}.firstperson_off_hand",
                        "firstperson_head": "animation.geyser_custom.disable"
                    },
                    "render_controllers": ["controller.render.item_default"]
                }
            }
        }
        with open(f"./target/rp/attachables/{ns}/{mpath}/{mname}.{entry['path_hash']}.attachable.json", "w") as f:
            json.dump(attachable, f, separators=(',', ':'))

import zipfile
import os
import json
import re
import glob
import shutil
import subprocess

def finalize_pack(config, args):
    status_message("process", "Writing en_US and en_GB lang files")
    os.makedirs("./target/rp/texts", exist_ok=True)
    lang_content = []
    
    for gid, entry in config.items():
        # Format name from snake_case
        raw_name = entry["item"]
        formatted_name = " ".join([word.capitalize() for word in raw_name.split("_")])
        lang_content.append(f"item.geyser_custom:{entry['path_hash']}.name={formatted_name}")
        
    lang_text = "\n".join(lang_content)
    with open("./target/rp/texts/en_US.lang", "w") as f: f.write(lang_text)
    with open("./target/rp/texts/en_GB.lang", "w") as f: f.write(lang_text)
    with open("./target/rp/texts/languages.json", "w") as f: json.dump(["en_US", "en_GB"], f)
    
    status_message("process", "Setting all images to RGBA (png32) using Pillow")
    for r, d, files_list in os.walk("./target/rp/textures"):
        for file in files_list:
            if file.endswith('.png'):
                fp = os.path.join(r, file)
                try:
                    img = PILImage.open(fp).convert("RGBA")
                    img.save(fp, "PNG")
                except Exception:
                    pass
                
    # Geyser Mappings (V1 or V2 based on user setting)
    mapping_ver = args.mapping_version
    status_message("process", f"Creating Geyser mappings in target directory ({mapping_ver.upper()})")
    
    if mapping_ver == "v2":
        # V2 Format: array with type/bedrock_identifier/display_name/bedrock_options
        mappings = {"format_version": 2, "items": {}}
        
        for gid, entry in config.items():
            m_item = f"minecraft:{entry['item']}"
            if m_item not in mappings["items"]:
                mappings["items"][m_item] = []
            
            # Build display name from model_name (snake_case -> Title Case)
            raw_name = entry["model_name"]
            display_name = " ".join([word.capitalize() for word in raw_name.split("_")])
                
            mapping_entry = {
                "type": "legacy",
                "bedrock_identifier": f"geyser_custom:{entry['path_hash']}",
                "display_name": display_name,
                "bedrock_options": {
                    "icon": entry["path_hash"],
                    "allow_offhand": True
                }
            }
            
            nbt = entry.get("nbt", {})
            cmd = nbt.get("CustomModelData")
            dmg = nbt.get("Damage")
            unb = nbt.get("Unbreakable")
            if cmd is not None: mapping_entry["custom_model_data"] = cmd
            if dmg is not None: mapping_entry["damage_predicate"] = dmg
            if unb is not None: mapping_entry["unbreakable"] = unb
            
            # Deduplicate
            is_dup = False
            for existing in mappings["items"][m_item]:
                if existing.get("custom_model_data") == cmd and \
                   existing.get("damage_predicate") == dmg and \
                   existing.get("unbreakable") == unb:
                    is_dup = True
                    break
            if not is_dup:
                mappings["items"][m_item].append(mapping_entry)

    else:
        # V1 Format: array structure (default)
        mappings = {"format_version": "1", "items": {}}
        
        for gid, entry in config.items():
            m_item = f"minecraft:{entry['item']}"
            if m_item not in mappings["items"]:
                mappings["items"][m_item] = []
                
            mapping_entry = {
                "name": entry["path_hash"],
                "allow_offhand": True,
                "icon": entry["path_hash"]
            }
            
            if "frame" in entry.get("bedrock_icon", {}):
                mapping_entry["frame"] = entry["bedrock_icon"]["frame"]
                
            nbt = entry.get("nbt", {})
            cmd = nbt.get("CustomModelData")
            dmg = nbt.get("Damage")
            unb = nbt.get("Unbreakable")
            if cmd is not None: mapping_entry["custom_model_data"] = cmd
            if dmg is not None: mapping_entry["damage_predicate"] = dmg
            if unb is not None: mapping_entry["unbreakable"] = unb
            
            # Deduplicate
            is_dup = False
            for existing in mappings["items"][m_item]:
                if existing.get("custom_model_data") == cmd and \
                   existing.get("damage_predicate") == dmg and \
                   existing.get("unbreakable") == unb:
                    is_dup = True
                    break
            if not is_dup:
                mappings["items"][m_item].append(mapping_entry)

        
    with open("./target/geyser_mappings.json", "w", encoding="utf-8") as f:
        json.dump(mappings, f, separators=(',', ':'))

    # Update item_texture.json with icons
    try:
        with open("./target/rp/textures/item_texture.json", "r") as f:
            items_tex = json.load(f)
    except: items_tex = {"texture_data": {}}
    
    for gid, entry in config.items():
        if entry["is_2d"]:
             bedrock_path = f"textures/{entry['namespace']}/{entry['model_path']}/{entry['model_name']}"
             bedrock_path = bedrock_path.replace("//", "/")
             items_tex["texture_data"][entry["path_hash"]] = {"textures": bedrock_path}

    
    # Add atlases to item_texture.json (Geyser prefers them here for attachables)
    for f in glob.glob("scratch_files/spritesheet/*.png"):
        bn = os.path.basename(f).replace(".png", "")
        items_tex["texture_data"][f"atlas_{bn}"] = {"textures": f"textures/{bn}"}

        
    # Copy generated atlas sheets
    status_message("process", "Moving sprite sheets to resource pack")
    for f in glob.glob("scratch_files/spritesheet/*.png"):
        shutil.copy(f, "./target/rp/textures/")
        
    # Build terrain_texture.json equivalent
    try:
         with open("./target/rp/textures/terrain_texture.json", "r") as f:
             terrain_tex = json.load(f)
    except: terrain_tex = {"texture_data": {}}
    
    for f in glob.glob("scratch_files/spritesheet/*.png"):
        bn = os.path.basename(f).replace(".png", "")
        terrain_tex["texture_data"][f"gmdl_atlas_{bn}"] = {"textures": f"textures/{bn}"}
        
    os.makedirs("./target/rp/textures", exist_ok=True)
    with open("./target/rp/textures/item_texture.json", "w") as f: json.dump(items_tex, f, separators=(',', ':'))
    with open("./target/rp/textures/terrain_texture.json", "w") as f: json.dump(terrain_tex, f, separators=(',', ':'))

    if args.merge_input and args.merge_input != "null" and os.path.isfile(args.merge_input):
        status_message("process", "Merging input bedrock pack")
        os.makedirs("inputbedrockpack", exist_ok=True)
        with zipfile.ZipFile(args.merge_input, 'r') as zip_ref:
            zip_ref.extractall("inputbedrockpack")
            
        for item in os.listdir("inputbedrockpack"):
            s = os.path.join("inputbedrockpack", item)
            d = os.path.join("./target/rp", item)
            if os.path.isdir(s): shutil.copytree(s, d, dirs_exist_ok=True)
            else: shutil.copy2(s, d)
            
        shutil.rmtree("inputbedrockpack")
        
    # Pack output
    status_message("process", "Integrating Armor and Font data via Python scripts...")
    try:
        status_message("process", "Running Armor integration...")
        import armor
    except Exception as e:
        status_message("error", f"Armor integration failed: {e}")

    try:
        status_message("process", "Running Font integration...")
        import font
    except Exception as e:
        status_message("error", f"Font integration failed: {e}")

    status_message("process", "Compressing output packs")
    os.makedirs("./target/packaged", exist_ok=True)
    os.makedirs("./target/unpackaged", exist_ok=True)
    
    with zipfile.ZipFile('./target/packaged/geyser_resources.mcpack', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('./target/rp'):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, './target/rp')
                zipf.write(abs_path, rel_path)
                
    shutil.copyfile('./target/packaged/geyser_resources.mcpack', './target/packaged/geyser_resources_preview.mcpack')
    
    shutil.move('./target/rp', './target/unpackaged/rp')

    status_message("completion", "Conversion Process Complete. Output available in target/packaged")

def main():
    parser = argparse.ArgumentParser(description="Convert Java resource pack to Bedrock.")
    parser.add_argument("input_pack", help="Input resource pack zip file")

    parser.add_argument("-m", "--merge_input", default="null", help="Input pack to merge")
    parser.add_argument("-a", "--attachable_material", default="entity_alphatest_one_sided", help="Attachable material")
    parser.add_argument("-b", "--block_material", default="alpha_test", help="Block material")
    parser.add_argument("-f", "--fallback_pack", default="null", help="Fallback pack URL")
    parser.add_argument("-da", "--default_assets", default=None, help="Path to default_assets.zip")
    parser.add_argument("--mapping_version", default="v1", choices=["v1", "v2"], help="Geyser mapping output format (v1 or v2)")
    parser.add_argument("--filter", default=None, help="Path to JSON file with list of items to convert")
    
    args = parser.parse_args()
    
    status_message("info", f"Settings: mapping={args.mapping_version}")
    
    status_message("info", "Starting Python Converter Phase 1 Setup...")
    setup_phase(args)
    
    download_scratch_files()
    filter_unwanted_folders()
    
    # Load filter if provided
    filter_items = None
    if args.filter and os.path.exists(args.filter):
        try:
            with open(args.filter, "r", encoding="utf-8") as f:
                filter_items = json.load(f)
            status_message("info", f"Filtering enabled: Only converting {len(filter_items)} items.")
        except:
            status_message("error", f"Could not load filter file: {args.filter}")
    
    # Load Mappings
    try:
        with open("scratch_files/item_mappings.json", "r", encoding="utf-8") as f:
            item_mappings = json.load(f)
    except: item_mappings = {}
    
    try:
        with open("scratch_files/item_texture.json", "r", encoding="utf-8") as f:
            texture_maps = json.load(f)
    except: texture_maps = {}

    config = {}
    g_id = 1
    
    old_fmt, g_id = parse_old_format(item_mappings, texture_maps, filter_items)
    config.update(old_fmt)
    
    new_fmt, g_id = parse_new_format(g_id, filter_items)
    config.update(new_fmt)
    
    config = resolve_parental(config)
    
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    status_message("completion", f"Phase 3 Complete: Parent resolving done. {len(config)} entries.")
    
    unique_texture_sets = build_atlases(config)
    convert_models_and_animations(config, args)
    
    finalize_pack(config, args)

def perform_cleanup():
    status_message("process", "Cleaning up intermediate files...")
    temp_paths = [
        "pack", 
        "scratch_files", 
        "config.json", 
        "target/rp", 
        "target/unpackaged",
        "rp_current_nexo",
        "rp_java_nexo"
        # "vanilla_cache" -> We KEEP this now!
    ]
    for path in temp_paths:
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except:
                pass
    status_message("info", "Intermediate files cleaned up successfully.")


if __name__ == "__main__":
    try:
        main()
    finally:
        perform_cleanup()

