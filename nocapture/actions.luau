local M = {}

M.modes = {
  { id = "region", label = "Region", glyph = "crop" },
  { id = "display", label = "Display", glyph = "device-desktop" },
  { id = "window", label = "Window", glyph = "app-window" },
}

function M.command(kind, target)
  if kind ~= "screenshot" and kind ~= "record" then
    return nil
  end
  if target ~= "region" and target ~= "display" and target ~= "window" then
    return nil
  end
  if kind == "record" then
    local source = { region = "region", display = "focused", window = "portal" }
    return {
      "noctalia",
      "msg",
      "plugin",
      "noctalia/screen_recorder:service",
      "all",
      "start",
      source[target],
    }
  end
  if target == "window" then
    return { "niri", "msg", "action", "screenshot-window" }
  end
  if target == "display" then
    return { "noctalia", "msg", "screenshot-fullscreen", "pick" }
  end
  return { "noctalia", "msg", "screenshot-region" }
end

function M.stopCommand()
  return { "noctalia", "msg", "plugin", "noctalia/screen_recorder:service", "all", "stop" }
end

function M.recorderEnabled(list)
  for line in list:gmatch("[^\r\n]+") do
    if line:match("^noctalia/screen_recorder%s") and line:match("%senabled$") then
      return true
    end
  end
  return false
end

return M
