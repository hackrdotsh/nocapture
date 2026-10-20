local root = "nocapture/"
local actions = dofile(root .. "actions.luau")
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
  local h = { calls = {}, errors = {}, queue = {}, missing = {} }
  local env = setmetatable({}, { __index = _G })
  env.require = function(path)
    equal(path, "./actions.luau")
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
  }
  env.noctalia = {
    commandExists = function(name)
      return not h.missing[name]
    end,
    notifyError = function(title, body)
      table.insert(h.errors, title .. ": " .. body)
    end,
    runAsync = function(argv, callback)
      table.insert(h.calls, command(argv))
      if h.reject then
        return false
      end
      table.insert(h.queue, callback)
      return true
    end,
  }
  assert(loadfile(root .. "toolbar.luau", "t", env))()
  h.env = env
  function h:complete(result)
    table.remove(self.queue, 1)(result or { exitCode = 0 })
  end
  function h:click(label)
    local function find(node)
      if node.type == "button" and node.props.text == label then
        return node.props.onClick
      end
      for _, child in ipairs(node.children) do
        local found = find(child)
        if found then
          return found
        end
      end
    end
    local callback = assert(find(self.tree), label)
    if type(callback) == "string" then
      self.env[callback]()
    else
      callback()
    end
  end
  env.onOpen()
  return h
end

test("routes every capture mode", function()
  local expected = {
    screenshot = {
      region = "noctalia msg screenshot-region",
      display = "noctalia msg screenshot-fullscreen pick",
      window = "niri msg action screenshot-window",
    },
    record = {
      region = "noctalia msg plugin noctalia/screen_recorder:service all start region",
      display = "noctalia msg plugin noctalia/screen_recorder:service all start focused",
      window = "noctalia msg plugin noctalia/screen_recorder:service all start portal",
    },
  }
  for kind, targets in pairs(expected) do
    for target, argv in pairs(targets) do
      equal(command(actions.command(kind, target)), argv)
    end
  end
  equal(actions.command("shell", "region"), nil)
  equal(actions.command("record", "region; bad"), nil)
end)

test("recognizes only enabled recorder entries", function()
  equal(actions.recorderEnabled("noctalia/screen_recorder [official] 1.3.6 enabled\n"), true)
  equal(actions.recorderEnabled("noctalia/screen_recorder [official] 1.3.6 disabled"), false)
  equal(actions.recorderEnabled("other/plugin [official] 1.3.6 enabled"), false)
end)

test("opens without capturing and closes before delayed capture", function()
  local h = host()
  equal(#h.calls, 0)
  h:click("Capture")
  equal(h.calls[1], "close")
  equal(h.calls[2], "sleep 0.25")
  h:click("Capture")
  equal(#h.calls, 2)
  h:complete()
  equal(h.calls[3], "noctalia msg screenshot-region")
end)

test("window selection uses Niri", function()
  local h = host()
  h:click("Window")
  h:click("Capture")
  h:complete()
  equal(h.calls[3], "niri msg action screenshot-window")
end)

test("missing window tool leaves toolbar open", function()
  local h = host()
  h.missing.niri = true
  h:click("Window")
  h:click("Capture")
  equal(#h.calls, 0)
  equal(#h.errors, 1)
end)

test("recording requires native engine and region picker", function()
  for _, missing in ipairs({ "gpu-screen-recorder", "slurp" }) do
    local h = host()
    h.missing[missing] = true
    h:click("Record")
    h:click("Record")
    h.env.onCapture()
    equal(#h.calls, 0)
    equal(#h.errors, 1)
  end
end)

test("disabled recorder does not close or start capture", function()
  local h = host()
  h.env.onRecord()
  h.env.onCapture()
  h:complete({ exitCode = 0, stdout = "noctalia/screen_recorder [official] 1.3.6 disabled" })
  equal(#h.calls, 1)
  equal(#h.errors, 1)
end)

test("enabled recorder launches selected source after close", function()
  local h = host()
  h.env.onRecord()
  h:click("Display")
  h.env.onCapture()
  h:complete({ exitCode = 0, stdout = "noctalia/screen_recorder [official] 1.3.6 enabled" })
  equal(h.calls[2], "close")
  equal(h.calls[3], "sleep 0.25")
  h:complete()
  equal(h.calls[4], "noctalia msg plugin noctalia/screen_recorder:service all start focused")
end)

test("reopening invalidates a pending capture", function()
  local h = host()
  h.env.onCapture()
  h.env.onOpen()
  h:complete()
  equal(#h.calls, 2)
end)

test("dismiss invalidates recorder preflight", function()
  local h = host()
  h.env.onRecord()
  h.env.onCapture()
  h.env.onDismiss()
  h:complete({ exitCode = 0, stdout = "noctalia/screen_recorder [official] 1.3.6 enabled" })
  equal(#h.calls, 2)
end)

test("outside dismissal invalidates recorder preflight", function()
  local h = host()
  h.env.onRecord()
  h.env.onCapture()
  h.env.onClose()
  h:complete({ exitCode = 0, stdout = "noctalia/screen_recorder [official] 1.3.6 enabled" })
  equal(#h.calls, 1)
end)

test("capture-triggered close preserves the delayed capture", function()
  local h = host()
  h.env.onCapture()
  h.env.onClose()
  h:complete()
  equal(h.calls[3], "noctalia msg screenshot-region")
end)

test("failed launches and nonzero exits surface errors", function()
  local h = host()
  h.reject = true
  h.env.onCapture()
  equal(#h.errors, 1)
  h = host()
  h.env.onCapture()
  h:complete()
  h:complete({ exitCode = 1, stderr = "Capture unavailable" })
  equal(h.errors[1], "Capture command failed: Capture unavailable")
end)

test("stop delegates to the recorder owner", function()
  local h = host()
  h.env.onStop()
  equal(h.calls[1], command(actions.stopCommand()))
end)

print(string.format("%d plugin tests passed", passed))
