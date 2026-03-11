#Requires AutoHotkey v2.0
#SingleInstance Ignore
#NoTrayIcon
#MaxThreadsPerHotkey 1

Persistent

global heldKeys := []
global isLatched := false
global commandFile := A_ScriptDir "\.profile_03_latch_command.txt"

SetTimer(CheckCommands, 25)
OnExit(ReleaseHeldKeys)
return

CheckCommands(*) {
    global commandFile
    if !FileExist(commandFile) {
        return
    }

    command := ""
    Try command := Trim(FileRead(commandFile))
    Try FileDelete(commandFile)
    command := StrLower(command)

    if (command = "toggle") {
        ToggleLatch()
        return
    }
    if (command = "activate") {
        ActivateLatch()
        return
    }
    if (command = "deactivate") {
        ReleaseHeldKeys(0, 0)
        return
    }
    if (command = "stop") {
        ReleaseHeldKeys(0, 0)
        ExitApp
    }
}

ToggleLatch() {
    global isLatched
    if isLatched {
        ReleaseHeldKeys(0, 0)
        return
    }
    ActivateLatch()
}

ActivateLatch() {
    global heldKeys, isLatched
    if isLatched {
        return
    }

    heldKeys := CapturePressedKeys()
    if heldKeys.Length = 0 {
        return
    }

    for keyName in heldKeys {
        SendInput("{" keyName " down}")
        Try Hotkey("*" keyName " Up", ReassertHeldKey, "On")
    }

    isLatched := true
}

CapturePressedKeys() {
    keys := []
    for keyName in GetWatchKeys() {
        if (keyName = "F12") {
            continue
        }
        if GetKeyState(keyName, "P") {
            keys.Push(keyName)
        }
    }
    return keys
}

ReassertHeldKey(thisHotkey) {
    global isLatched
    if !isLatched {
        return
    }

    keyName := RegExReplace(SubStr(thisHotkey, 2), "\s+Up$")
    SendInput("{" keyName " down}")
}

ReleaseHeldKeys(exitReason := 0, exitCode := 0) {
    global heldKeys, isLatched
    if !isLatched {
        return
    }

    for keyName in heldKeys {
        Try Hotkey("*" keyName " Up", ReassertHeldKey, "Off")
    }

    Loop heldKeys.Length {
        keyName := heldKeys[heldKeys.Length - A_Index + 1]
        Try SendInput("{" keyName " up}")
    }

    heldKeys := []
    isLatched := false
}

GetWatchKeys() {
    static watchKeys := BuildWatchKeys()
    return watchKeys
}

BuildWatchKeys() {
    keys := [
        "LButton", "RButton", "MButton", "XButton1", "XButton2",
        "Space", "Tab", "Enter", "Escape", "Backspace",
        "Up", "Down", "Left", "Right",
        "Home", "End", "PgUp", "PgDn", "Insert", "Delete",
        "LShift", "RShift", "LControl", "RControl", "LAlt", "RAlt", "LWin", "RWin",
        "CapsLock", "NumLock", "ScrollLock", "PrintScreen", "Pause",
        "Numpad0", "Numpad1", "Numpad2", "Numpad3", "Numpad4",
        "Numpad5", "Numpad6", "Numpad7", "Numpad8", "Numpad9",
        "NumpadDot", "NumpadDiv", "NumpadMult", "NumpadAdd", "NumpadSub", "NumpadEnter"
    ]

    for keyChar in StrSplit("ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
        keys.Push(keyChar)
    }

    Loop 10 {
        keys.Push(Mod(A_Index, 10))
    }

    Loop 24 {
        keys.Push("F" A_Index)
    }

    return keys
}

