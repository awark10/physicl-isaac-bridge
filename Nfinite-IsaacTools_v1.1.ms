macroScript IsaacSimTools
category:"Nfinite"
tooltip:"Nfinite Isaac Sim Tools"
buttonText:"Isaac Sim"
(
	-- Nfinite Isaac Sim Tools v1.1.15 (SAFETY REVERT)
	-- Reverting Destructive Unit Swap to fix "Gigantic Objects" issue.
	
	global rNfiniteIsaacTools
	global rStructureFilter
	try(destroyDialog rNfiniteIsaacTools) catch()
	try(destroyDialog rStructureFilter) catch()
	
	-- RECURSION
	local colRecursive
	fn colRecursive c r = (
		if (isValidNode c) do (
			for ch in c.children do ( append r ch; colRecursive ch r )
		)
	)
	
	-- LOGIC: HIERARCHY
	fn isAncestor root node = (
		local p = node.parent; local result = false
		while (p != undefined) do ( if (p == root) do result = true; p = p.parent )
		return result
	)
	
	fn selectSubtree root = (
		if (isValidNode root) do (
			local n = #(root); colRecursive root n; selectMore n
		)
	)

	-- --- SAFETY EXPORT (v1.1.15) ---
	-- Using Standard Export to maintain correct numerical size.
	fn exportSafe exportPath isSelectedOnly = (
		-- Reverting to standard export. 
		-- If models are black in Isaac Sim, check Shadow Bias in Isaac Sim (Common for 0.001 scale).
		return (exportFile exportPath #noPrompt selectedOnly:isSelectedOnly)
	)

	fn doExportWithScale ep isSelectedOnly nodes:undefined = (
		local factor = 1.0
		if (rNfiniteIsaacTools != undefined and rNfiniteIsaacTools.chkForceMeters.checked) then (
			case units.SystemType of (
				#millimeters: factor = 0.001
				#centimeters: factor = 0.01
				#inches: factor = 0.0254
				#feet: factor = 0.3048
				default: factor = 1.0
			)
		)
		
		if (factor == 1.0) then ( return (exportSafe ep isSelectedOnly) )
		
		-- Manual Scale logic (Hold/Fetch + Manual Revert Fallback)
		local oldUnits = units.SystemType
		holdMaxFile()
		local ok = false
		local roots = #()
		try (
			units.SystemType = #meters
			local sourceNodes = if nodes != undefined then nodes else (if isSelectedOnly then (selection as array) else (objects as array))
			roots = for n in sourceNodes where (isValidNode n and (n.parent == undefined or (findItem sourceNodes n.parent) == 0)) collect n
			for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [factor, factor, factor]) )
			ok = exportSafe ep isSelectedOnly
		) catch (
			::messageBox ("Export Error: " + getCurrentException())
		)
		
		-- Manual Revert before Fetch (for stability)
		if (roots.count > 0) do (
			for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [1.0/factor, 1.0/factor, 1.0/factor]) )
		)
		units.SystemType = oldUnits
		fetchMaxFile quiet:true
		forceCompleteRedraw()
		
		return ok
	)

	-- ASSETS
	fn convertAssetHierarchyAction silent:false = (
		local asNode = getNodeByName "ASSET"; if (asNode == undefined) do return 0
		local h = for o in objects where (matchPattern o.name pattern:"*_POS" and (isAncestor asNode o)) collect o; local rc = 0
		undo on (
			for p in h where (p.children.count > 0) do (
				local mn = p.children[1].name; local pat = ("*_" + mn)
				if (not (matchPattern p.name pattern:pat)) do ( p.name = p.name + "_" + mn; rc = rc + 1 )
			)
		)
		if (not silent) do (::messageBox ("Renamed " + (rc as string) + " Asset Markers."))
		return rc
	)
	
	fn restoreAssetHierarchyAction silent:false = (
		local asNode = getNodeByName "ASSET"; if (asNode == undefined) do return 0
		local h = for o in objects where (matchPattern o.name pattern:"*_POS_*" and (isAncestor asNode o)) collect o; local rc = 0
		undo on (
			for p in h do ( local idx = findString p.name "_POS_"; if (idx != undefined) do ( p.name = substring p.name 1 (idx + 3); rc = rc + 1 ) )
		)
		if (not silent) do (::messageBox ("Restored " + (rc as string) + " Asset names."))
		return rc
	)

	-- LIGHT BRIDGE (Intensity calibration)
	fn convertVRayLightsAction silent:false = (
		local nconv = 0
		local vlights = for o in objects where ((classOf o == VRayLight or classOf o == VRaySun) and not (matchPattern o.name pattern:"*portal*" ignoreCase:true)) collect o
		if (vlights.count == 0) do ( if (not silent) do (::messageBox "No Lights found."); return false )
		undo on (
			for vl in vlights do (
				local cleanLn = substituteString vl.name "VRay" ""; local lt = vl.transform
				local lType = "Sphere"; local dim0 = 20.0; local dim1 = 20.0
				if (classOf vl == VRaySun) then ( lType = "Distant" ) else (
					case vl.type of (
						0: ( lType = "Rect"; if (hasProperty vl #size0) do dim1 = vl.size0 * 2.0; if (hasProperty vl #size1) do dim0 = vl.size1 * 2.0 )
						1: ( lType = "Dome" )
						2: ( lType = "Sphere"; if (hasProperty vl #size0) do dim0 = vl.size0 * 2.0 )
						4: ( lType = "Sphere"; if (hasProperty vl #size0) do dim0 = vl.size0 * 2.0 )
					)
				)
				local m = 1.0; if (classOf vl == VRaySun) then ( if (hasProperty vl #intensity_multiplier) do m = vl.intensity_multiplier ) else ( if (hasProperty vl #multiplier) do m = vl.multiplier )
				-- Multiplier calibrated for mm-to-m transition
				local mName = "_LGT_" + lType + "_" + (((m * 1000.0) as integer) as string) + "_" + ((dim0 as integer) as string) + "_" + ((dim1 as integer) as string) + "_" + cleanLn + "_POS"
				local newM = Point(); newM.name = mName; newM.size = 10.0; newM.box = true; newM.transform = lt
				if (vl.parent != undefined) do newM.parent = vl.parent
				nconv = nconv + 1; vl.isHidden = true
			)
		)
		return (nconv > 0)
	)
	
	fn restoreVRayLightsAction silent:false = (
		undo on (
			local lMarkers = for o in objects where (matchPattern o.name pattern:"_LGT_*_POS") collect o
			delete lMarkers
			for vl in objects where (classOf vl == VRayLight or classOf vl == VRaySun) do ( vl.isHidden = false )
		)
	)
	
	fn collapseStructureAction silent:false = (
		local sNode = getNodeByName "STRUCTURE"
		if (sNode == undefined) do return (::messageBox "STRUCTURE not found.")
		local nodes = #()
		colRecursive sNode nodes
		local rc = 0
		undo on (
			for n in nodes where (isValidNode n and superclassof n == GeometryClass) do (
				convertToPoly n
				rc = rc + 1
			)
		)
		if (not silent) do (::messageBox ("Converted " + (rc as string) + " Structure elements to Poly."))
		return (rc > 0)
	)

	-- STRUCTURE FILTER
	rollout rStructureFilter "Select Elements for STRUCTURE Export" width:300 height:410 (
		dotNetControl lv "System.Windows.Forms.ListView" width:280 height:320 offset:[0,5]
		button btnExp "EXPORT SELECTED" width:135 height:38 align:#left across:2 offset:[0,5]
		button btnCan "CANCEL" width:135 height:35 align:#right offset:[0,5]
		local structureItems = #(), exportPath = ""
		fn fillList root ep = (
			exportPath = ep; lv.view = (dotNetClass "System.Windows.Forms.View").Details; lv.CheckBoxes = true
			lv.HeaderStyle = (dotNetClass "System.Windows.Forms.ColumnHeaderStyle").None; lv.columns.add "Name" 250
			structureItems = for c in root.children collect c
			for o in structureItems do ( (lv.items.add o.name).checked = true )
		)
		on btnExp pressed do (
			local toExportChoices = #()
			for i = 0 to lv.items.count-1 do ( if lv.items.item[i].checked do append toExportChoices structureItems[i+1] )
			if toExportChoices.count > 0 then (
				holdMaxFile()
				clearSelection(); for o in toExportChoices do ( selectSubtree o ) 
				
				-- Hierarchy Normalization: Make all selected objects unique to prevent USD instancing issues
				InstanceMgr.MakeObjectsUnique selection #individual
				
				-- Apply Material Modifier to fix GeomSubsets if checked
				local matMod = undefined
				if (rNfiniteIsaacTools != undefined and rNfiniteIsaacTools.chkResetMatIDs.checked) do (
					matMod = Materialmodifier materialID:1
					for o in selection where superclassof o == GeometryClass do addModifier o matMod
				)
				
				local ok = false
				local oldUnits = units.SystemType
				local needsScale = (rNfiniteIsaacTools.chkForceMeters.checked and (units.SystemType != #meters))
				if (needsScale) then (
					local factor = 1.0
					case units.SystemType of ( #millimeters: factor = 0.001; #centimeters: factor = 0.01; #inches: factor = 0.0254; #feet: factor = 0.3048; default: factor = 1.0 )
					units.SystemType = #meters
					local roots = for o in toExportChoices where (o.parent == undefined or (findItem toExportChoices o.parent) == 0) collect o
					for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [factor, factor, factor]) )
					ok = exportSafe exportPath true
					
					-- Manual Revert (redundant but safe)
					for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [1.0/factor, 1.0/factor, 1.0/factor]) )
				) else (
					ok = exportSafe exportPath true
				)
				
				units.SystemType = oldUnits
				fetchMaxFile quiet:true
				
				if (ok) then ( 
					destroyDialog rStructureFilter
					::messageBox "STRUCTURE Exported."
				)
			) else ( ::messageBox "Please select at least one object." )
		)
		on btnCan pressed do ( destroyDialog rStructureFilter )
	)

	-- UI
	rollout rNfiniteIsaacTools "Nfinite Isaac Tools v1.1.15" width:340 (
		group "Model Export" (
			checkbox chkResetMatIDs "Reset Mat IDs to 1 (Fix GeomSubsets)" checked:true offset:[0,5]
			checkbox chkForceMeters "Force Meters (0.001 scale + System Unit)" checked:true offset:[0,5]
			button btnModelExp "EXPORT SELECTED MODEL" width:300 height:45 offset:[0,5]
		)
		group "Scene Export" (
			button btnStruct "STRUCTURE EXPORT..." width:300 height:45
			button btnAsExp "ASSET POS EXPORT" width:300 height:45
			button btnCamExp "CAMERA EXPORT" width:300 height:45
			button btnLightExp "LIGHT EXPORT (Bridge)" width:300 height:45
			--button btnFull "Export FULL Scene" width:300 height:35
		)
		checkbutton cbManual "Show Advanced Controls" width:300 height:28 highlightColor:[120,150,220]
		button btnPos "Marker Rename" width:145 height:30 align:#left across:2 offset:[0,20]; button btnPosRes "Marker Restore" width:145 height:30 align:#right offset:[0,20]
		button btnLight "Tag Physical L" width:145 height:30 align:#left across:2; button btnRestore "Rest Orig L" width:145 height:30 align:#right
		button btnCollapse "Collapse Structure (to Poly)" width:300 height:30 offset:[0,5]
		
		on rNfiniteIsaacTools open do ( cbManual.state = false; rNfiniteIsaacTools.height = 425; btnPos.visible = btnPosRes.visible = btnLight.visible = btnRestore.visible = btnCollapse.visible = false )
		on cbManual changed state do ( if state then ( rNfiniteIsaacTools.height = 570; btnPos.visible = btnPosRes.visible = btnLight.visible = btnRestore.visible = btnCollapse.visible = true ) else ( btnPos.visible = btnPosRes.visible = btnLight.visible = btnRestore.visible = btnCollapse.visible = false; rNfiniteIsaacTools.height = 425 ) )
		
		on btnStruct pressed do ( 
			local r = getNodeByName "STRUCTURE"
			if (r == undefined) do return (::messageBox "STRUCTURE not found.")
			local fName = if maxFileName != "" then (getFilenameFile maxFileName) + "_STRUCTURE.usd" else "STRUCTURE.usd"
			local ep = getSaveFileName caption:"Export Structure" filename:(maxFilePath + fName) types:"USD (*.usd)|*.usd"
			if (ep != undefined) do ( createDialog rStructureFilter; rStructureFilter.fillList r ep )
		)
		
		on btnAsExp pressed do (
			local asNode = getNodeByName "ASSET"; if (asNode == undefined) do return (::messageBox "ASSET not found.")
			local fName = if maxFileName != "" then (getFilenameFile maxFileName) + "_ASSET.usd" else "ASSET.usd"
			local ep = getSaveFileName caption:"Export ASSET" filename:(maxFilePath + fName) types:"USD (*.usd)|*.usd"
			if (ep == undefined) do return false
			
			local needsScale = (chkForceMeters.checked and (units.SystemType != #meters))
			if (needsScale) do holdMaxFile()
			
			convertAssetHierarchyAction silent:true
			local phelpers = for o in objects where (matchPattern o.name pattern:"*_POS*" and (isAncestor asNode o)) collect o
			local n = #(asNode)
			for p in phelpers do ( local cur = p; while (cur != undefined and cur != asNode) do ( appendIfUnique n cur; cur = cur.parent ) )
			clearSelection(); select n 
			
			if (needsScale) then (
				local oldUnits = units.SystemType
				local factor = 1.0
				case units.SystemType of ( #millimeters: factor = 0.001; #centimeters: factor = 0.01; #inches: factor = 0.0254; #feet: factor = 0.3048; default: factor = 1.0 )
				units.SystemType = #meters
				local roots = #(asNode)
				for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [factor, factor, factor]) )
				exportSafe ep true
				
				-- Manual Revert
				for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [1.0/factor, 1.0/factor, 1.0/factor]) )
				units.SystemType = oldUnits
				restoreAssetHierarchyAction silent:true -- Added safety call
				fetchMaxFile quiet:true
			) else (
				exportSafe ep true
				restoreAssetHierarchyAction silent:true
			)
			::messageBox "Asset POS Exported."
		)
		on btnCamExp pressed do (
			local camNode = getNodeByName "CAMERA"; if (camNode == undefined) do return (::messageBox "CAMERA not found.")
			local fName = if maxFileName != "" then (getFilenameFile maxFileName) + "_CAMERA.usd" else "CAMERA.usd"
			local ep = getSaveFileName caption:"Export CAMERA" filename:(maxFilePath + fName) types:"USD (*.usd)|*.usd"
			if (ep != undefined) then ( clearSelection(); selectSubtree camNode; doExportWithScale ep true; ::messageBox "Camera Exported." )
		)
		on btnLightExp pressed do (
			local fName = if maxFileName != "" then (getFilenameFile maxFileName) + "_LIGHTS.usd" else "LIGHTS.usd"
			local ep = getSaveFileName caption:"Export Light Markers" filename:(maxFilePath + fName) types:"USD (*.usd)|*.usd"
			if (ep == undefined) do return false
			
			local needsScale = (chkForceMeters.checked and (units.SystemType != #meters))
			if (needsScale) do holdMaxFile()
			
			local oldUnits = units.SystemType
			if (convertVRayLightsAction silent:true) then (
				local lRoots = for o in objects where (matchPattern o.name pattern:"_LGT_*_POS") collect o
				if (lRoots.count > 0) then ( 
					clearSelection(); select lRoots
					if (needsScale) then (
						local factor = 1.0
						case units.SystemType of ( #millimeters: factor = 0.001; #centimeters: factor = 0.01; #inches: factor = 0.0254; #feet: factor = 0.3048; default: factor = 1.0 )
						units.SystemType = #meters
						for n in lRoots do ( if isValidNode n do n.transform *= (scaleMatrix [factor, factor, factor]) )
						exportSafe ep true
						
						-- Manual Revert
						for n in lRoots do ( if isValidNode n do n.transform *= (scaleMatrix [1.0/factor, 1.0/factor, 1.0/factor]) )
						units.SystemType = oldUnits
						fetchMaxFile quiet:true
					) else (
						exportSafe ep true
						restoreVRayLightsAction silent:true
					)
					::messageBox "Light Markers Exported."
				) else ( if (needsScale) do ( fetchMaxFile quiet:true; units.SystemType = oldUnits ) )
			) else ( if (needsScale) do ( fetchMaxFile quiet:true; units.SystemType = oldUnits ) )
		)
		--on btnFull pressed do ( local p = getSaveFileName caption:"Export Full Scene" types:"USD (*.usd)|*.usd"; if (p != undefined) do ( exportSafe p false ) )
		on btnModelExp pressed do (
			if (selection.count == 0) do return (::messageBox "Please select at least one object before exporting.")
			local fName = if maxFileName != "" then (getFilenameFile maxFileName) + ".usd" else "MODEL.usd"
			local ep = getSaveFileName caption:"Export Selected Model" filename:(maxFilePath + fName) types:"USD (*.usd)|*.usd"
			if (ep != undefined) then (
				holdMaxFile()
				local needsScale = (chkForceMeters.checked and (units.SystemType != #meters))
				local rawNodes = #()
				for o in selection do ( appendIfUnique rawNodes o; colRecursive o rawNodes )
				local allNodes = #()
				for n in rawNodes do appendIfUnique allNodes n
				InstanceMgr.MakeObjectsUnique allNodes #individual
				local matMod = undefined
				if chkResetMatIDs.checked do (
					matMod = Materialmodifier materialID:1
					for n in allNodes where (isValidNode n and superclassof n == GeometryClass) do addModifier n matMod
				)
				local origNames = #()
				for n in allNodes do ( 
					append origNames n.name
					local isGeo = (isValidNode n and superclassof n == GeometryClass) and not (matchPattern n.name pattern:"UCX_*" ignoreCase:true)
					local startsWithNum = (isValidNode n and matchPattern (substring n.name 1 1) pattern:"[0-9]")
					local isTopLevel = (isValidNode n and (n.parent == undefined or (findItem allNodes n.parent) == 0))
					if (isGeo or startsWithNum or isTopLevel) do ( n.name = "SM_" + n.name )
				)
				clearSelection(); select allNodes
				local ok = false
				if (needsScale) then (
					local oldUnits = units.SystemType
					local factor = 1.0
					case units.SystemType of ( #millimeters: factor = 0.001; #centimeters: factor = 0.01; #inches: factor = 0.0254; #feet: factor = 0.3048; default: factor = 1.0 )
					units.SystemType = #meters
					local roots = for n in allNodes where (isValidNode n and (n.parent == undefined or (findItem allNodes n.parent) == 0)) collect n
					for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [factor, factor, factor]) )
					ok = exportSafe ep true
					for n in roots do ( if isValidNode n do n.transform *= (scaleMatrix [1.0/factor, 1.0/factor, 1.0/factor]) )
					units.SystemType = oldUnits
				) else (
					ok = exportSafe ep true
				)
				fetchMaxFile quiet:true
				forceCompleteRedraw()
				if ok do ( ::messageBox ("Model Exported: " + ep) )
			)
		)
		on btnPos pressed do ( convertAssetHierarchyAction() ); on btnPosRes pressed do ( restoreAssetHierarchyAction() )
		on btnLight pressed do ( convertVRayLightsAction() ); on btnRestore pressed do ( restoreVRayLightsAction() )
		on btnCollapse pressed do ( collapseStructureAction() )
	)
	createDialog rNfiniteIsaacTools
)
