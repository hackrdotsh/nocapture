local actions = require("./actions.luau")
local kind = "screenshot"
local target = "region"
local busy = false
local generation = 0
local closingForCapture = false

local function render()
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
          target = id
          render()
        end,
      })
    )
  end

  panel.render(ui.column({ gap = 12, padding = 12 }, {
    ui.row({ gap = 8, align = "center" }, {
      ui.label({ text = "Nocapture", fontWeight = "bold", flexGrow = 1 }),
      ui.button({
        text = "Screenshot",
        selected = kind == "screenshot",
        enabled = not busy,
        onClick = "onScreenshot",
      }),
      ui.button({
        text = "Record",
        selected = kind == "record",
        enabled = not busy,
        onClick = "onRecord",
      }),
      ui.button({ text = "Close", variant = "ghost", onClick = "onDismiss" }),
    }),
    ui.row({ gap = 8, align = "center" }, modes),
    ui.row({ gap = 8, align = "center" }, {
      ui.label({
        text = kind == "record" and target == "window" and "Choose a window in the system picker."
          or "",
        flexGrow = 1,
      }),
      ui.button({
        text = "Stop recording",
        variant = "outline",
        enabled = not busy,
        onClick = "onStop",
      }),
      ui.button({
        text = kind == "record" and "Record" or "Capture",
        variant = "primary",
        enabled = not busy,
        onClick = "onCapture",
      }),
    }),
  }))
end

local function fail(message)
  busy = false
  render()
  noctalia.notifyError("Nocapture", message)
end

local function run(command)
  if
    not noctalia.runAsync(command, function(result)
      if result.exitCode ~= 0 then
        local message = result.stderr
        if message == nil or message == "" then
          message = "Check the Noctalia log and try again."
        end
        noctalia.notifyError("Capture command failed", message)
      end
    end)
  then
    noctalia.notifyError("Nocapture", "Could not launch " .. command[1] .. ".")
  end
end

local function captureAfterClose(command, token)
  closingForCapture = true
  panel.close()
  -- Let the layer surface disappear before sampling the desktop or opening a picker.
  if
    not noctalia.runAsync({ "sleep", "0.25" }, function(result)
      if token ~= generation then
        return
      end
      busy = false
      if result.exitCode == 0 then
        run(command)
      else
        noctalia.notifyError("Nocapture", "Capture delay failed. Try again.")
      end
    end)
  then
    fail("Could not start the capture delay. Check that sleep is available.")
  end
end

function onOpen()
  generation = generation + 1
  closingForCapture = false
  busy = false
  render()
end

function onClose()
  if closingForCapture then
    closingForCapture = false
    return
  end
  generation = generation + 1
  busy = false
end

function onDismiss()
  generation = generation + 1
  busy = false
  panel.close()
end

function onScreenshot()
  kind = "screenshot"
  render()
end

function onRecord()
  kind = "record"
  render()
end

function onCapture()
  if busy then
    return
  end
  local command = actions.command(kind, target)
  if not noctalia.commandExists(command[1]) then
    fail("Install " .. command[1] .. " to use this capture mode.")
    return
  end
  busy = true
  render()
  local token = generation
  if kind == "screenshot" then
    captureAfterClose(command, token)
    return
  end
  if not noctalia.commandExists("gpu-screen-recorder") then
    fail("Install gpu-screen-recorder to enable recording.")
    return
  end
  if target == "region" and not noctalia.commandExists("slurp") then
    fail("Install slurp to select a recording region.")
    return
  end
  if
    not noctalia.runAsync({ "noctalia", "msg", "plugins", "list" }, function(result)
      if token ~= generation then
        return
      end
      if result.exitCode ~= 0 then
        fail("Could not query Noctalia plugins. Check that Noctalia is running.")
      elseif not actions.recorderEnabled(result.stdout or "") then
        fail("Enable noctalia/screen_recorder in Noctalia's plugin settings.")
      else
        captureAfterClose(command, token)
      end
    end)
  then
    fail("Could not query Noctalia plugins. Try again.")
  end
end

function onStop()
  run(actions.stopCommand())
end
