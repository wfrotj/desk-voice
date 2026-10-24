Set shell = CreateObject("Wscript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder

launcher = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe")
If files.FileExists(launcher) Then
  shell.Run """" & launcher & """ -3 server.py", 0, False
Else
  shell.Run "pyw.exe -3 server.py", 0, False
End If
