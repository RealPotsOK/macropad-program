#Requires AutoHotkey v2.0
#SingleInstance Force
#NoTrayIcon

commandFile := A_ScriptDir "\.profile_03_latch_command.txt"
serviceWindowTitle := "profile_03_latch_service.ahk ahk_class AutoHotkey"

DetectHiddenWindows(true)
if WinExist(serviceWindowTitle) {
    Try FileDelete(commandFile)
    FileAppend("stop`n", commandFile, "UTF-8-RAW")
    Sleep(150)
}

Try FileDelete(commandFile)

ExitApp
