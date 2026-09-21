import omni.ext
import omni.ui as ui
import omni.usd
import omni.client
import omni.kit.commands
import omni.kit.window.filepicker
import re
import os
import json
import webbrowser
import carb
import pxr
from pxr import Gf, UsdGeom, Usd, UsdLux, Sdf, UsdPhysics

print("DEBUG: ALIGNER + MEASURE LOADED - V8.11.0 (Full Scene Bridge)")
print("-" * 50)

_PREFS_FILE = os.path.join(os.path.expanduser("~"), ".nfinite_bridge_prefs.json")

def _load_prefs():
    try:
        with open(_PREFS_FILE, "r") as f: return json.load(f)
    except: return {}

def _save_prefs(data):
    try:
        with open(_PREFS_FILE, "w") as f: json.dump(data, f)
    except: pass

# Expected USD file default suffixes (uppercase = prim path under /World/)
SCENE_FILES = [
    ("STRUCTURE",   "STRUCTURE.usd"),
    ("LIGHT",       "LIGHTS.usd"),
    ("CAMERA",      "CAMERA.usd"),
    ("ASSET",       "ASSET.usd"),
]

class MyAligner(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[my.aligner] Startup V8.11.0")
        prefs = _load_prefs()
        self._scene_folder = prefs.get("scene_folder", "")
        self._checkboxes = {}  # key → ui.CheckBox
        self._folder_field = None
        self._textures_folder = prefs.get("textures_folder", "")
        self._apply_rotate_corr = prefs.get("apply_rotate_corr", False)
        self._status_label = None

        self._window = None
        self._load_btn = None

        self._window = ui.Window("Scene Bridge & Aligner", width=440, height=640)
        self._window.frame.clear()
        with self._window.frame:
            with ui.VStack(spacing=8, margin=15):

                # ── BRIDGE: SCENE IMPORT ──
                ui.Label("--- BRIDGE: SCENE IMPORT (V8.11) ---",
                         alignment=ui.Alignment.CENTER, style={"color": 0xFF44DDAA})

                # Глобальна галочка масштабування (Source of Truth)
                with ui.HStack(height=22):
                    self._cb_apply_scale = ui.CheckBox(width=20)
                    self._cb_apply_scale.model.set_value(prefs.get("apply_scale", True))
                    def on_scale_changed(model):
                        p = _load_prefs(); p["apply_scale"] = model.get_value_as_bool(); _save_prefs(p)
                        print(f"[BRIDGE] Scale setting updated to: {p['apply_scale']}")
                    self._cb_apply_scale.model.add_value_changed_fn(on_scale_changed)
                    ui.Label(" Apply mm-to-m scale (0.001)", alignment=ui.Alignment.LEFT)

                ui.Label("Scene Export Folder:", alignment=ui.Alignment.LEFT)
                with ui.HStack(height=28, spacing=5):
                    self._folder_field = ui.StringField()
                    self._folder_field.model.set_value(self._scene_folder)
                    ui.Button("...", clicked_fn=self._browse_folder, width=30)

                # Checkboxes for each file
                ui.Label("Files to load:", alignment=ui.Alignment.LEFT,
                         style={"color": 0xFF888888})
                with ui.VStack(spacing=4):
                    for key, fname in SCENE_FILES:
                        with ui.HStack(height=22, spacing=5):
                            cb = ui.CheckBox(width=20)
                            cb.model.set_value(True)
                            self._checkboxes[key] = cb
                            ui.Label(f"  {fname}", alignment=ui.Alignment.LEFT)
                            ui.Spacer()
                            ui.Button("RELOAD", width=60, height=20, 
                                      clicked_fn=lambda k=key: self.reload_single_logic(k),
                                      style={"background_color": 0xFF555555, "font_size": 10})

                    # Assets folder checkbox (feeds Auto Populate)
                    with ui.HStack(height=22):
                        self._cb_assets = ui.CheckBox(width=20)
                        self._cb_assets.model.set_value(True)
                        ui.Label("  Set Assets Folder for Auto Populate",
                                 alignment=ui.Alignment.LEFT,
                                 style={"color": 0xFF88CCFF})

                with ui.HStack(height=44, spacing=5):
                    ui.Button("LOAD ALL", clicked_fn=self.load_all_logic,
                              style={"background_color": 0xFF227733,
                                     "font_size": 15}, height=44)
                    ui.Button("RELOAD",  clicked_fn=self.reload_all_logic,
                              style={"background_color": 0xFF335577}, height=44, width=80)

                self._status_label = ui.Label("", alignment=ui.Alignment.LEFT,
                                              style={"color": 0xFF88FF88})

                ui.Label("─" * 42, alignment=ui.Alignment.CENTER,
                         style={"color": 0xFF445544})

                # ── AUTO POPULATE ──
                ui.Label("--- SMART AUTO POPULATE (V2.3) ---",
                         alignment=ui.Alignment.CENTER, style={"color": 0xFF88CCFF})
                with ui.HStack(height=28, spacing=5):
                    self._library_path = ui.StringField()
                    self._library_path.model.set_value(
                        prefs.get("assets_folder",
                                  "omniverse://localhost/Library/"))
                    ui.Button("...", clicked_fn=self._browse_library_folder, width=30)
                
                with ui.HStack(height=22):
                    self._cb_rotate_corr = ui.CheckBox(width=20)
                    self._cb_rotate_corr.model.set_value(self._apply_rotate_corr)
                    def on_rotate_corr_changed(model):
                        p = _load_prefs(); p["apply_rotate_corr"] = model.get_value_as_bool(); _save_prefs(p)
                        print(f"[BRIDGE] Rotation Correction updated to: {p['apply_rotate_corr']}")
                    self._cb_rotate_corr.model.add_value_changed_fn(on_rotate_corr_changed)
                    ui.Label(" Apply +90° Rotation Correction to assets", alignment=ui.Alignment.LEFT, style={"color": 0xFFFFAA44})

                with ui.HStack(height=45, spacing=10):
                    ui.Button("AUTO POPULATE ALL",   clicked_fn=self.auto_populate_logic)
                    ui.Button("REIMPORT ALL MODELS", clicked_fn=self.reimport_models_logic, style={"background_color": 0xFF775522})
                    ui.Button("EXPORT MISSING LIST", clicked_fn=self.export_missing_list_logic, width=150)

                ui.Spacer(height=5)
                ui.Label("Textures Library Folder:", alignment=ui.Alignment.LEFT)
                with ui.HStack(height=28, spacing=5):
                    self._textures_path_field = ui.StringField()
                    self._textures_path_field.model.set_value(self._textures_folder)
                    ui.Button("...", clicked_fn=self._browse_textures_folder, width=30)
                ui.Button("RELINK ALL SCENE TEXTURES", clicked_fn=self.relink_scene_textures_logic,
                          style={"background_color": 0xFF224477}, height=35)

                ui.Spacer(height=5)
                ui.Label("--- MANUAL POPULATE ---",
                         alignment=ui.Alignment.CENTER, style={"color": 0xFF888888})
                ui.Button("POPULATE TO SELECTED",
                          clicked_fn=self.populate_to_selected_logic, height=35)

                ui.Button("POPULATE TO SELECTED",
                          clicked_fn=self.populate_to_selected_logic, height=35)

        # --- ADD MODEL BRIDGE LAUNCHER ---
        try:
            import Nfnt_Model_To_Isaac_Bridge
            import importlib
            importlib.reload(Nfnt_Model_To_Isaac_Bridge)
            self._model_bridge = Nfnt_Model_To_Isaac_Bridge.NfntModelToIsaacBridge()
            self._model_bridge.on_startup(ext_id)
        except Exception as e:
            carb.log_warn(f"[ALIGNER] Failed to load Model Bridge: {e}")

        import omni.kit.ui
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            self._menu_item = editor_menu.add_item(
                "Window/Aligner & Measure", lambda: self._window.show(), True)

    # ── FOLDER PICKER ──
    def _browse_folder(self):
        try:
            import omni.kit.window.filepicker as fp
            def on_apply(filename, dirname):
                folder = dirname.replace("\\", "/")
                self._folder_field.model.set_value(folder)
                # self._scene_folder IS the model, so we don't reassign it to a string
                prefs = _load_prefs(); prefs["scene_folder"] = folder; _save_prefs(prefs)
                if hasattr(self, "_fp_dir"): self._fp_dir.hide()
            self._fp_dir = fp.FilePickerDialog(
                "Select Scene Export Folder",
                apply_button_label="Select Folder",
                click_apply_handler=on_apply,
            )
            if self._scene_folder:
                self._fp_dir.navigate_to(self._scene_folder)
            self._fp_dir.show()
        except Exception as e:
            carb.log_warn(f"[BRIDGE] Folder picker error: {e}")

    def _browse_library_folder(self):
        try:
            import omni.kit.window.filepicker as fp
            def on_apply(filename, dirname):
                folder = dirname.replace("\\", "/")
                self._library_path.model.set_value(folder)
                prefs = _load_prefs()
                prefs["assets_folder"] = folder
                _save_prefs(prefs)
                if hasattr(self, "_fp_lib_dir"): self._fp_lib_dir.hide()
            self._fp_lib_dir = fp.FilePickerDialog(
                "Select Library Folder",
                apply_button_label="Select Folder",
                click_apply_handler=on_apply,
            )
            cur = self._library_path.model.get_value_as_string()
            if cur: self._fp_lib_dir.navigate_to(cur)
            self._fp_lib_dir.show()
        except Exception as e:
            carb.log_warn(f"[BRIDGE] Library picker error: {e}")

    def _browse_textures_folder(self):
        try:
            import omni.kit.window.filepicker as fp
            def on_apply(filename, dirname):
                folder = dirname.replace("\\", "/")
                self._textures_path_field.model.set_value(folder)
                # self._textures_folder is just for initial value/nav
                prefs = _load_prefs(); prefs["texture_folder"] = folder; _save_prefs(prefs)
                if hasattr(self, "_fp_tex_dir"): self._fp_tex_dir.hide()
            self._fp_tex_dir = fp.FilePickerDialog(
                "Select Textures Library Folder",
                apply_button_label="Select Folder",
                click_apply_handler=on_apply,
            )
            if self._textures_folder:
                self._fp_tex_dir.navigate_to(self._textures_folder)
            self._fp_tex_dir.show()
        except Exception as e:
            carb.log_warn(f"[BRIDGE] Textures Folder picker error: {e}")

    # ── LOAD ALL ──
    def load_all_logic(self):
        folder = self._folder_field.model.get_value_as_string().strip().replace("\\", "/")
        if not folder:
            self._status("⚠ Please set the Scene Export Folder first.", error=True)
            return

        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        loaded = []; skipped = []; missing = []

        local_dir = folder.replace("/", os.sep)
        available_files = os.listdir(local_dir) if os.path.isdir(local_dir) else []

        for key, fname in SCENE_FILES:
            if not self._checkboxes[key].model.get_value_as_bool():
                continue
            
            res = self._load_single_usd(key)
            if res == "loaded": loaded.append(key)
            elif res == "skipped": skipped.append(key)
            elif res == "missing": missing.append(key)

        # Optionally update Assets folder for Auto Populate
        if self._cb_assets.model.get_value_as_bool():
            assets_folder = f"{folder}/"
            self._library_path.model.set_value(assets_folder)
            _save_prefs({"scene_folder": folder, "assets_folder": assets_folder})
        else:
            _save_prefs({"scene_folder": folder})

        # Auto-apply post-load fixes
        if "LIGHT" in loaded or "LIGHT" in skipped:
            try: self.inflate_lights_logic()
            except Exception as e: carb.log_warn(f"Failed to auto-inflate lights: {e}")
        if "ASSET" in loaded or "ASSET" in skipped:
            try: self.inflate_assets_logic()
            except Exception as e: carb.log_warn(f"Failed to auto-inflate assets: {e}")
        if "STRUCTURE" in loaded or "STRUCTURE" in skipped:
            try: self.fix_glass_shadows_logic()
            except Exception as e: carb.log_warn(f"Failed to auto-fix glass shadows: {e}")

        # Status message
        parts = []
        if loaded:   parts.append(f"✓ Loaded: {', '.join(loaded)}")
        if skipped:  parts.append(f"↩ Skipped (exists): {', '.join(skipped)}")
        if missing:  parts.append(f"✗ Not found: {', '.join(missing)}")
        self._status(" | ".join(parts) if parts else "Nothing to load.")


    def _status(self, msg, error=False):
        color = 0xFFFF6666 if error else 0xFF88FF88
        if self._status_label:
            self._status_label.set_style({"color": color})
            self._status_label.text = msg
        print(f"[BRIDGE] {msg}")

    def reload_all_logic(self):
        """Delete existing scene prims then reload all USD files."""
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        to_delete = [f"/World/{key}" for key, _ in SCENE_FILES
                     if stage.GetPrimAtPath(f"/World/{key}").IsValid()]
        if to_delete:
            omni.kit.commands.execute("DeletePrims", paths=to_delete)
            print(f"[BRIDGE] Deleted for reload: {to_delete}")
        self.load_all_logic()

    def reload_single_logic(self, key):
        """Delete specific prim and reload just that USD."""
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        path = f"/World/{key}"
        if stage.GetPrimAtPath(path).IsValid():
            omni.kit.commands.execute("DeletePrims", paths=[path])
            print(f"[BRIDGE] Deleted for single reload: {path}")
        
        res = self._load_single_usd(key)
        if res == "loaded":
            self._status(f"✓ Reloaded {key}")
            # Auto-apply post-load fixes
            if key == "LIGHT": self.inflate_lights_logic()
            elif key == "ASSET": self.inflate_assets_logic()
            elif key == "STRUCTURE": self.fix_glass_shadows_logic()
        elif res == "skipped":
            self._status(f"↩ {key} already exists.")
        else:
            self._status(f"✗ Failed to reload {key}", error=True)

    def _load_single_usd(self, key):
        """Helper to load a single USD file by key (e.g. 'STRUCTURE')."""
        folder = self._folder_field.model.get_value_as_string().strip().replace("\\", "/")
        if not folder: return "error"
        
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        local_dir = folder.replace("/", os.sep)
        available_files = os.listdir(local_dir) if os.path.isdir(local_dir) else []

        # Find filename for key
        fname = next((f[1] for f in SCENE_FILES if f[0] == key), None)
        if not fname: return "error"
        
        target_fname = fname
        for f in available_files:
            if f.upper().endswith(f"_{fname.upper()}") or f.upper() == fname.upper() or f.upper() == f"{key.upper()}_POS.USD":
                target_fname = f
                break

        usd_path = f"{folder}/{target_fname}"
        prim_path = f"/World/{key}"

        if not os.path.isfile(usd_path.replace("/", os.sep)):
            return "missing"

        if stage.GetPrimAtPath(prim_path).IsValid():
            return "skipped"

        prim = stage.DefinePrim(prim_path, "Xform")
        prim.GetReferences().AddReference(usd_path)
        
        # Clean Meters Pipeline: Standardize on Scale 1.0
        xf = UsdGeom.Xformable(prim)
        scale_op = xf.GetScaleOp() or xf.AddScaleOp()
        scale_op.Set(Gf.Vec3f(1.0, 1.0, 1.0))
        
        if key == "STRUCTURE":
            try:
                import omni.physx.scripts.utils as physxUtils
                physxUtils.setStaticCollider(prim)
            except: pass
            
        return "loaded"

    def inflate_assets_logic(self):
        """Standardize on Scale 1.0 (Asset Inflation) while keeping local transformations."""
        try:
            ctx = omni.usd.get_context(); stage = ctx.get_stage()
            old_root_path = "/World/ASSET"
            old_root = stage.GetPrimAtPath(old_root_path)
            if not old_root.IsValid():
                carb.log_warn("[BRIDGE] /World/ASSET for inflation not found."); return

            # Отримуємо глобальні налаштування (Source of Truth)
            prefs = _load_prefs()
            apply_scale = prefs.get("apply_scale", True)
            scale_factor = 0.001 if apply_scale else 1.0
            print(f"[BRIDGE] Pref 'apply_scale': {apply_scale} -> scale_factor: {scale_factor}")

            # Capture Root Transform (Axis Fix)
            root_xf = UsdGeom.Xformable(old_root)
            root_ops = []
            for op in root_xf.GetOrderedXformOps():
                root_ops.append({
                    "type": op.GetOpType(), 
                    "prec": op.GetPrecision(), 
                    "val": op.Get(), 
                    "name": op.GetOpName()
                })

            # Capture Children
            data = []
            all_prims = [p for p in stage.Traverse() if str(p.GetPath()).startswith(old_root_path + "/")]
            all_prims.sort(key=lambda x: len(str(x.GetPath())))
            
            for p in all_prims:
                rel_path = str(p.GetPath().MakeRelativePath(old_root.GetPath()))
                if not rel_path or rel_path == ".": continue
                
                xf = UsdGeom.Xformable(p)
                ops_info = []
                for op in xf.GetOrderedXformOps():
                    # Отримуємо назву атрибута (напр. xformOp:translate)
                    attr_name = str(op.GetAttr().GetName()).lower()
                    op_type = op.GetOpType()
                    
                    is_translate = (op_type == UsdGeom.XformOp.TypeTranslate or "translate" in attr_name)
                    is_matrix = (op_type == UsdGeom.XformOp.TypeTransform)
                    
                    # DEBUG: виводимо в консоль кожну операцію, щоб знайти винуватця
                    # print(f"[BRIDGE] Found Op on {rel_path}: {attr_name} (Type: {op_type}, IsTr: {is_translate}, IsMx: {is_matrix})")
                    
                    ops_info.append({
                        "type": op_type,
                        "prec": op.GetPrecision(),
                        "val": op.Get(),
                        "is_tr": is_translate,
                        "is_mx": is_matrix
                    })
                
                # Fallback matrix (un-converted local)
                m_local = xf.GetLocalTransformation(Usd.TimeCode.Default())
                data.append((rel_path, ops_info, m_local, p.GetTypeName()))
            
            # 2. Rebuild Root with original transform
            omni.kit.commands.execute("DeletePrims", paths=[old_root_path])
            new_root_prim = stage.DefinePrim(old_root_path, "Xform")
            xf_root = UsdGeom.Xformable(new_root_prim)
            for op in root_ops:
                xf_root.AddXformOp(op["type"], op["prec"]).Set(op["val"])
            
            # 3. Rebuild Children 1:1
            count = 0
            for rel_path, ops_info, m_local, type_name in data:
                try:
                    parts = rel_path.split('/')
                    final_rel = "/".join(parts[1:]) if parts[0].upper() == "ASSET" else rel_path
                    if not final_rel: continue
                    
                    target_path = f"{old_root_path}/{final_rel}"
                    new_p = stage.DefinePrim(target_path, type_name if type_name else "Xform")
                    xf_new = UsdGeom.Xformable(new_p)
                    
                    if ops_info:
                        for info in ops_info:
                            val = info["val"]
                            if val is None: continue
                            new_op = xf_new.AddXformOp(info["type"], info["prec"])
                            final_val = val
                            if info["is_tr"] and apply_scale:
                                final_val = val * scale_factor
                                if "_POS" in target_path:
                                    print(f"[BRIDGE] Scaling {target_path} (TRS): {val} -> {final_val}")
                                    
                            elif info["is_mx"] and apply_scale:
                                # Масштабуємо ТІЛЬКИ компонент переміщення в матриці 4x4
                                if not isinstance(val, pxr.Gf.Matrix4d):
                                    final_val = val
                                else:
                                    # Create a deep copy using the Matrix4d constructor
                                    final_val = pxr.Gf.Matrix4d(val)
                                    tr = val.ExtractTranslation()
                                    scaled_tr = tr * scale_factor
                                    
                                    # Set translation elements directly to avoid any side-effects on rotation
                                    final_val[3,0] = scaled_tr[0]
                                    final_val[3,1] = scaled_tr[1]
                                    final_val[3,2] = scaled_tr[2]
                                    
                                    if "_POS" in target_path:
                                        print(f"[BRIDGE] Scaling {target_path} (Matrix): {tr} -> {scaled_tr}")
                            
                            new_op.Set(final_val)
                    else:
                        tr = m_local.ExtractTranslation()
                        ro = m_local.ExtractRotation().Decompose(pxr.Gf.Vec3d(1,0,0), pxr.Gf.Vec3d(0,1,0), pxr.Gf.Vec3d(0,0,1))
                        xf_new.AddTranslateOp().Set(tr * scale_factor)
                        xf_new.AddRotateXYZOp().Set(pxr.Gf.Vec3f(*ro))
                    
                    if "_POS" in target_path: count += 1
                except Exception as e:
                    print(f"[BRIDGE] Skip {rel_path}: {e}")

            msg = f"Inflation Finished! {count} markers active (Root Parity)."
            self._status(f"✓ {msg}")
            print(f"[BRIDGE] {msg}")
            
        except Exception as e:
            msg = f"Asset Inflation FAILED: {e}"
            carb.log_error(msg)
            import traceback
            carb.log_error(traceback.format_exc())
            self._status(f"✗ {msg}", error=True)

    # ── INFLATE LIGHTS (Merged with Clean) ──
    def inflate_lights_logic(self):
        stage = omni.usd.get_context().get_stage()
        old_root = "/World/LIGHT"
        
        if not stage.GetPrimAtPath(old_root).IsValid():
            carb.log_warn("[BRIDGE] /World/LIGHT not found."); return
            
        new_root_path = "/World/LIGHT_CLEAN"
        new_root = stage.DefinePrim(new_root_path, "Xform")
        
        # Clean Meters Pipeline: Use scale 1.0
        UsdGeom.Xformable(new_root).AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))
        
        # Use explicit texture folder or auto-detect 'textures' subfolder
        scene_folder = self._folder_field.model.get_value_as_string().strip()
        tex_folder = self._textures_path_field.model.get_value_as_string().strip()
        if not tex_folder and scene_folder:
            auto_tex = os.path.join(scene_folder, "textures").replace("\\", "/")
            if os.path.isdir(auto_tex.replace("/", os.sep)):
                tex_folder = auto_tex
                carb.log_info(f"[BRIDGE] Auto-detected texture folder: {tex_folder}")
        
        count = 0
        has_dome = False
        markers = [p for p in stage.Traverse() if "_LGT_" in p.GetName() and "_POS" in p.GetName() and old_root in str(p.GetPath())]
        
        for marker in markers:
            parts = marker.GetName().split("_")
            if len(parts) < 8: continue
            
            l_type = parts[2]
            if l_type == "Dome": has_dome = True
            try: intensity = float(parts[3]); dim0 = float(parts[4]); dim1 = float(parts[5])
            except: intensity = 1.0; dim0 = dim1 = 20.0
            
            clean_name = "_".join(parts[6:])
            new_name = f"{l_type}Light_{clean_name}"
            new_path = f"{new_root_path}/{new_name}"
            new_prim = stage.DefinePrim(new_path, "Xform")
            
            # Локальна матриця
            world_m = UsdGeom.Xformable(marker).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            parent_world = UsdGeom.Xformable(marker.GetParent()).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            local_m = world_m * parent_world.GetInverse()
            
            UsdGeom.Xformable(new_prim).AddTransformOp().Set(local_m)
            
            # Створюємо світло
            light_internal_name = f"{l_type}Light_" + "_".join(parts[6:-1]).replace("VRay", "")
            l_path = new_prim.GetPath().AppendChild(light_internal_name)
            
            light = None
            if l_type == "Sphere":
                light = UsdLux.SphereLight.Define(stage, l_path)
                light.GetRadiusAttr().Set(dim0 / 2.0)
            elif l_type == "Rect":
                light = UsdLux.RectLight.Define(stage, l_path)
                light.GetWidthAttr().Set(dim1); light.GetHeightAttr().Set(dim0)
            elif l_type == "Distant":
                light = UsdLux.DistantLight.Define(stage, l_path)
            elif l_type == "Dome":
                light = UsdLux.DomeLight.Define(stage, l_path)
                
                # Automatic HDR Assignment
                calc_tex_folder = tex_folder
                if calc_tex_folder and os.path.isdir(calc_tex_folder.replace("/", os.sep)):
                    hdr_file = None
                    try:
                        for f in os.listdir(calc_tex_folder.replace("/", os.sep)):
                            if f.lower().endswith(".hdr") or f.lower().endswith(".exr"):
                                hdr_file = f; break
                    except: pass
                    
                    if hdr_file:
                        hdr_path = os.path.join(calc_tex_folder, hdr_file).replace("\\", "/")
                        light.GetTextureFileAttr().Set(hdr_path)
                        carb.log_info(f"[BRIDGE] Assigned HDR to DomeLight: {hdr_path}")
            
            if light:
                # Збільшуємо інтенсивність сонця у 100 разів (раніше було 1000, але сцена була пересвічена)
                final_intensity = intensity * 100.0 if l_type == "Distant" else intensity
                light.GetIntensityAttr().Set(final_intensity)
                
                if l_type == "Distant":
                    # М'які тіні (Size Multiplier 5.0 у VRay = кут приблизно 2.5-3.0 градуси)
                    try: light.GetAngleAttr().Set(2.5)
                    except: light.GetPrim().CreateAttribute("inputs:angle", Sdf.ValueTypeNames.Float).Set(2.5)
                    
                    # Налаштовуємо температуру кольору (в районі 5500-5800K для природного сонця з Turbidity 3.0)
                    try:
                        light.GetPrim().CreateAttribute("inputs:enableColorTemperature", Sdf.ValueTypeNames.Bool).Set(True)
                        light.GetPrim().CreateAttribute("inputs:colorTemperature", Sdf.ValueTypeNames.Float).Set(5800.0)
                    except: pass

                count += 1
                
        # Якщо в сцені не було VRayDome, створюємо дефолтне небо
        if not has_dome:
            sky_path = f"{new_root_path}/Default_Sky_Dome"
            sky_dome = UsdLux.DomeLight.Define(stage, sky_path)
            sky_dome.GetIntensityAttr().Set(1000.0) # Базова яскравість неба
            
            # Холоднуватий колір для підсвічування тіней (відтінок неба в ясний день)
            try:
                sky_dome.GetPrim().CreateAttribute("inputs:enableColorTemperature", Sdf.ValueTypeNames.Bool).Set(True)
                sky_dome.GetPrim().CreateAttribute("inputs:colorTemperature", Sdf.ValueTypeNames.Float).Set(8500.0)
            except: pass
            count += 1

        # Замінюємо старий референс на новий локальний
        to_delete = [old_root]
        # Видаляємо дефолтне світло Isaac Sim, якщо воно є
        for p_test in ["/Environment/defaultLight", "/World/Environment/defaultLight"]:
            if stage.GetPrimAtPath(p_test).IsValid():
                to_delete.append(p_test)
        
        omni.kit.commands.execute("DeletePrims", paths=to_delete)
        omni.kit.commands.execute("MovePrim", path_from=new_root_path, path_to=old_root)
            
        msg = f"Lights fixed! ({count} lights processed)"
        carb.log_warn(msg)
        self._status(f"✓ {msg}")

    def reimport_models_logic(self):
        """Clears all children of populated markers and re-runs auto-populate."""
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        if not stage: return
        
        to_delete = []
        # Traverse for markers under /World/ASSET
        for prim in stage.Traverse():
            path = str(prim.GetPath())
            if not path.startswith("/World/ASSET"): continue
            
            # Check if it's a marker (_POS) but NOT a LIGHT marker
            n_up = prim.GetName().upper()
            if "_POS" in n_up and "_LGT_" not in n_up and "LIGHT" not in n_up:
                # Direct children of these markers are the populated references (SM_...)
                for child in prim.GetChildren():
                    to_delete.append(str(child.GetPath()))
        
        if to_delete:
            omni.kit.commands.execute("DeletePrims", paths=to_delete)
            msg = f"Cleared {len(to_delete)} models. Re-populating..."
            carb.log_info(f"[BRIDGE] {msg}")
            self._status(msg)
        
        # Trigger standard populate
        self.auto_populate_logic()

    # ── AUTO POPULATE ──
    def _get_asset_id_from_marker(self, name):
        name_up = name.upper()
        if "_POS" not in name_up: return None
        
        if "_POS_" in name_up:
            base = name.split("_POS_")[-1]
        else:
            base = name.split("_POS")[-1]
            if base.startswith("_"): base = base[1:]
            
        if not base: return None
        return re.sub(r'_\d+$', '', base)

    def auto_populate_logic(self):
        assets_dir = self._library_path.model.get_value_as_string().strip().replace('\\', '/')
        if not assets_dir.endswith("/"): assets_dir += "/"
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        
        # Build dictionary of local files to handle USD replacing hyphens (-) with underscores (_) in marker names
        file_map = {}
        local_dir = assets_dir.replace("/", os.sep)
        if os.path.isdir(local_dir):
            for fname in os.listdir(local_dir):
                if fname.lower().endswith(".usd"):
                    normalized = fname[:-4].replace("-", "_").upper()
                    file_map[normalized] = fname
        
        count = 0
        missing_count = 0
        seen_markers = 0
        
        for marker in stage.Traverse():
            m_path = str(marker.GetPath())
            if "/ASSET" not in m_path: continue
            
            m_name = marker.GetName()
            if "_POS" not in m_name.upper(): continue
            if "_LGT_" in m_name.upper() or "LIGHT" in m_name.upper(): continue
            
            clean_id = self._get_asset_id_from_marker(m_name)
            if not clean_id: continue
            
            seen_markers += 1
            
            # Map clean_id to real filename if it had hyphens
            normalized_id = clean_id.replace("-", "_").upper()
            actual_filename = file_map.get(normalized_id)
            
            if actual_filename:
                asset_url = f"{assets_dir}{actual_filename}"
            else:
                asset_url = f"{assets_dir}{clean_id}.usd"
                local_path = asset_url.replace("/", os.sep)
                if not os.path.isfile(local_path):
                    carb.log_warn(f"[BRIDGE] Missing exact OR mapped file for {clean_id}")
                    missing_count += 1
                    continue
                    
            carb.log_warn(f"[BRIDGE] Found asset marker: {m_name} -> placing {asset_url}")
            
            # Визначаємо суфікс (номер екземпляра)
            suffix = m_name.split("_")[-1]
            if not suffix.isdigit():
                suffix = "01"
                
            # Генеруємо шлях до нового об'єкта (використовуючи Sdf.Path для безпеки)
            try:
                # Очищуємо clean_id від будь-яких символів, які USD не любить у іменах вузлів
                # ВАЖЛИВО: Назва вузла в USD НЕ МОЖЕ починатися з цифри!
                node_name = f"{clean_id}_{suffix}"
                node_name = re.sub(r'[^0-9a-zA-Z_]', '_', node_name)
                
                if node_name[0].isdigit():
                    node_name = f"SM_{node_name}"
                
                inst_path = Sdf.Path(m_path).AppendChild(node_name)
                
                # Створюємо референс
                tp = stage.DefinePrim(inst_path, "Xform")
                tp.GetReferences().AddReference(asset_url)
                
                # FORCE IDENTITY SCALE (Clean Meters Pipeline)
                # Це гарантує, що модель не отримає автоматичний скейл 0.001 від Isaac Sim
                UsdGeom.Xformable(tp).AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))
                
                # APPLY ROTATION CORRECTION (Optional)
                if self._cb_rotate_corr.model.get_value_as_bool():
                    UsdGeom.Xformable(tp).AddRotateXYZOp().Set(Gf.Vec3f(0.0, 0.0, 90.0))
                    print(f"[AUTO POPULATE] Applied +90 deg rotation correction to {node_name}")
                
                print(f"[AUTO POPULATE] Model Loaded: {clean_id} (into {m_name})")
                count += 1
            except Exception as e:
                carb.log_warn(f"[BRIDGE] Failed to place {clean_id} at {m_path}: {e}")
            
        msg = f"AUTO POPULATE DONE! Found {seen_markers} markers. Placed: {count}. Missing: {missing_count}"
        carb.log_warn(f"[BRIDGE] {msg}")
        self._status(msg)

    def export_missing_list_logic(self):
        assets_dir = self._library_path.model.get_value_as_string().strip().replace('\\', '/')
        if not assets_dir.endswith("/"): assets_dir += "/"
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        
        file_map = {}
        local_dir = assets_dir.replace("/", os.sep)
        if os.path.isdir(local_dir):
            for fname in os.listdir(local_dir):
                if fname.lower().endswith(".usd"):
                    normalized = fname[:-4].replace("-", "_").upper()
                    file_map[normalized] = fname
                    
        missing = sorted(set(
            self._get_asset_id_from_marker(p.GetName())
            for p in stage.Traverse() if "/ASSET" in str(p.GetPath()) and "_POS" in p.GetName().upper() and "_LGT_" not in p.GetName().upper() and "LIGHT" not in p.GetName().upper()
        ) - {None})
        
        missing = [m for m in missing
                   if not file_map.get(m.replace("-", "_").upper()) and not os.path.isfile(f"{assets_dir}{m}.usd".replace("/", os.sep))]
        if not missing:
            carb.log_warn("[BRIDGE] No missing files found!")
            return
            
        log = os.path.join(os.path.expanduser("~"), "Desktop", "missing_assets_report.txt")
        with open(log, "w") as f:
            f.write(f"MISSING - {len(missing)} items\n")
            for m in missing: f.write(f"- {m}.usd\n")
        webbrowser.open(log)

    def populate_to_selected_logic(self):
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        sel = ctx.get_selection().get_selected_prim_paths()
        if len(sel) < 2: return
        src = sel[0]
        for tgt in sel[1:]:
            wm   = UsdGeom.Xformable(stage.GetPrimAtPath(tgt)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            tr   = wm.ExtractTranslation()
            rv   = wm.ExtractRotation().Decompose(Gf.Vec3d(1,0,0), Gf.Vec3d(0,1,0), Gf.Vec3d(0,0,1))
            tmp  = f"/World/_AlignTemp_{re.sub('[^0-9a-zA-Z]','',tgt)}"
            omni.kit.commands.execute("CopyPrim", path_from=src, path_to=tmp)
            tp   = stage.GetPrimAtPath(tmp); txf = UsdGeom.Xformable(tp)
            ta   = tp.GetAttribute("xformOp:translate") or txf.AddTranslateOp().GetAttr()
            ra   = tp.GetAttribute("xformOp:rotateXYZ") or txf.AddRotateXYZOp().GetAttr()
            ta.Set(tr); ra.Set(Gf.Vec3f(*rv))
            omni.kit.commands.execute("MovePrim", path_from=tmp, path_to=f"{tgt}/INST")

    def fix_glass_shadows_logic(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            carb.log_warn("No stage open."); return
            
        count = 0
        for prim in stage.Traverse():
            if "WINDOW_GLASS" in prim.GetName().upper() and prim.IsA(UsdGeom.Mesh):
                # Відключаємо Cast Shadows
                prim.CreateAttribute("primvars:doNotCastShadows", Sdf.ValueTypeNames.Bool).Set(True)
                count += 1
                
        msg = f"Windows Glass Shadow OFF! ({count} meshes)"
        carb.log_warn(msg)
        self._status(f"✓ {msg}")

    def relink_scene_textures_logic(self):
        from pxr import UsdShade
        tex_dir = self._textures_path_field.model.get_value_as_string().strip().replace("\\", "/")
        if not tex_dir:
            self._status("⚠ Please set the Textures Library Folder first.", error=True)
            return
        if not tex_dir.endswith("/"): tex_dir += "/"
            
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        root_path = "/World/ASSET"
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim or not root_prim.IsValid():
            self._status("⚠ /World/ASSET not found.", error=True)
            return
            
        # Pre-scan for recursive search
        file_lookup = {}
        tex_dir_os = tex_dir.replace("/", os.sep)
        for root, dirs, files in os.walk(tex_dir_os):
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tga', '.dds', '.exr')):
                    if f not in file_lookup: 
                        file_lookup[f] = os.path.join(root, f).replace("\\", "/")

        count = 0
        for prim in Usd.PrimRange(root_prim):
            if prim.IsA(UsdShade.Shader):
                shader = UsdShade.Shader(prim)
                for input in shader.GetInputs():
                    if input.GetTypeName() == Sdf.ValueTypeNames.Asset:
                        val = input.Get()
                        if val:
                            filepath = str(val.resolvedPath if hasattr(val, "resolvedPath") else val)
                            if not filepath or not os.path.exists(filepath):
                                basename = os.path.basename(filepath)
                                if basename in file_lookup:
                                    input.Set(Sdf.AssetPath(file_lookup[basename]))
                                    count += 1
        
        msg = f"✓ Relinked {count} textures under /World/ASSET."
        self._status(msg)
        carb.log_info(f"[BRIDGE] {msg}")

    def on_shutdown(self):
        if hasattr(self, "_model_bridge") and self._model_bridge:
            self._model_bridge.on_shutdown()
        if hasattr(self, "_window") and self._window:
            self._window.destroy(); self._window = None
