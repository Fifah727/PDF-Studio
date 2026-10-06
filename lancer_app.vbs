Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = "H:\PROJECTS\pdf_manip_flet"
WshShell.Run "python main.py", 0, False