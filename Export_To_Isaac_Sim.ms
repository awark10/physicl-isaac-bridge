macroScript ExportToIsaacSim
category:"Nfinite"
tooltip:"Export Scene to Isaac Sim (USD)"
(
	-- Get 3ds Max year from version number
	fn getMaxYear = (
		local ver = (maxVersion())[1] / 1000
		case ver of (
			24: "2022"
			25: "2023"
			26: "2024"
			27: "2025"
			28: "2026"
			default: undefined
		)
	)

	-- Return the matching GitHub MSI download URL
	fn getUSDInstallerUrl maxYear = (
		case maxYear of (
			"2022": "https://github.com/Autodesk/3dsmax-usd/releases/download/v0.9.0/USD3dsMax2022-0.9.0-0.9-release_085.msi"
			"2023": "https://github.com/Autodesk/3dsmax-usd/releases/download/v0.13.0/USD3dsMax2023-0.13.0-0.13-release_013.msi"
			"2024": "https://github.com/Autodesk/3dsmax-usd/releases/download/v0.13.0/USD3dsMax2024-0.13.0-0.13-release_013.msi"
			"2025": "https://github.com/Autodesk/3dsmax-usd/releases/download/v0.13.0/USD3dsMax2025-0.13.0-0.13-release_013.msi"
			"2026": "https://github.com/Autodesk/3dsmax-usd/releases/download/v0.13.0/USD3dsMax2026-0.13.0-0.13-release_013.msi"
			default: undefined
		)
	)

	-- Check if the USD plugin is installed by looking in ProgramData\Autodesk\ApplicationPlugins
	fn isUSDInstalled = (
		local maxYear = getMaxYear()
		if maxYear == undefined do return false
		local pluginDir = "C:\\ProgramData\\Autodesk\\ApplicationPlugins\\USD for 3ds Max " + maxYear + "\\"
		doesFileExist pluginDir
	)

	-- Download and install the USD plugin for the current 3ds Max version
	fn installUSDPlugin = (
		local maxYear = getMaxYear()
		if maxYear == undefined do (
			messageBox "Your 3ds Max version is not supported by the Autodesk USD plugin.\nSupported: 3ds Max 2022 - 2026." title:"Unsupported Version"
			return false
		)

		local url = getUSDInstallerUrl maxYear
		local msiPath = (getDir #temp) + "\\USD3dsMax" + maxYear + ".msi"

		messageBox ("Autodesk USD plugin not found.\nDownloading installer for 3ds Max " + maxYear + "...\n\nThis may take a minute. Click OK and wait.") title:"Installing USD Plugin"

		-- Download using bitsadmin
		local dlCmd = "bitsadmin /transfer USDDl /download /priority normal \"" + url + "\" \"" + msiPath + "\""
		DOSCommand dlCmd

		if doesFileExist msiPath then (
			messageBox ("Download complete!\nThe installer will now open.\nPlease complete the installation, then RESTART 3ds Max.") title:"USD Plugin"
			ShellLaunch "msiexec.exe" ("/i \"" + msiPath + "\"")
			true
		) else (
			messageBox "Failed to download the USD plugin installer. Check your internet connection." title:"Error"
			false
		)
	)

	-- Find instances that have a different material than other instances in the same group
	-- and convert them to unique geometry. Returns the count of converted objects.
	fn prepareInstancesForExport objList = (
		local processed = #()
		local converted = 0

		for obj in objList do (
			if findItem processed obj == 0 do (
				local insts = #()
				InstanceMgr.GetInstances obj &insts
				if insts.count > 1 do ( -- count will be at least 1 (the object itself)
					-- Filter out the object itself from the instances list for processing
					local otherInsts = for i in insts where i != obj collect i
					
					-- Build the complete instance group: obj + all its instances
					local allInsts = #(obj)
					join allInsts otherInsts

					-- Mark all as processed so we don't re-process the same group
					for inst in allInsts do append processed inst

					-- Find the "base" material (from the first instance)
					local baseMat = allInsts[1].material

					-- Collect instances that have a different material
					local diffObjs = #()
					for i = 2 to allInsts.count do (
						if allInsts[i].material != baseMat do
							append diffObjs allInsts[i]
					)

					-- Convert instances with different materials to unique geometry
					if diffObjs.count > 0 do (
						for dObj in diffObjs do (
							-- Detach shared geometry by replacing baseObject with a copy
							-- This is the most reliable way to "uninstance" in MAXScript
							dObj.baseObject = copy dObj.baseObject
							converted += 1
						)
					)
				)
			)
		)
		converted
	)

	rollout ro_export_isaac "Export to Isaac Sim (USD)"
	(
		label lbl_info "Exports the current 3ds Max scene to USD" align:#left
		label lbl_info2 "format for use in NVIDIA Isaac Sim." align:#left

		edittext edt_path "Save Path:" text:"C:\\temp\\scene.usd" width:300
		button btn_browse "Browse..." width:80 align:#right

		checkbox chk_selection "Export Selected Objects Only" checked:false

		button btn_export "Export to USD" width:150 height:40 align:#center offset:[0,10]

		on btn_browse pressed do
		(
			local savePath = getSaveFileName caption:"Save USD File for Isaac Sim" types:"USD File (*.usd)|*.usd|USD ASCII (*.usda)|*.usda|USD Crate (*.usdc)|*.usdc"
			if savePath != undefined do edt_path.text = savePath
		)

		on btn_export pressed do
		(
			-- Check if USD plugin is installed; offer to install if not
			if not (isUSDInstalled()) do (
				local doInstall = queryBox "Autodesk USD plugin is not installed.\nWould you like to download and install it now?" title:"USD Plugin Required"
				if doInstall then (
					installUSDPlugin()
					return ()
				) else (
					messageBox "Export cancelled. Please install the Autodesk USD plugin and restart 3ds Max." title:"Cancelled"
					return ()
				)
			)

			local exportPath = edt_path.text
			if exportPath == "" do (
				messageBox "Please specify a file path to save to." title:"Error"
				return ()
			)

			-- Create output directory if needed
			local outDir = getFilenamePath exportPath
			if not (doesFileExist outDir) do makeDir outDir

			-- Hold current scene state so we can restore after export
			holdMaxFile()

			-- Convert instances with a unique material to individual geometry
			local objList = if chk_selection.checked then selection as array else objects as array
			local convertedCount = prepareInstancesForExport objList

			-- Export
			local success = false
			try (
				success = exportFile exportPath #noPrompt selectedOnly:chk_selection.checked
			) catch (
				success = false
			)

			-- Restore scene (undo the instance-to-unique conversions)
			fetchMaxFile()

			-- Show result
			if success then (
				local extraMsg = ""
				if convertedCount > 0 do
					extraMsg = "\n\n(" + convertedCount as string + " instance(s) with unique materials were temporarily converted for export. Your scene was restored.)"
				messageBox ("Scene exported successfully:\n" + exportPath + "\n\nYou can now open this file in Isaac Sim!" + extraMsg) title:"Success"
			) else (
				messageBox "Export failed. Make sure the Autodesk USD plugin is properly installed." title:"Error"
			)
		)
	)

	createDialog ro_export_isaac width:340 height:170
)
