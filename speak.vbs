Set Sapi = CreateObject("SAPI.SpVoice")
Set Voices = Sapi.GetVoices

' ค้นหาเสียงภาษาไทย
For i = 0 To Voices.Count - 1
    If InStr(Voices.Item(i).GetDescription, "Thai") > 0 Then
        Set Sapi.Voice = Voices.Item(i)
        Exit For
    End If
Next

Sapi.Volume = 100
Sapi.Rate = 0
Sapi.Speak WScript.Arguments(0)
