#Requires AutoHotkey v2.0
#SingleInstance Force
#NoTrayIcon

serviceScript := A_ScriptDir "\profile_03_latch_service.ahk"
commandFile := A_ScriptDir "\.profile_03_latch_command.txt"
serviceWindowTitle := "profile_03_latch_service.ahk ahk_class AutoHotkey"

DetectHiddenWindows(true)
windows := WinGetList(serviceWindowTitle)
if windows.Length > 1 {
    for hwnd in windows {
        Try WinClose("ahk_id " hwnd)
    }
    Sleep(150)
}

if !WinExist(serviceWindowTitle) && FileExist(serviceScript) {
    Try Run('"' A_AhkPath '" "' serviceScript '"',, "Hide")
    Sleep(120)
}

Try FileDelete(commandFile)
FileAppend("toggle`n", commandFile, "UTF-8-RAW")

ExitApp
