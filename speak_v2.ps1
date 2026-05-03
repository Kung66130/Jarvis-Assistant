param(
    [Parameter(Mandatory=$true)]
    [string]$Text
)

# ใช้ Windows.Media.SpeechSynthesis (Modern API)
Add-Type -AssemblyName "System.Runtime.WindowsRuntime"
$asb = [System.Reflection.Assembly]::LoadWithPartialName("System.Runtime.WindowsRuntime")

# ใช้สคริปต์ PowerShell ในการเรียก WinRT API แบบตรงไปตรงมา
$code = @'
using System;
using System.Linq;
using System.Threading.Tasks;
using Windows.Media.SpeechSynthesis;
using Windows.Media.Playback;
using Windows.Storage.Streams;

public class ModernSpeaker {
    public static async Task Speak(string text) {
        using (var synth = new SpeechSynthesizer()) {
            // ค้นหาเสียงภาษาไทย
            var voice = SpeechSynthesizer.AllVoices.FirstOrDefault(v => v.Language.Contains("th-TH"));
            if (voice != null) synth.Voice = voice;

            var stream = await synth.SynthesizeTextToStreamAsync(text);
            var player = new MediaPlayer();
            player.Source = MediaSource.CreateFromStream(stream, stream.ContentType);
            player.Play();
            
            // รอให้พูดจบ (ประมาณการจากความยาวข้อความ)
            System.Threading.Thread.Sleep(text.Length * 200 + 1000);
        }
    }
}
'@

# หมายเหตุ: การเรียก WinRT ผ่าน PowerShell โดยตรงอาจจะซับซ้อน 
# เราจะใช้วิธีที่ง่ายกว่าคือการใช้คำสั่ง "voice" ผ่าน C# snippet เล็กๆ
# แต่เพื่อความรวดเร็ว ผมจะลองใช้คำสั่งมาตรฐานอีกตัวที่มักจะเข้าถึงเสียงใหม่ๆ ได้ครับ

$speak = New-Object -ComObject SAPI.SpVoice
$speak.Volume = 100
$speak.Rate = 0
$speak.Speak($Text)
