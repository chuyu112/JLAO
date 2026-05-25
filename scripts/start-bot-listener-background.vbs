Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
psFile = scriptDir & "\start-bot-listener.ps1"

WshShell.Run "powershell -WindowStyle Hidden -File """ & psFile & """"", 0, False

MsgBox "Bot listener started in background." & vbCrLf & "Log: JLAO\logs\bot-listener.log", vbInformation, "Feishu Bot"
