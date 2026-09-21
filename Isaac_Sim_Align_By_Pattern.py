import omni.usd
import omni.kit.commands
import re
from pxr import Gf, UsdGeom

def align_and_populate():
    """
    Script to align existing objects by ID or duplicate a single object to multiple _POS targets.
    """
    ctx = omni.usd.get_context()
    selection = ctx.get_selection().get_selected_prim_paths()
    stage = ctx.get_stage()
    
    if not selection:
        print("[-] Error: Nothing selected.")
        return

    # 1. Find all target markers (_POS) in the stage
    all_targets = [p for p in stage.Traverse() if "_POS" in p.GetName()]
    if not all_targets:
        print("[-] Error: No '_POS' objects found.")
        return

    # Sort targets numerically
    all_targets.sort(key=lambda x: int(re.findall(r'\d+', x.GetName())[-1]) if re.findall(r'\d+', x.GetName()) else 0)

    # MODE A: Single object -> Many targets (Duplicate)
    if len(selection) == 1:
        source_path = selection[0]
        source_name = stage.GetPrimAtPath(source_path).GetName()
        print(f"[*] Mode: DUPLICATE '{source_name}' to all {len(all_targets)} targets...")

        for target in all_targets:
            t_nums = re.findall(r'\d+', target.GetName())
            t_suffix = f"_{t_nums[-1]}" if t_nums else ""
            new_name = f"{source_name}{t_suffix}"
            new_path = f"{target.GetPath()}/{new_name}"
            
            omni.kit.commands.execute("CopyPrim", path_from=source_path, path_to=new_path)
            omni.kit.commands.execute("TransformPrimSRTCommand",
                path=new_path,
                new_translation=Gf.Vec3d(0, 0, 0),
                new_rotation_euler=Gf.Vec3d(0, 0, 0),
                new_scale=Gf.Vec3d(1, 1, 1)
            )
        print("[+] Success: Copies created and aligned.")

    # MODE B: Many objects -> One-to-one (Align by ID)
    else:
        print(f"[*] Mode: ALIGN multiple selected objects...")
        for s_path in selection:
            s_prim = stage.GetPrimAtPath(s_path)
            s_nums = re.findall(r'\d+', s_prim.GetName())
            if not s_nums: continue
            
            s_id = int(s_nums[-1])
            for target in all_targets:
                t_nums = re.findall(r'\d+', target.GetName())
                if t_nums and int(t_nums[-1]) == s_id:
                    new_path = f"{target.GetPath()}/{s_prim.GetName()}"
                    omni.kit.commands.execute("MovePrim", path_from=s_path, path_to=new_path)
                    omni.kit.commands.execute("TransformPrimSRTCommand",
                        path=new_path,
                        new_translation=Gf.Vec3d(0, 0, 0),
                        new_rotation_euler=Gf.Vec3d(0, 0, 0)
                    )
                    break

if __name__ == "__main__":
    align_and_populate()
