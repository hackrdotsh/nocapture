local actions = dofile("nocapture/actions.luau")
local passed = 0
local function equal(actual, expected)
  assert(
    actual == expected,
    string.format("Expected %s, got %s", tostring(expected), tostring(actual))
  )
end
local function command(value)
  return table.concat(value, " ")
end
local function test(name, callback)
  callback()
  passed = passed + 1
  print("ok - " .. name)
end

local function host()
  local h = { calls = {}, queue = {}, errors = {}, missing = false }
  local config = {
    screenshot_directory = "~/Pictures/Nocapture",
    recording_directory = "~/Videos/Nocapture",
    padding = 96,
    fps = 30,
    gif_fps = 15,
    gif_width = 1280,
  }
  local data = {
    context = {
      outputs = { "DP-1" },
      focused_output = "DP-1",
      applications = { "Music app" },
      windows = { { id = 42, title = "Editor", is_focused = true } },
    },
    status = { state = "idle" },
    result = { path = "/saved/capture.png" },
  }
  local env = setmetatable({}, { __index = _G })
  env.require = function()
    return actions
  end
  env.ui = setmetatable({}, {
    __index = function(_, name)
      return function(props, children)
        return { type = name, props = props, children = children or {} }
      end
    end,
  })
  env.panel = {
    render = function(tree)
      h.tree = tree
    end,
    close = function()
      table.insert(h.calls, "close")
    end,
    setWantsSecondTicks = function() end,
  }
  env.noctalia = {
    commandExists = function()
      return not h.missing
    end,
    getConfig = function(key)
      return assert(config[key], key)
    end,
    json = {
      decode = function(value)
        return data[value]
      end,
    },
    notify = function() end,
    notifyError = function(_, body)
      table.insert(h.errors, body)
    end,
    runAsync = function(argv, callback)
      table.insert(h.calls, command(argv))
      if h.reject then
        return false
      end
      table.insert(h.queue, { callback = callback, argv = argv })
      return true
    end,
  }
  assert(loadfile("nocapture/toolbar.luau", "t", env))()
  function h:complete(result)
    local pending = table.remove(self.queue, 1)
    pending.callback(result or { exitCode = 0, stdout = pending.argv[2] })
  end
  function h:find(kind, label)
    local function find(node)
      if
        node.type == kind
        and (node.props.text == label or node.props.options and node.props.options[1] == label)
      then
        return node.props
      end
      for _, child in ipairs(node.children) do
        local found = find(child)
        if found then
          return found
        end
      end
    end
    return assert(find(self.tree), label)
  end
  function h:click(label)
    local callback = self:find("button", label).onClick
    if type(callback) == "string" then
      env[callback]()
    else
      callback()
    end
  end
  h.env = env
  env.onOpen()
  h:complete({ exitCode = 0, stdout = "context" })
  h:complete({ exitCode = 0, stdout = "status" })
  h.calls = {}
  return h
end

test("all targets route screenshots, video, and GIF to the backend", function()
  for _, target in ipairs({ "region", "window", "display" }) do
    for _, kind in ipairs({ "screenshot", "record", "gif" }) do
      local value = actions.command({ kind = kind, target = target })
      equal(value[1], "nocapture-engine")
      equal(value[2], kind == "screenshot" and "screenshot" or "record")
      equal(value[3], target)
    end
  end
  equal(actions.command({ kind = "shell", target = "region" }), nil)
  equal(actions.command({ kind = "record", target = "invalid" }), nil)
end)

test("GIF cannot accidentally capture audio", function()
  local value = command(actions.command({ kind = "gif", target = "display", audio = "system" }))
  assert(value:find("--format gif --audio none", 1, true))
end)

test("window recording requires isolated application audio or silence", function()
  equal(actions.command({ kind = "record", target = "window", audio = "system" }), nil)
  equal(actions.command({ kind = "record", target = "window", audio = "application" }), nil)
  local value = actions.command({
    kind = "record",
    target = "window",
    audio = "application",
    application = "Music app",
  })
  equal(value[9], "Music app")
end)

test("wallpaper, shadow, and exact window id are passed without shell parsing", function()
  local value = command(actions.command({
    kind = "screenshot",
    target = "window",
    windowId = 42,
    wallpaper = true,
    shadow = true,
    padding = 80,
  }))
  assert(value:find("--window-id 42 --wallpaper --shadow --padding 80", 1, true))
end)

test("opening only reads context and status", function()
  local h = host()
  equal(#h.calls, 0)
end)

test("capture closes first and prevents duplicate clicks", function()
  local h = host()
  h:click("Capture")
  h:click("Capture")
  equal(#h.calls, 2)
  equal(h.calls[1], "close")
  equal(h.calls[2], "sleep 0.25")
  h.env.onClose()
  h:complete()
  assert(h.calls[3]:find("nocapture-engine screenshot region", 1, true))
end)

test("window screenshot uses the selected window", function()
  local h = host()
  h:click("Window")
  h:click("Capture")
  h:complete()
  assert(h.calls[3]:find("--window-id 42", 1, true))
end)

test("video audio choice and GIF mode reach the backend", function()
  local h = host()
  h:click("Video")
  h:find("select", "No audio").onChange("1")
  h:click("Record")
  h:complete()
  assert(h.calls[3]:find("--audio system", 1, true))
  h = host()
  h:click("GIF")
  h:click("Record")
  h:complete()
  assert(h.calls[3]:find("--format gif --audio none", 1, true))
end)

test("missing backend keeps toolbar open with an actionable error", function()
  local h = host()
  h.missing = true
  h:click("Capture")
  equal(#h.calls, 0)
  equal(#h.errors, 1)
end)

test("reopening invalidates delayed capture", function()
  local h = host()
  h:click("Capture")
  h.env.onOpen()
  local before = #h.calls
  h:complete()
  equal(#h.calls, before)
end)

test("stop targets only Nocapture's worker", function()
  local h = host()
  h.env.onStop()
  equal(h.calls[1], "nocapture-engine stop")
end)

test("failed launches and backend exits surface errors", function()
  local h = host()
  h.reject = true
  h:click("Capture")
  equal(#h.errors, 1)
  h = host()
  h:click("Capture")
  h:complete()
  h:complete({ exitCode = 1, stderr = "No wallpaper" })
  equal(h.errors[1], "No wallpaper")
end)

print(string.format("%d plugin tests passed", passed))
