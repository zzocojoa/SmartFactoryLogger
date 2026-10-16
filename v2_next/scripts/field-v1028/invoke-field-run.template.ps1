[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRequestSha256,
    [Parameter(Mandatory=$true)][string]$ResultParent,
    [Parameter(Mandatory=$true)][ValidatePattern('^S-1-5-21-[0-9-]+$')][string]$OperatorSid
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$fieldRunManifestSha256='@@MANIFEST_SHA256@@'

function Assert-RunCondition([bool]$Value,[string]$Reason) { if(-not $Value){throw $Reason} }
function Get-RunPath([string]$Path) {
    Assert-RunCondition ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path -notmatch '[\x00-\x1f]') 'absolute-local-path'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')
    Assert-RunCondition ($full.Length -gt 3 -and $full.Length -le 240 -and $full.Substring(2) -notmatch ':') 'path-budget-or-stream'
    $node=[IO.FileInfo]::new($full)
    while($null -ne $node){
        Assert-RunCondition ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function Get-RunHash([IO.Stream]$Stream) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()}
    finally{$sha.Dispose()}
}
function New-RunAcl([string]$ReaderSid) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($sid in @('S-1-5-32-544','S-1-5-18',$ReaderSid)){
        $rights=if($sid -ceq $ReaderSid){'ReadAndExecute'}else{'FullControl'}
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid),$rights,'ContainerInherit,ObjectInherit','None','Allow'))
    }
    return $acl
}
function Assert-RunAcl([string]$Path,[string]$ReaderSid) {
    $actual=[IO.Directory]::GetAccessControl((Get-RunPath $Path))
    $expected=New-RunAcl $ReaderSid
    Assert-RunCondition ($actual.AreAccessRulesProtected -and $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'result-owner-inheritance'
    $rules=@($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Assert-RunCondition ($rules.Count -eq 3) 'result-rule-count'
    $seen=@{}
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value
        $matches=@($expected.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|Where-Object{$_.IdentityReference.Value -ceq $sid})
        Assert-RunCondition ($matches.Count -eq 1 -and -not $seen.ContainsKey($sid)) 'result-rule-sid'
        Assert-RunCondition (-not $rule.IsInherited -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq $matches[0].FileSystemRights -and $rule.InheritanceFlags -eq $matches[0].InheritanceFlags -and $rule.PropagationFlags -eq 'None') 'result-rule-rights'
        $seen[$sid]=$true
    }
}
function Write-RunJson([string]$Path,$Value) {
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 30))
    $stream=[IO.File]::Open((Get-RunPath $Path),'CreateNew','Write','None')
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Get-RunFact([string]$Path) {
    $stream=[IO.File]::Open((Get-RunPath $Path),'Open','Read','Read')
    try{return [ordered]@{bytes=$stream.Length;sha256=(Get-RunHash $stream)}}finally{$stream.Dispose()}
}
function Test-RunOutput([string]$Directory,[string]$RequestSha256,[bool]$ChildPassed) {
    $session=Get-RunPath ($Directory+'\session')
    $manifestPath=Get-RunPath ($session+'\manifest.json')
    $manifestFact=Get-RunFact $manifestPath
    Assert-RunCondition ($manifestFact.bytes -le 64MB) 'result-manifest-budget'
    $manifest=[IO.File]::ReadAllText($manifestPath,[Text.UTF8Encoding]::new($false,$true))|ConvertFrom-Json
    Assert-RunCondition ($manifest.schema -ceq 'sfl-field-run-files-v1' -and $manifest.release_gate -ceq 'HOLD' -and $manifest.promotion_allowed -is [bool] -and -not $manifest.promotion_allowed) 'result-manifest-scope'
    $expected=@{}
    foreach($item in $manifest.files.PSObject.Properties){
        $name=$item.Name
        Assert-RunCondition ($name.Length -le 240 -and $name -notmatch '[\\:\x00-\x1f]' -and -not $name.StartsWith('/') -and @($name.Split('/')|Where-Object{$_ -in @('','.','..')}).Count -eq 0 -and -not $expected.ContainsKey($name)) 'result-member-path'
        $path=Get-RunPath ($session+'\'+$name.Replace('/','\'))
        Assert-RunCondition ($path.StartsWith($session+'\',[StringComparison]::OrdinalIgnoreCase)) 'result-member-boundary'
        $fact=Get-RunFact $path
        Assert-RunCondition ($fact.bytes -eq $item.Value.bytes -and $fact.sha256 -ceq $item.Value.sha256) 'result-member-fact'
        $expected[$name]=$true
    }
    $pending=[Collections.Generic.Queue[string]]::new();$pending.Enqueue($session)
    $seen=@{};$count=0
    while($pending.Count -gt 0){
        foreach($path in [IO.Directory]::GetFileSystemEntries($pending.Dequeue())){
            $count++;Assert-RunCondition ($count -le 1000000) 'result-tree-budget'
            $path=Get-RunPath $path
            if(([IO.File]::GetAttributes($path) -band [IO.FileAttributes]::Directory) -ne 0){$pending.Enqueue($path)}
            elseif($path -ine $manifestPath){$name=$path.Substring($session.Length+1).Replace('\','/');Assert-RunCondition ($expected.ContainsKey($name) -and -not $seen.ContainsKey($name)) 'result-extra-file';$seen[$name]=$true}
        }
    }
    Assert-RunCondition ($seen.Count -eq $expected.Count) 'result-member-count'
    $resultPath=$session+'\result.json'
    Assert-RunCondition (([IO.FileInfo]::new($resultPath)).Length -le 64MB) 'runner-result-budget'
    $result=[IO.File]::ReadAllText($resultPath,[Text.UTF8Encoding]::new($false,$true))|ConvertFrom-Json
    Assert-RunCondition ($result.schema -ceq 'sfl-field-run-result-v1' -and $result.request_sha256 -ceq $RequestSha256 -and $result.frozen -is [bool] -and $result.frozen) 'runner-result-binding'
    Assert-RunCondition ($result.status -ceq $(if($ChildPassed){'PASS'}else{'FAIL'}) -and $result.release_gate -ceq 'HOLD' -and $result.promotion_allowed -is [bool] -and -not $result.promotion_allowed) 'runner-result-scope'
    Assert-RunCondition ((Get-RunFact $manifestPath).sha256 -ceq $manifestFact.sha256) 'result-manifest-changed'
    return [ordered]@{status='PASS';scope='RUNNER_OUTPUT_BYTES';file_count=$seen.Count;manifest=$manifestFact;phase_status=$result.status}
}
function Initialize-RunNative {
    if('SflOwnedRun' -as [type]){return}
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
public sealed class SflOwnedRun : IDisposable {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct SI { public int cb; public string reserved, desktop, title; public uint x,y,xs,ys,xc,yc,fill,flags;
        public ushort show, reservedCount; public IntPtr reservedBytes, input, output, error; }
    [StructLayout(LayoutKind.Sequential)] struct SIX { public SI startup; public IntPtr attributes; }
    [StructLayout(LayoutKind.Sequential)] struct PI { public IntPtr process, thread; public uint pid, tid; }
    [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)] static extern IntPtr CreateJobObjectW(IntPtr a,string n);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr h,int c,IntPtr p,int n);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr h,int c,IntPtr p,int n,IntPtr r);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr j,IntPtr p);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateJobObject(IntPtr j,uint c);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateProcess(IntPtr p,uint c);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetHandleInformation(IntPtr h,uint m,uint f);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool InitializeProcThreadAttributeList(IntPtr p,int c,int f,ref IntPtr s);
    [DllImport("kernel32.dll")] static extern void DeleteProcThreadAttributeList(IntPtr p);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool UpdateProcThreadAttribute(IntPtr p,uint f,IntPtr a,IntPtr v,IntPtr s,IntPtr x,IntPtr y);
    [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)] static extern bool CreateProcessW(string app,StringBuilder cmd,IntPtr pa,IntPtr ta,bool inherit,uint flags,IntPtr env,string cwd,ref SIX si,out PI pi);
    [DllImport("kernel32.dll",SetLastError=true)] static extern uint ResumeThread(IntPtr h);
    [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr h,uint ms);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr h,out uint code);
    [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,uint pid);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool IsProcessInJob(IntPtr p,IntPtr j,out bool member);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr p,out long created,out long exited,out long kernel,out long user);
    [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)] static extern bool QueryFullProcessImageNameW(IntPtr p,uint flags,StringBuilder name,ref uint size);
    IntPtr job, process;
    long rootCreated;
    string rootExecutable;
    FileStream stdout, stderr, stdin;
    public uint Pid {get; private set;}
    static void Check(bool ok){if(!ok)throw new Win32Exception(Marshal.GetLastWin32Error());}
    public static string Quote(string value){
        if(value.IndexOf('\0')>=0)throw new ArgumentException("NUL argument");
        StringBuilder b=new StringBuilder("\""); int slashes=0;
        foreach(char c in value){if(c=='\\'){slashes++;continue;}
            b.Append('\\', c=='"'?slashes*2+1:slashes); b.Append(c);slashes=0;}
        b.Append('\\',slashes*2);b.Append('"');return b.ToString();
    }
    public SflOwnedRun(string exe,string[] args,string environment,string cwd,string outPath,string errPath){
        if(IntPtr.Size!=8 || Marshal.SizeOf(typeof(SIX))!=112)throw new InvalidOperationException("x64 startup ABI");
        IntPtr limits=IntPtr.Zero, attrs=IntPtr.Zero, handles=IntPtr.Zero, env=IntPtr.Zero;
        PI pi=new PI(); bool initialized=false, assigned=false;
        try{
            job=CreateJobObjectW(IntPtr.Zero,null);Check(job!=IntPtr.Zero);
            limits=Marshal.AllocHGlobal(144);Marshal.Copy(new byte[144],0,limits,144);Marshal.WriteInt32(limits,16,0x2000);
            Check(SetInformationJobObject(job,9,limits,144));
            stdout=new FileStream(outPath,FileMode.CreateNew,FileAccess.Write,FileShare.Read);
            stderr=new FileStream(errPath,FileMode.CreateNew,FileAccess.Write,FileShare.Read);
            string emptyInput=Path.Combine(cwd,"stdin.empty");
            using(FileStream empty=new FileStream(emptyInput,FileMode.CreateNew,FileAccess.Write,FileShare.None)){}
            stdin=new FileStream(emptyInput,FileMode.Open,FileAccess.Read,FileShare.Read);
            IntPtr[] hs={stdin.SafeFileHandle.DangerousGetHandle(),stdout.SafeFileHandle.DangerousGetHandle(),stderr.SafeFileHandle.DangerousGetHandle()};
            foreach(IntPtr h in hs)Check(SetHandleInformation(h,1,1));
            IntPtr size=IntPtr.Zero;InitializeProcThreadAttributeList(IntPtr.Zero,1,0,ref size);
            attrs=Marshal.AllocHGlobal(size);Check(InitializeProcThreadAttributeList(attrs,1,0,ref size));initialized=true;
            handles=Marshal.AllocHGlobal(IntPtr.Size*3);Marshal.Copy(hs,0,handles,3);
            Check(UpdateProcThreadAttribute(attrs,0,new IntPtr(0x20002),handles,new IntPtr(IntPtr.Size*3),IntPtr.Zero,IntPtr.Zero));
            SIX si=new SIX();si.startup.cb=Marshal.SizeOf(typeof(SIX));si.startup.flags=0x100;
            si.startup.input=hs[0];si.startup.output=hs[1];si.startup.error=hs[2];si.attributes=attrs;
            StringBuilder command=new StringBuilder(Quote(exe));foreach(string arg in args)command.Append(" ").Append(Quote(arg));
            env=Marshal.StringToHGlobalUni(environment);
            Check(CreateProcessW(exe,command,IntPtr.Zero,IntPtr.Zero,true,0x08080404,env,cwd,ref si,out pi));
            process=pi.process;Pid=pi.pid;
            Check(AssignProcessToJobObject(job,process));assigned=true;
            long exited,kernel,user;Check(GetProcessTimes(process,out rootCreated,out exited,out kernel,out user));
            uint nameSize=32768;StringBuilder name=new StringBuilder((int)nameSize);
            Check(QueryFullProcessImageNameW(process,0,name,ref nameSize));rootExecutable=name.ToString();
            if(ResumeThread(pi.thread)==0xffffffff)throw new Win32Exception(Marshal.GetLastWin32Error());
        }catch{
            if(pi.process!=IntPtr.Zero && !assigned){TerminateProcess(pi.process,1);WaitForSingleObject(pi.process,10000);}
            Dispose();throw;
        }finally{
            if(pi.thread!=IntPtr.Zero)CloseHandle(pi.thread);
            foreach(FileStream stream in new FileStream[]{stdin,stdout,stderr})if(stream!=null)SetHandleInformation(stream.SafeFileHandle.DangerousGetHandle(),1,0);
            if(initialized)DeleteProcThreadAttributeList(attrs);
            foreach(IntPtr p in new IntPtr[]{limits,attrs,handles,env})if(p!=IntPtr.Zero)Marshal.FreeHGlobal(p);
        }
    }
    public bool Wait(int milliseconds){uint r=WaitForSingleObject(process,(uint)milliseconds);if(r==0)return true;if(r==258)return false;throw new Win32Exception(Marshal.GetLastWin32Error());}
    public uint ExitCode(){uint code;Check(GetExitCodeProcess(process,out code));return code;}
    public int[] Accounting(){IntPtr p=Marshal.AllocHGlobal(48);try{Check(QueryInformationJobObject(job,1,p,48,IntPtr.Zero));return new int[]{Marshal.ReadInt32(p,36),Marshal.ReadInt32(p,40),Marshal.ReadInt32(p,44)};}finally{Marshal.FreeHGlobal(p);}}
    public sealed class ProcessObservation {
        public uint pid;
        public bool? owned, signaled;
        public long? created_filetime, exited_filetime;
        public uint? exit_code;
        public string executable, error_stage, error;
        public int? win32_error;
    }
    ProcessObservation ObserveProcess(uint pid,IntPtr held){
        ProcessObservation r=new ProcessObservation();r.pid=pid;IntPtr p=held;string stage="open-process";
        try{
            // A PID from the owned job may exit/recycle before OpenProcess. Check
            // membership through this handle before reading identity or state.
            if(p==IntPtr.Zero){p=OpenProcess(0x101000,false,pid);Check(p!=IntPtr.Zero);}
            stage="owned-job-membership";bool member;Check(IsProcessInJob(p,job,out member));r.owned=member;
            if(!member){r.error_stage=stage;r.error="not-owned-or-pid-reused";return r;}
            stage="process-times";long created,exited,kernel,user;
            Check(GetProcessTimes(p,out created,out exited,out kernel,out user));r.created_filetime=created;
            if(held!=IntPtr.Zero && created!=rootCreated)throw new InvalidOperationException("root-identity-changed");
            stage="process-wait";uint wait=WaitForSingleObject(p,0);
            if(wait!=0 && wait!=258)throw new Win32Exception(Marshal.GetLastWin32Error());
            r.signaled=wait==0;
            if(wait==0){
                // Query times again after observing the terminal signal; the
                // earlier exit time is undefined if it was still running.
                stage="terminal-process-times";Check(GetProcessTimes(p,out created,out exited,out kernel,out user));
                r.exited_filetime=exited;stage="exit-code";uint code;Check(GetExitCodeProcess(p,out code));r.exit_code=code;
            }
            stage="executable";
            if(held!=IntPtr.Zero){r.executable=rootExecutable;}
            else{uint size=32768;StringBuilder name=new StringBuilder((int)size);Check(QueryFullProcessImageNameW(p,0,name,ref size));r.executable=name.ToString();}
        }catch(Exception e){r.error_stage=stage;r.error=e.Message;Win32Exception w=e as Win32Exception;if(w!=null)r.win32_error=w.NativeErrorCode;}
        finally{if(held==IntPtr.Zero && p!=IntPtr.Zero)CloseHandle(p);}
        return r;
    }
    public sealed class JobObservation {
        public string schema="sfl-owned-job-observation-v1";
        public string status="PARTIAL", error;
        public bool sequence_not_atomic=true;
        public long started_ticks,ended_ticks,stopwatch_frequency=System.Diagnostics.Stopwatch.Frequency;
        public int[] accounting_before,accounting_after;
        public uint? assigned,listed;
        public ProcessObservation root;
        public List<ProcessObservation> members=new List<ProcessObservation>();
    }
    public JobObservation ObserveJob(){
        JobObservation r=new JobObservation();r.started_ticks=System.Diagnostics.Stopwatch.GetTimestamp();IntPtr b=IntPtr.Zero;
        try{
            r.accounting_before=Accounting();r.root=ObserveProcess(Pid,process);
            b=Marshal.AllocHGlobal(8200);Check(QueryInformationJobObject(job,3,b,8200,IntPtr.Zero));
            uint assigned=(uint)Marshal.ReadInt32(b,0),listed=(uint)Marshal.ReadInt32(b,4);r.assigned=assigned;r.listed=listed;
            // Bound work and fail closed on truncation; never claim an empty job
            // from a failed query or an incomplete process list.
            if(assigned!=listed || listed>1024)throw new InvalidOperationException("owned-process-list-incomplete");
            uint[] ids=new uint[listed];for(int i=0;i<ids.Length;i++)ids[i]=checked((uint)Marshal.ReadInt64(b,8+8*i));
            foreach(uint pid in ids)r.members.Add(ObserveProcess(pid,pid==Pid?process:IntPtr.Zero));
            r.accounting_after=Accounting();r.status=r.root.error==null && r.members.TrueForAll(p=>p.error==null)?"OBSERVED":"PARTIAL";
        }catch(Exception e){r.error=e.Message;}
        finally{if(b!=IntPtr.Zero)Marshal.FreeHGlobal(b);r.ended_ticks=System.Diagnostics.Stopwatch.GetTimestamp();}
        return r;
    }
    public void Terminate(){Check(TerminateJobObject(job,1));}
    public void Dispose(){
        if(job!=IntPtr.Zero){CloseHandle(job);job=IntPtr.Zero;}
        if(process!=IntPtr.Zero){WaitForSingleObject(process,10000);CloseHandle(process);process=IntPtr.Zero;}
        foreach(FileStream stream in new FileStream[]{stdin,stdout,stderr})if(stream!=null)stream.Dispose();
        stdin=null;stdout=null;stderr=null;
    }
}
'@
}
function Invoke-RunNative([string]$Executable,[string[]]$Arguments,[string]$Directory,[int]$TimeoutSeconds) {
    Assert-RunCondition ($TimeoutSeconds -gt 0 -and $TimeoutSeconds -le 9000) 'outer-time-budget'
    Initialize-RunNative
    $environment=[Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $environment['SYSTEMROOT']=[Environment]::GetFolderPath('Windows');$environment['WINDIR']=$environment['SYSTEMROOT']
    $environment['SYSTEMDRIVE']=[IO.Path]::GetPathRoot($environment['SYSTEMROOT']).TrimEnd('\')
    $environment['PATH']=[Environment]::SystemDirectory+';'+$environment['SYSTEMROOT']
    foreach($key in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){
        $path=Get-RunPath (Join-Path $Directory $key)
        Assert-RunCondition (-not [IO.Directory]::Exists($path) -and -not [IO.File]::Exists($path)) 'new-environment-directory'
        [void][IO.Directory]::CreateDirectory($path);$environment[$key]=$path
    }
    $block=($environment.GetEnumerator()|ForEach-Object{$_.Key+'='+$_.Value+[char]0}) -join ''
    $block+=[char]0
    $child=$null;$clock=[Diagnostics.Stopwatch]::StartNew()
    $record=[ordered]@{status='FAIL';created_suspended=$false;job_assigned_before_resume=$false;termination_requested=$false;errors=@()}
    try{
        $child=[SflOwnedRun]::new($Executable,$Arguments,$block,$Directory,($Directory+'\stdout.log'),($Directory+'\stderr.log'))
        $record.pid=$child.Pid;$record.created_suspended=$true;$record.job_assigned_before_resume=$true
        while(-not $child.Wait(100)){
            Assert-RunCondition ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds) 'outer-deadline'
            foreach($name in @('stdout.log','stderr.log')){Assert-RunCondition (([IO.FileInfo]::new($Directory+'\'+$name)).Length -le 128MB) 'outer-output-budget'}
        }
        $record.actual_exit_code=$child.ExitCode()
        $record.job_before_cleanup=$child.Accounting()
        try{$record.job_observation_before_cleanup=$child.ObserveJob()}
        catch{$record.job_observation_error=$_.Exception.Message}
        # Root-process signaling and whole-job accounting are separate facts.
        # Retain the first count, then require an idle owned job within a short
        # drain budget and the original overall deadline. No restart or timeout
        # extension, and a surviving descendant still fails and is terminated.
        $settle=[Diagnostics.Stopwatch]::StartNew()
        $record.job_drain=[ordered]@{budget_seconds=2;observations=@();idle_confirmed=$false}
        do{
            $current=$child.Accounting()
            $record.job_drain.observations+= [ordered]@{elapsed_ms=$settle.Elapsed.TotalMilliseconds;accounting=$current}
            if($current[1] -eq 0){$record.job_drain.idle_confirmed=$true;break}
            Assert-RunCondition ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds) 'outer-deadline'
            if($settle.Elapsed.TotalSeconds -ge 2){break}
            [Threading.Thread]::Sleep(25)
        }while($true)
        $record.job_drain.elapsed_ms=$settle.Elapsed.TotalMilliseconds
        Assert-RunCondition ($record.job_drain.idle_confirmed) 'outer-descendants-remain'
        foreach($name in @('stdout.log','stderr.log')){Assert-RunCondition (([IO.FileInfo]::new($Directory+'\'+$name)).Length -le 128MB) 'outer-final-output-budget'}
        if($record.actual_exit_code -eq 0){$record.status='PASS'}
    }catch{$record.errors+= $_.Exception.Message}
    finally{
        if($null -ne $child){
            # Diagnostic fields never prevent cleanup. The observation spans
            # multiple native calls; only the bounded idle check grants success.
            if(-not $record.Contains('job_observation_before_cleanup') -and -not $record.Contains('job_observation_error')){
                try{$record.job_observation_before_cleanup=$child.ObserveJob()}
                catch{$record.job_observation_error=$_.Exception.Message}
            }
            try{
                if($child.Accounting()[1] -ne 0){$record.termination_requested=$true;$record.status='FAIL';$child.Terminate()}
                $drain=[Diagnostics.Stopwatch]::StartNew()
                while($child.Accounting()[1] -ne 0 -and $drain.Elapsed.TotalSeconds -lt 10){[Threading.Thread]::Sleep(50)}
                $record.job_after_cleanup=$child.Accounting();$record.actual_exit_code=$child.ExitCode()
                Assert-RunCondition ($record.job_after_cleanup[1] -eq 0) 'outer-job-still-active'
            }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
            finally{$child.Dispose()}
        }
        if($record.errors.Count -gt 0 -or $record.termination_requested){$record.status='FAIL'}
        $record.elapsed_seconds=$clock.Elapsed.TotalSeconds
    }
    return $record
}

$held=[Collections.Generic.List[IO.Stream]]::new();$resultRoot=$null;$childReceipt=$null
try{
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    Assert-RunCondition ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'native-powershell-5.1-x64-required'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    Assert-RunCondition ([Security.Principal.WindowsPrincipal]::new($identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'administrator-required'
    $root=Get-RunPath $PackageRoot;$parent=Get-RunPath $ResultParent;$request=Get-RunPath $RequestPath
    Assert-RunCondition ([IO.Directory]::Exists($root) -and [IO.Directory]::Exists($parent) -and $parent -ine $root -and -not $parent.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) 'result-package-boundary'
    $manifest=[IO.File]::Open((Get-RunPath ($root+'\manifest.json')),'Open','Read','Read');$held.Add($manifest)
    Assert-RunCondition ($manifest.Length -le 2MB -and (Get-RunHash $manifest) -ceq $fieldRunManifestSha256) 'package-manifest-pin'
    $manifest.Position=0;$reader=[IO.StreamReader]::new($manifest,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
    try{$document=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    Assert-RunCondition ($document.schema -ceq 'sfl-field-run-package-v1') 'package-schema'
    $allowed=@{'manifest.json'=$true;'invoke-field-run.ps1'=$true}
    foreach($required in @('field_runner.exe','validate_csv_v2_shadow.exe','validate_spot_image_files.exe','candidate-payload.json')){
        Assert-RunCondition ($null -ne $document.files.PSObject.Properties[$required]) 'package-required-file'
    }
    foreach($item in $document.files.PSObject.Properties){
        Assert-RunCondition ($item.Name -cmatch '^[A-Za-z0-9_.-]{1,80}$' -and -not $allowed.ContainsKey($item.Name)) 'package-file-name'
        $allowed[$item.Name]=$true
        $stream=[IO.File]::Open((Get-RunPath ($root+'\'+$item.Name)),'Open','Read','Read');$held.Add($stream)
        Assert-RunCondition ($stream.Length -eq $item.Value.bytes -and (Get-RunHash $stream) -ceq $item.Value.sha256) 'package-file-fact'
    }
    foreach($path in [IO.Directory]::GetFileSystemEntries($root)){
        $path=Get-RunPath $path
        Assert-RunCondition ([IO.File]::Exists($path) -and $allowed.ContainsKey([IO.Path]::GetFileName($path))) 'package-extra-entry'
    }
    $requestStream=[IO.File]::Open($request,'Open','Read','Read');$held.Add($requestStream)
    Assert-RunCondition ($requestStream.Length -le 128MB -and (Get-RunHash $requestStream) -ceq $ExpectedRequestSha256) 'request-pin'
    $resultRoot=Get-RunPath ($parent+'\run-'+[Guid]::NewGuid().ToString('N').Substring(0,12))
    Assert-RunCondition (-not [IO.Directory]::Exists($resultRoot) -and -not [IO.File]::Exists($resultRoot)) 'result-already-exists'
    [void][IO.Directory]::CreateDirectory($resultRoot,(New-RunAcl $OperatorSid));Assert-RunAcl $resultRoot $OperatorSid
    $child=Invoke-RunNative ($root+'\field_runner.exe') @('--request',$request,'--request-sha256',$ExpectedRequestSha256,'--output-root',$resultRoot,'--package-root',$root) $resultRoot 9000
    Assert-RunAcl $resultRoot $OperatorSid
    Write-RunJson ($resultRoot+'\native-child.json') $child
    $childReceipt=Get-RunFact ($resultRoot+'\native-child.json')
    $outputVerification=$null
    if([IO.File]::Exists($resultRoot+'\session\manifest.json')){$outputVerification=Test-RunOutput $resultRoot $ExpectedRequestSha256 ($child.status -ceq 'PASS')}
    Assert-RunCondition ($child.status -cne 'PASS' -or $null -ne $outputVerification) 'successful-child-missing-output'
    Assert-RunCondition ((Get-RunHash $requestStream) -ceq $ExpectedRequestSha256 -and (Get-RunHash $manifest) -ceq $fieldRunManifestSha256) 'launcher-input-closeout'
    $record=[ordered]@{schema='sfl-field-launch-v1';child=$child;native_child_receipt=$childReceipt;output_verification=$outputVerification;request_sha256=$ExpectedRequestSha256;package_manifest_sha256=$fieldRunManifestSha256;signature_policy='UNSIGNED_INTERNAL';release_gate='HOLD';promotion_allowed=$false;installation_performed=$false;application_shutdown_performed=$false}
    Write-RunJson ($resultRoot+'\launcher.json') $record
    Write-Host ('RESULT_PATH='+$resultRoot)
    $digest=[IO.File]::Open($resultRoot+'\launcher.json','Open','Read','Read')
    try{Write-Host ('LAUNCHER_SHA256='+(Get-RunHash $digest))}finally{$digest.Dispose()}
    if($child.status -cne 'PASS'){exit 1};exit 0
}catch{
    $failure=[ordered]@{status='FAIL';reason=$_.Exception.Message;result_path=$resultRoot;native_child_receipt=$childReceipt;release_gate='HOLD';promotion_allowed=$false}
    if($null -ne $resultRoot){try{Write-RunJson ($resultRoot+'\launcher-failure.json') $failure}catch{}}
    $failure|ConvertTo-Json -Compress
    exit 1
}finally{foreach($stream in $held){$stream.Dispose()}}
