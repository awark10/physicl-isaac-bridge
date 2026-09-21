import omni.ext
import omni.ui as ui
import omni.usd
import omni.kit.commands
import carb
from pxr import Gf, UsdGeom, Usd, UsdPhysics, Sdf, UsdShade
import os
import json
import re

_PREFS_FILE = os.path.join(os.path.expanduser("~"), ".nfinite_bridge_prefs.json")

def _load_prefs():
    try:
        with open(_PREFS_FILE, "r") as f: return json.load(f)
    except: return {}

def _save_prefs(data):
    try:
        with open(_PREFS_FILE, "w") as f: json.dump(data, f)
    except: pass

class NfntModelToIsaacBridge(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[Nfnt_Model_To_Isaac_Bridge] Startup V1.3")
        prefs = _load_prefs()
        self._model_folder = prefs.get("model_folder", "")
        self._textures_folder = prefs.get("textures_folder", "")
        self._apply_scale = prefs.get("apply_scale", True)

        self._window = ui.Window("Nfnt Model To Isaac Bridge", width=440, height=550)
        self._window.frame.clear()
        
        with self._window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=8, margin=15):
                    ui.Label("--- MODEL LOADER ---",
                            alignment=ui.Alignment.CENTER, style={"color": 0xFF44DDAA})
                    
                    ui.Label("Model Export Folder:", alignment=ui.Alignment.LEFT)
                    with ui.HStack(height=28, spacing=5):
                        self._folder_field = ui.StringField()
                        self._folder_field.model.set_value(self._model_folder)
                        ui.Button("...", clicked_fn=self._browse_model_folder, width=30)

                    def on_cb_scale_changed(model):
                        prefs = _load_prefs()
                        prefs["apply_scale"] = model.get_value_as_bool()
                        _save_prefs(prefs)
                        print(f"[BRIDGE] Scale Pref Saved: {prefs['apply_scale']}")

                    with ui.HStack(height=22):
                        self._cb_scale_widget = ui.CheckBox(width=20)
                        self._cb_scale = self._cb_scale_widget.model
                        self._cb_scale.set_value(self._apply_scale)
                        self._cb_scale.add_value_changed_fn(on_cb_scale_changed)
                        ui.Label(" Apply mm-to-m scale (0.001)", alignment=ui.Alignment.LEFT)

                    ui.Button("LOAD MODEL", clicked_fn=self.load_model_logic,
                            style={"background_color": 0xFF227733, "font_size": 15}, height=44)

                    ui.Spacer(height=10)
                    ui.Label("--- TEXTURES ---",
                            alignment=ui.Alignment.CENTER, style={"color": 0xFF88CCFF})
                    
                    ui.Label("Textures Library Folder:", alignment=ui.Alignment.LEFT)
                    with ui.HStack(height=28, spacing=5):
                        self._textures_field = ui.StringField()
                        self._textures_field.model.set_value(self._textures_folder)
                        ui.Button("...", clicked_fn=self._browse_textures_folder, width=30)
                    
                    ui.Button("RELINK TEXTURES ON SELECTED", clicked_fn=self.relink_textures_logic,
                            style={"background_color": 0xFF224477})

                    ui.Spacer(height=10)
                    ui.Label("--- MODEL TOOLS ---",
                            alignment=ui.Alignment.CENTER, style={"color": 0xFFFFAA44})
                    self._ucx_status_label = ui.Label("", alignment=ui.Alignment.LEFT,
                                                    style={"color": 0xFF88FF88, "font_size": 12})
                    with ui.HStack(height=40, spacing=5):
                        ui.Button("APPLY UCX COLLIDERS",
                                clicked_fn=self.apply_ucx_colliders_logic,
                                style={"background_color": 0xFF774400, "font_size": 13}, height=40)

                    ui.Spacer(height=10)
                    ui.Label("--- TRANSFORM MEASUREMENT ---",
                             alignment=ui.Alignment.CENTER, style={"color": 0xFFFFAA44})
                    
                    with ui.VStack(spacing=4):
                        with ui.HStack(height=22):
                            ui.Label("Translate (m):", width=100)
                            self._meas_t_x = ui.StringField(read_only=True)
                            self._meas_t_y = ui.StringField(read_only=True)
                            self._meas_t_z = ui.StringField(read_only=True)
                        
                        with ui.HStack(height=22):
                            ui.Label("Rotate (deg):", width=100)
                            self._meas_r_x = ui.StringField(read_only=True)
                            self._meas_r_y = ui.StringField(read_only=True)
                            self._meas_r_z = ui.StringField(read_only=True)

                        with ui.HStack(height=22):
                            ui.Label("Size (mm):", width=100)
                            self._field_x = ui.StringField(read_only=True)
                            self._field_y = ui.StringField(read_only=True)
                            self._field_z = ui.StringField(read_only=True)

                        with ui.HStack(height=22):
                            self._meas_space_cb = ui.CheckBox(width=20)
                            self._meas_space_cb.model.set_value(False) # False = Local, True = World
                            ui.Label(" World Space", alignment=ui.Alignment.LEFT, style={"color": 0xFF888888})
                    
                    ui.Spacer(height=10)
                    with ui.HStack(spacing=10, height=35):
                        ui.Button("MEASURE",  clicked_fn=self.measure_selected_logic, height=35)
                        ui.Button("COPY ALL", clicked_fn=self.copy_all_logic, height=35)

        import omni.kit.ui
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            self._menu_item = editor_menu.add_item(
                "Window/Nfnt Model Bridge", lambda: self._window.show(), True)

    def _browse_model_folder(self):
        self._browse_folder(self._folder_field, "model_folder")

    def _browse_textures_folder(self):
        self._browse_folder(self._textures_field, "textures_folder")

    def _browse_folder(self, target_field, pref_key):
        try:
            import omni.kit.window.filepicker as fp
            def on_apply(filename, dirname):
                folder = dirname.replace("\\", "/")
                target_field.model.set_value(folder)
                if pref_key == "model_folder": self._model_folder = folder
                else: self._textures_folder = folder
                
                prefs = _load_prefs()
                prefs[pref_key] = folder
                _save_prefs(prefs)
                if hasattr(self, "_fp_dir"): self._fp_dir.hide()
            
            self._fp_dir = fp.FilePickerDialog(
                f"Select {pref_key.replace('_', ' ').title()}",
                apply_button_label="Select Folder",
                click_apply_handler=on_apply,
            )
            curr = target_field.model.get_value_as_string()
            if curr: self._fp_dir.navigate_to(curr)
            self._fp_dir.show()
        except Exception as e:
            carb.log_warn(f"[MODEL BRIDGE] Folder picker error: {e}")

    def load_model_logic(self):
        folder = self._folder_field.model.get_value_as_string().strip().replace("\\", "/")
        if not folder:
            self._ucx_status("⚠ Please set the Model Export Folder first.", error=True)
            return

        target_fname = None
        local_dir = folder.replace("/", os.sep)
        if os.path.isdir(local_dir):
            files = os.listdir(local_dir)
            for f in files:
                if f.upper().endswith("_MODEL.USD") or f.upper() == "MODEL.USD":
                    target_fname = f
                    break
        
        if not target_fname:
            self._ucx_status(f"✗ No *_MODEL.usd found in {folder}", error=True)
            return

        usd_path = f"{folder}/{target_fname}"
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        prim_path = "/World/MODEL"
        
        # Check file exists (local path)
        local_path = usd_path.replace("/", os.sep)
        if not os.path.isfile(local_path):
            self._ucx_status(f"✗ Model USD file not found: {usd_path}", error=True)
            return

        if stage.GetPrimAtPath(prim_path).IsValid():
            omni.kit.commands.execute("DeletePrims", paths=[prim_path])
        
        prim = stage.DefinePrim(prim_path, "Xform")
        prim.GetReferences().AddReference(usd_path)
        
        # Clean Meters Pipeline: Identity Scale by default
        xf = UsdGeom.Xformable(prim)
        scale_val = Gf.Vec3f(0.001, 0.001, 0.001) if self._cb_scale.model.get_value_as_bool() else Gf.Vec3f(1.0, 1.0, 1.0)
        
        scale_op = xf.GetScaleOp()
        if not scale_op:
            scale_op = xf.AddScaleOp()
        scale_op.Set(scale_val)
        
        carb.log_info(f"[MODEL BRIDGE] Loaded model at {scale_val[0]} scale.")
        
        prefs = _load_prefs()
        prefs["model_folder"] = folder
        prefs["apply_scale"] = self._cb_scale.model.get_value_as_bool()
        _save_prefs(prefs)
        
        self._ucx_status(f"✓ Loaded: {target_fname}")
        self.apply_ucx_colliders_logic()
        
        # Auto-relink textures if folder is set
        tex_folder = self._textures_field.model.get_value_as_string()
        if tex_folder:
            self.relink_textures_logic(root_path=prim_path)

    def relink_textures_logic(self, root_path=None):
        tex_dir = self._textures_field.model.get_value_as_string().strip().replace("\\", "/")
        if not tex_dir:
            self._ucx_status("⚠ Please set Textures Folder first.", error=True)
            return
        if not tex_dir.endswith("/"): tex_dir += "/"
            
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        
        # If no root supplied, use selection or the last loaded /World/MODEL
        if not root_path:
            sel = ctx.get_selection().get_selected_prim_paths()
            if sel: root_path = sel[0]
            else: root_path = "/World/MODEL"
            
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim or not root_prim.IsValid():
            self._ucx_status("⚠ No valid root found for relinking.", error=True)
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
                    # We check for inputs that look like texture files
                    if input.GetTypeName() == Sdf.ValueTypeNames.Asset:
                        val = input.Get()
                        if val:
                            filepath = str(val.resolvedPath if hasattr(val, "resolvedPath") else val)
                            if not filepath or not os.path.exists(filepath):
                                basename = os.path.basename(filepath)
                                if basename in file_lookup:
                                    input.Set(Sdf.AssetPath(file_lookup[basename]))
                                    count += 1
        
        self._ucx_status(f"✓ Relinked {count} textures.")
        carb.log_info(f"[MODEL BRIDGE] Relinked {count} textures under {root_path}")

    def measure_selected_logic(self):
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        if not stage: return
        metersPerUnit = UsdGeom.GetStageMetersPerUnit(stage)
        sel = ctx.get_selection().get_selected_prim_paths()
        if not sel: return
        try:
            prim = stage.GetPrimAtPath(sel[0])
            if not prim.IsValid() or not prim.IsA(UsdGeom.Xformable): return
            
            xf = UsdGeom.Xformable(prim)
            is_world = self._meas_space_cb.model.get_value_as_bool()
            
            # 1. Transform (Translate / Rotate)
            if is_world:
                m = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            else:
                m = xf.GetLocalTransformation()
            
            tr = m.ExtractTranslation()
            ro = m.ExtractRotation().Decompose(Gf.Vec3d(1,0,0), Gf.Vec3d(0,1,0), Gf.Vec3d(0,0,1))
            
            self._meas_t_x.model.set_value(f"{tr[0]:.4f}")
            self._meas_t_y.model.set_value(f"{tr[1]:.4f}")
            self._meas_t_z.model.set_value(f"{tr[2]:.4f}")
            
            self._meas_r_x.model.set_value(f"{ro[0]:.3f}")
            self._meas_r_y.model.set_value(f"{ro[1]:.3f}")
            self._meas_r_z.model.set_value(f"{ro[2]:.3f}")

            # 2. Size (Bounding Box) in mm
            imageable = UsdGeom.Imageable(prim)
            world_bbox = imageable.ComputeWorldBound(Usd.TimeCode.Default(), "default")
            world_range = world_bbox.ComputeAlignedRange()
            s = world_range.GetSize()
            sm = [val * metersPerUnit for val in s]
            smm = [val * 1000.0 for val in sm]

            self._field_x.model.set_value(f"{smm[0]:.1f}")
            self._field_y.model.set_value(f"{smm[1]:.1f}")
            self._field_z.model.set_value(f"{smm[2]:.1f}")

            self._last_measure = (tr, ro, smm)
        except Exception as e:
            carb.log_warn(f"[MEASURE] Error: {e}")

    def copy_all_logic(self):
        import omni.kit.clipboard
        if hasattr(self, "_last_measure"):
            tr, ro, smm = self._last_measure
            text = f"T: {tr[0]:.4f}, {tr[1]:.4f}, {tr[2]:.4f} | R: {ro[0]:.3f}, {ro[1]:.3f}, {ro[2]:.3f} | Size: {smm[0]:.1f}x{smm[1]:.1f}x{smm[2]:.1f} mm"
            omni.kit.clipboard.copy(text)

    def apply_ucx_colliders_logic(self):
        from pxr import UsdPhysics
        ctx = omni.usd.get_context(); stage = ctx.get_stage()
        if not stage: return
        applied = []
        for prim in stage.Traverse():
            name = prim.GetName()
            if not name.upper().startswith("UCX_") or not prim.IsA(UsdGeom.Mesh): continue
            if not prim.HasAPI(UsdPhysics.CollisionAPI): UsdPhysics.CollisionAPI.Apply(prim)
            if not prim.HasAPI(UsdPhysics.MeshCollisionAPI): mesh_col = UsdPhysics.MeshCollisionAPI.Apply(prim)
            else: mesh_col = UsdPhysics.MeshCollisionAPI(prim)
            mesh_col.GetApproximationAttr().Set(UsdPhysics.Tokens.convexHull)
            imageable = UsdGeom.Imageable(prim)
            if imageable: imageable.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
            applied.append(name)

        if applied: 
            self._ucx_status(f"✓ UCX Applied to {len(applied)} meshes.")
        else:
            self._ucx_status("No UCX_ meshes found.")

    def _ucx_status(self, msg, error=False):
        color = 0xFFFF6666 if error else 0xFF88FF88
        if hasattr(self, "_ucx_status_label") and self._ucx_status_label:
            self._ucx_status_label.set_style({"color": color})
            self._ucx_status_label.text = msg

    def on_shutdown(self):
        if hasattr(self, "_window") and self._window:
            self._window.destroy(); self._window = None
