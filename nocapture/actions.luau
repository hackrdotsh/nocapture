local M = {}

M.modes = {
  { id = "region", label = "Region", glyph = "crop" },
  { id = "display", label = "Display", glyph = "device-desktop" },
  { id = "window", label = "Window", glyph = "app-window" },
}

function M.command(options)
  local kind = options.kind
  local target = options.target
  if kind ~= "screenshot" and kind ~= "record" and kind ~= "gif" then
    return nil
  end
  if target ~= "region" and target ~= "display" and target ~= "window" then
    return nil
  end
  local command = { "nocapture-engine", kind == "screenshot" and "screenshot" or "record", target }
  if options.output and options.output ~= "" then
    table.insert(command, "--output")
    table.insert(command, options.output)
  end
  if options.directory and options.directory ~= "" then
    table.insert(command, "--directory")
    table.insert(command, options.directory)
  end
  if kind == "screenshot" then
    if target == "window" then
      if options.windowId then
        table.insert(command, "--window-id")
        table.insert(command, tostring(options.windowId))
      end
      if options.wallpaper then
        table.insert(command, "--wallpaper")
      end
      if options.shadow then
        table.insert(command, "--shadow")
      end
      table.insert(command, "--padding")
      table.insert(command, tostring(options.padding or 96))
    end
  else
    local audio = kind == "gif" and "none" or options.audio or "none"
    if target == "window" and audio ~= "none" and audio ~= "application" then
      return nil
    end
    if audio == "application" and (not options.application or options.application == "") then
      return nil
    end
    table.insert(command, "--format")
    table.insert(command, kind == "gif" and "gif" or "mp4")
    table.insert(command, "--audio")
    table.insert(command, audio)
    if audio == "application" then
      table.insert(command, "--application")
      table.insert(command, options.application)
    end
    table.insert(command, "--fps")
    table.insert(command, tostring(options.fps or 30))
    if kind == "gif" then
      table.insert(command, "--gif-fps")
      table.insert(command, tostring(options.gifFps or 15))
      table.insert(command, "--gif-width")
      table.insert(command, tostring(options.gifWidth or 1280))
    end
  end
  return command
end

return M
