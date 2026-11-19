local actions = require("./actions.luau")
local kind = "screenshot"
local target = "region"
local audio = "none"
local wallpaper = false
local shadow = false
local asShown = true
local context = { applications = {} }
local applicationIndex = 1
local busy = false
local generation = 0
local closingForCapture = false
local visible = false
local recording = { state = "idle" }
local polling = false
local render

local function errorMessage(message)
  busy = false
  if visible then
    render()
  end
  noctalia.notifyError("Nocapture", message)
end

local function execute(command, callback, timeout)
  local accepted = noctalia.runAsync(command, function(result)
    if result.exitCode ~= 0 then
      local message = result.stderr
      if not message or message == "" then
        message = "Check the Nocapture log and try again."
      end
      errorMessage(message)
    elseif callback then
      callback(result)
    end
  end, timeout)
  if not accepted then
    errorMessage("Could not launch nocapture-engine. Install the Nocapture package.")
  end
end

local function setKind(value)
  kind = value
  if kind == "gif" then
    audio = "none"
  end
  render()
end

local function setTarget(value)
  target = value
  audio = "none"
  render()
end

render = function()
  local modes = {}
  for _, mode in ipairs(actions.modes) do
    local id = mode.id
    table.insert(
      modes,
      ui.button({
        text = mode.label,
        glyph = mode.glyph,
        selected = target == id,
        enabled = not busy,
        onClick = function()
          setTarget(id)
        end,
      })
    )
  end
  local options = {}
  if kind == "record" then
    local labels = target == "window" and { "No audio", "Application audio" }
      or { "No audio", "System audio", "Microphone", "System + microphone" }
    local values = target == "window" and { "none", "application" }
      or { "none", "system", "microphone", "both" }
    local selected = 0
    for index, value in ipairs(values) do
      if value == audio then
        selected = index - 1
      end
    end
    table.insert(options, ui.label({ text = "Audio" }))
    table.insert(
      options,
      ui.select({
        options = labels,
        selectedIndex = selected,
        width = 210,
        enabled = not busy,
        onChange = function(value)
          audio = values[tonumber(value) + 1]
          render()
        end,
      })
    )
    if audio == "application" then
      table.insert(options, ui.label({ text = "Application" }))
      table.insert(
        options,
        ui.select({
          options = context.applications,
          selectedIndex = applicationIndex - 1,
          enabled = not busy,
          width = 220,
          onChange = function(value)
            applicationIndex = tonumber(value) + 1
            render()
          end,
        })
      )
    end
  end
  local effects = {}
  if target == "window" and kind == "screenshot" then
    effects = {
      ui.label({ text = "Wallpaper" }),
      ui.toggle({
        checked = wallpaper,
        enabled = not busy,
        onChange = function(value)
          wallpaper = value == "true"
          render()
        end,
      }),
      ui.label({ text = "Window shadow" }),
      ui.toggle({
        checked = shadow,
        enabled = not busy,
        onChange = function(value)
          shadow = value == "true"
          render()
        end,
      }),
    }
    if context.window_as_shown and not wallpaper and not shadow then
      table.insert(effects, ui.label({ text = "As shown on screen" }))
      table.insert(
        effects,
        ui.toggle({
          checked = asShown,
          enabled = not busy,
          onChange = function(value)
            asShown = value == "true"
            render()
          end,
        })
      )
    end
  end
  local status = recording.state or "idle"
  local active = status == "starting"
    or status == "recording"
    or status == "stopping"
    or status == "converting"
    or status == "selecting"
  local hint = ""
  if target == "display" then
    hint = "Select a screen"
  elseif target == "window" then
    if kind == "screenshot" then
      hint = "Select a window"
    else
      hint = "Select a window in the system picker. Match it to the audio application."
    end
  end
  local formats = ui.row({ gap = 8, align = "center" }, {
    ui.button({
      text = "Screenshot",
      glyph = "screenshot",
      selected = kind == "screenshot",
      enabled = not busy,
      onClick = function()
        setKind("screenshot")
      end,
    }),
    ui.button({
      text = "Video",
      glyph = "video",
      selected = kind == "record",
      enabled = not busy,
      onClick = function()
        setKind("record")
      end,
    }),
    ui.button({
      text = "GIF",
      glyph = "photo-video",
      selected = kind == "gif",
      enabled = not busy,
      onClick = function()
        setKind("gif")
      end,
    }),
  })
  panel.render(ui.column({ gap = 12, padding = 12 }, {
    ui.row({ gap = 16, align = "center" }, {
      formats,
      ui.row({ gap = 8, align = "center" }, modes),
      ui.spacer({ flexGrow = 1 }),
      ui.button({
        text = kind == "screenshot" and "Capture" or "Record",
        variant = "primary",
        enabled = not busy and (kind == "screenshot" or not active),
        onClick = "onCapture",
      }),
    }),
    ui.row({ gap = 8, align = "center", visible = #options > 0 }, options),
    ui.row({ gap = 8, align = "center", visible = #effects > 0 }, effects),
    ui.label({ text = hint, color = "on_surface_variant", visible = hint ~= "" }),
    ui.row({ gap = 8, align = "center", visible = active }, {
      ui.label({ text = status, flexGrow = 1 }),
      ui.button({
        text = "Stop recording",
        variant = "outline",
        enabled = active and status ~= "converting",
        onClick = "onStop",
      }),
    }),
  }))
end

function update()
  if polling or not visible or not noctalia.commandExists("nocapture-engine") then
    return
  end
  polling = true
  local accepted = noctalia.runAsync({ "nocapture-engine", "status" }, function(result)
    polling = false
    if result.exitCode == 0 then
      local value = noctalia.json.decode(result.stdout)
      if value then
        recording = value
      end
      if visible then
        render()
      end
    end
  end)
  if not accepted then
    polling = false
  end
end

function onOpen()
  generation = generation + 1
  closingForCapture = false
  busy = false
  visible = true
  render()
  panel.setWantsSecondTicks(true)
  local token = generation
  execute({ "nocapture-engine", "context" }, function(result)
    if token ~= generation then
      return
    end
    local value = noctalia.json.decode(result.stdout)
    if not value then
      errorMessage("Could not read capture targets.")
      return
    end
    context = value
    applicationIndex = 1
    render()
  end)
  update()
end

function onClose()
  visible = false
  if closingForCapture then
    closingForCapture = false
    return
  end
  generation = generation + 1
  busy = false
end

function onCapture()
  if busy then
    return
  end
  local command = actions.command({
    kind = kind,
    target = target,
    audio = audio,
    application = context.applications[applicationIndex],
    wallpaper = wallpaper,
    shadow = shadow,
    asShown = context.window_as_shown and asShown,
    directory = noctalia.getConfig(
      kind == "screenshot" and "screenshot_directory" or "recording_directory"
    ),
    padding = noctalia.getConfig("padding"),
    fps = noctalia.getConfig("fps"),
    gifFps = noctalia.getConfig("gif_fps"),
    gifWidth = noctalia.getConfig("gif_width"),
  })
  if not command then
    errorMessage("Select an audio application, or choose No audio.")
    return
  end
  if not noctalia.commandExists("nocapture-engine") then
    errorMessage("Install the Nocapture package so nocapture-engine is on Noctalia's PATH.")
    return
  end
  busy = true
  closingForCapture = true
  local token = generation
  local timeout = kind == "screenshot" and target == "window" and 60000 or nil
  panel.close()
  local accepted = noctalia.runAsync({ "sleep", "0.25" }, function(result)
    if token ~= generation then
      return
    end
    busy = false
    if result.exitCode ~= 0 then
      errorMessage("Capture delay failed. Try again.")
      return
    end
    execute(command, function(captured)
      local value = noctalia.json.decode(captured.stdout)
      if value and value.path and (value.state == nil or value.state == "saved") then
        noctalia.notify("Capture saved", value.path)
      end
    end, timeout)
  end)
  if not accepted then
    errorMessage("Could not start capture.")
  end
end

function onStop()
  execute({ "nocapture-engine", "stop" }, update)
end
