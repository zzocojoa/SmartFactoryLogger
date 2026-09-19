& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $root='C:\Users\user\Desktop\SmartFactory'
    $zipPath=$root+'\v1025-cold-backup-restore-ready.zip'
    $expected='FAA801888AB58FED5D08C55CCB5DF616DAF28D29A753F594B83A2F88457801EF'
    $pins=[Collections.Generic.List[IDisposable]]::new();$archive=$null;$destination=$null
    function PlainLaunch {
        param([string]$Path)
        $node=[IO.FileInfo]::new([IO.Path]::GetFullPath($Path));$stack=[Collections.Generic.List[string]]::new()
        while($null -ne $node){$stack.Add($node.FullName);if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}}
        for($i=$stack.Count-1;$i -ge 0;$i--){if(([IO.File]::GetAttributes($stack[$i]) -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse transfer path rejected.'}}
    }
    function LaunchHash {
        param([IO.Stream]$Stream)
        $sha=[Security.Cryptography.SHA256]::Create()
        try{$Stream.Position=0;return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')}finally{$sha.Dispose()}
    }
    function ExtractNew {
        param([IO.Compression.ZipArchive]$Archive,[string]$Directory,[Collections.Generic.List[IDisposable]]$Pins)
        $files=@{
            'backup-restore-v1025.ps1'=@(26448,'E5A5CF167F79E75898BCAFFEA72545A091FD954C95361440180287F2129DE161')
            'backup-restore-v1025.ps1.sha256.txt'=@(65,'7B7BA03ED8C644AE35176667D36D1BC5A159D11F928E61341E275EB1179CCF0F')
            'cold-backup-core.dll'=@(19456,'3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71')
            'cold-backup-core.dll.sha256.txt'=@(65,'9BA88479B736E801D771569AA3B0C49C950A9439F925FF37A6FFC92E2E0466A5')
            'COLD_BACKUP_GUIDE.md'=@(7390,'F812B7B40CA7A55854868AD317E37857146096F17A8781F46AF5FA16D48E68F7')
        }
        if($Archive.Entries.Count -ne 5){throw 'Archive membership differs.'}
        $payloads=@{}
        foreach($entry in $Archive.Entries){
            if($entry.FullName -cnotin @($files.Keys) -or $payloads.ContainsKey($entry.FullName) -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000 -or ($entry.ExternalAttributes -band 0x400) -ne 0){throw 'Unapproved archive entry.'}
            $spec=$files[$entry.FullName]
            if($entry.Length -ne $spec[0]){throw 'Archive length differs.'}
            $s=$entry.Open();$b=[IO.MemoryStream]::new()
            try{
                $chunk=New-Object byte[] 8192
                while(($n=$s.Read($chunk,0,$chunk.Length)) -gt 0){if($b.Length+$n -gt $spec[0]){throw 'Entry expansion exceeds pin.'};$b.Write($chunk,0,$n)}
                if($b.Length -ne $spec[0] -or (LaunchHash $b) -cne $spec[1]){throw 'Entry bytes differ.'}
                $payloads[$entry.FullName]=$b.ToArray()
            }finally{$s.Dispose();$b.Dispose()}
        }
        PlainLaunch ([IO.Path]::GetDirectoryName($Directory))
        if([IO.File]::Exists($Directory) -or [IO.Directory]::Exists($Directory)){throw 'Existing extraction preserved.'}
        [void][IO.Directory]::CreateDirectory($Directory);PlainLaunch $Directory
        foreach($name in @($files.Keys)){
            $path=Join-Path $Directory $name;$bytes=$payloads[$name]
            $s=[IO.File]::Open($path,'CreateNew','Write','None')
            try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
            PlainLaunch $path;$s=[IO.File]::Open($path,'Open','Read','Read');$Pins.Add($s)
            if($s.Length -ne $files[$name][0] -or (LaunchHash $s) -cne $files[$name][1]){throw 'Extracted bytes differ.'}
        }
    }
    try{
        $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
        $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
            $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
            [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
            -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use administrator native x64 Windows PowerShell 5.1.'}
        PlainLaunch $zipPath;PlainLaunch ($zipPath+'.sha256.txt')
        $lines=@([IO.File]::ReadAllLines($zipPath+'.sha256.txt'))
        if($lines.Count -ne 1 -or $lines[0] -cne $expected){throw 'Transfer sidecar differs from external pin.'}
        $held=[IO.File]::Open($zipPath,'Open','Read','Read');$pins.Add($held)
        if($held.Length -ne 22383 -or (LaunchHash $held) -cne $expected){throw 'Transfer SHA256/length mismatch.'}
        Add-Type -AssemblyName System.IO.Compression
        $held.Position=0;$archive=[IO.Compression.ZipArchive]::new($held,'Read',$true)
        $destination=$root+'\v1025-cold-backup-'+[Guid]::NewGuid().ToString('N')
        ExtractNew $archive $destination $pins
        Write-Host '[VERIFIED] Backup helper extracted into a new folder. Read the capacity and maintenance instructions. No installer will run.' -ForegroundColor Green
        & $native -NoLogo -NoProfile -ExecutionPolicy Bypass -File ($destination+'\backup-restore-v1025.ps1') -Execute
        if($LASTEXITCODE -ne 0){throw 'Backup helper HOLD. Preserve the complete output.'}
    }catch{
        Write-Host '[HOLD] Preserve output and partial files. No automatic retry, cleanup, restart, rollback or installation.' -ForegroundColor Yellow
        throw
    }finally{
        if($null -ne $archive){$archive.Dispose()}
        foreach($pin in $pins){$pin.Dispose()}
    }
}
