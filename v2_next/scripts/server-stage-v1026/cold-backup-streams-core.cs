// .NET Framework 4.x, Windows only. No application control or network access.
// Separate version: retains default and named NTFS $DATA streams on files and
// directories. The pinned main helper supplies exact roots and a runtime guard.
// This is a byte copy, not VSS, ACL restoration, or application restore QA.
using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using Microsoft.Win32.SafeHandles;

namespace SflColdCopyStreamsV2 {
    public sealed class Totals {
        public long Files, Directories, NamedStreams, Bytes;
        public string ManifestSha256;
    }
    public sealed class DataStream {
        public string Name;
        public long Bytes;
    }
    public sealed class Engine {
        private readonly string[] roots;
        private readonly Action guard;
        private readonly Action<string,long,long,long> progress;
        private readonly Stopwatch clock = Stopwatch.StartNew();
        private long lastPulse = -10000, work, files;
        private string phase, outputRoot;
        private const int MaxPath = 240;
        private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
        private struct StreamData {
            public long Size;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst=296)] public string Name;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        private static extern IntPtr FindFirstStreamW(string name, int level, out StreamData data, uint flags);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        private static extern bool FindNextStreamW(IntPtr handle, out StreamData data);
        [DllImport("kernel32.dll", SetLastError=true)]
        private static extern bool FindClose(IntPtr handle);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        private static extern SafeFileHandle CreateFileW(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
        private static void NeedPath(bool ok, string code, string path) {
            if(!ok) {
                var error=new InvalidOperationException("COLD_BACKUP:"+code);
                error.Data["source_path"]=path;
                throw error;
            }
        }
        private static void Need(bool ok, string code) { if(!ok) throw new InvalidOperationException("COLD_BACKUP:"+code); }
        public static string Canonical(string value) {
            Need(value != null && value.Length > 3 && value.Length <= MaxPath, "path-length");
            Need(value.Length > 2 && Char.IsLetter(value[0]) && value[1]==':' && value[2]=='\\', "local-path");
            Need(value.IndexOf(':',2)<0 && value.IndexOfAny(new char[]{'~','*','?','"','<','>','|'})<0 && !value.Any(Char.IsControl), "path-syntax");
            foreach(string part in value.Substring(3).Split('\\')) {
                Need(part.Length>0 && part!="." && part!=".." && !part.EndsWith(" ") && !part.EndsWith("."), "path-component");
                string stem=part.Split('.')[0].ToUpperInvariant();
                Need(stem!="CON" && stem!="PRN" && stem!="AUX" && stem!="NUL" &&
                    !(stem.Length==4 && (stem.StartsWith("COM") || stem.StartsWith("LPT")) && Char.IsDigit(stem[3])), "reserved-name");
            }
            Need(Path.GetFullPath(value)==value, "noncanonical-path");
            return value;
        }
        public static bool Within(string path, string root) {
            return path.Equals(root,StringComparison.OrdinalIgnoreCase) || path.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase);
        }
        public static void Plain(string path, bool missingLeaf) {
            Canonical(path);
            string current=path.Substring(0,3);
            string[] parts=path.Substring(3).Split('\\');
            for(int i=0;i<parts.Length;i++) {
                current=Path.Combine(current,parts[i]);
                FileAttributes attr;
                try { attr=File.GetAttributes(current); }
                catch(FileNotFoundException) { Need(missingLeaf && i==parts.Length-1,"missing-path"); return; }
                catch(DirectoryNotFoundException) { Need(missingLeaf && i==parts.Length-1,"missing-parent"); return; }
                Need((attr & FileAttributes.ReparsePoint)==0,"reparse-path");
                if(i<parts.Length-1) Need((attr & FileAttributes.Directory)!=0,"parent-not-directory");
            }
        }
        private static void StreamName(string raw) {
            Need(raw!=null && raw.Length>=8 && raw.Length<296 && raw[0]==':' && raw.EndsWith(":$DATA",StringComparison.Ordinal),"stream-name");
            string leaf=raw.Substring(1,raw.Length-7);
            Need(leaf.Length>0 && leaf.IndexOfAny(new char[]{':','\\','/','\0'})<0,"stream-name");
            Utf8.GetBytes(raw); // Fail before shutdown if the exact name cannot be represented.
        }
        public static DataStream[] Streams(string path) {
            Plain(path,false);
            FileAttributes attr=File.GetAttributes(path);
            NeedPath((attr & (FileAttributes.ReparsePoint|FileAttributes.Encrypted|FileAttributes.SparseFile|FileAttributes.Offline|FileAttributes.Device))==0,"unsupported-file-attributes",path);
            var found=new List<DataStream>();
            var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            StreamData data;
            IntPtr handle=FindFirstStreamW(path,0,out data,0);
            if(handle==new IntPtr(-1)) {
                int error=Marshal.GetLastWin32Error();
                NeedPath(error==38,"stream-enumeration-failed",path);
                return found.ToArray();
            }
            try {
                do {
                    NeedPath(data.Size>=0,"stream-size",path);
                    if(data.Name=="::$DATA") {
                        NeedPath((attr & FileAttributes.Directory)==0 || data.Size==0,"directory-unnamed-data-not-supported",path);
                    } else {
                        try {StreamName(data.Name);} catch(Exception error) {error.Data["source_path"]=path;error.Data["stream_name"]=data.Name;throw;}
                        NeedPath(names.Add(data.Name),"duplicate-stream-name",path);
                        NeedPath(found.Count<4096,"stream-count-limit",path);
                        found.Add(new DataStream{Name=data.Name,Bytes=data.Size});
                    }
                } while(FindNextStreamW(handle,out data));
                NeedPath(Marshal.GetLastWin32Error()==38,"stream-enumeration-incomplete",path);
            } finally {FindClose(handle);}
            found.Sort((a,b)=>StringComparer.Ordinal.Compare(a.Name,b.Name));
            return found.ToArray();
        }
        public static void OrdinaryData(string path) {Streams(path);}
        private static string StreamShape(DataStream[] streams) {
            return String.Join(";",streams.Select(s=>B64(s.Name)+","+s.Bytes.ToString(CultureInfo.InvariantCulture)));
        }
        private static FileStream OpenFork(string path, string name, bool create) {
            Plain(path,false);StreamName(name);
            // Only the validated base path and enumerated/manifest-bound NTFS data
            // stream name are joined. Extended syntax permits a long stream name.
            string full=@"\\?\"+path+name;
            SafeFileHandle handle=CreateFileW(full,create?0x40000000u:0x80000000u,create?0u:1u,IntPtr.Zero,create?1u:3u,0x02000000u,IntPtr.Zero);
            if(handle.IsInvalid) {
                int code=Marshal.GetLastWin32Error();handle.Dispose();
                var error=new System.ComponentModel.Win32Exception(code,"COLD_BACKUP:stream-open");
                error.Data["source_path"]=path;error.Data["stream_name"]=name;throw error;
            }
            try {return new FileStream(handle,create?FileAccess.Write:FileAccess.Read,1048576,false);}
            catch {handle.Dispose();throw;}
        }
        private string TransferFork(string source, string target, DataStream fork, bool copy) {
            OrdinaryData(source);
            FileStream output=null;
            using(var input=OpenFork(source,fork.Name,false))
            using(var sha=SHA256.Create()) {
                Need(input.Length==fork.Bytes,"source-stream-length-changed");
                try {
                    if(copy) {OrdinaryData(target);Space(target,fork.Bytes);output=OpenFork(target,fork.Name,true);}
                    var buffer=new byte[1048576];long left=fork.Bytes;
                    while(left>0) {
                        int count=input.Read(buffer,0,(int)Math.Min(buffer.Length,left));Need(count>0,"truncated-source-stream");
                        sha.TransformBlock(buffer,0,count,buffer,0);if(output!=null) output.Write(buffer,0,count);
                        left-=count;work+=count;Pulse(false);
                    }
                    Need(input.Length==fork.Bytes && input.ReadByte()==-1,"growing-source-stream");
                    sha.TransformFinalBlock(new byte[0],0,0);
                    if(output!=null) output.Flush(true);
                    return BitConverter.ToString(sha.Hash).Replace("-","");
                } finally {if(output!=null) output.Dispose();}
            }
        }
        public Engine(string[] sourceRoots, Action runtimeGuard, Action<string,long,long,long> onProgress) {
            Need(sourceRoots!=null && sourceRoots.Length>0 && sourceRoots.Length<=8,"root-count");
            roots=sourceRoots.Select(Canonical).ToArray(); guard=runtimeGuard; progress=onProgress;
            Need(guard!=null && progress!=null,"callbacks-required");
            for(int i=0;i<roots.Length;i++) {
                Plain(roots[i],false); Need(Directory.Exists(roots[i]),"source-root-missing");
                for(int j=0;j<i;j++) Need(!Within(roots[i],roots[j]) && !Within(roots[j],roots[i]),"overlapping-roots");
            }
        }
        private void Pulse(bool force) {
            if(force || clock.ElapsedMilliseconds-lastPulse>=5000) {
                if(outputRoot!=null) Space(outputRoot,0);
                guard(); progress(phase,work,files,clock.ElapsedMilliseconds); lastPulse=clock.ElapsedMilliseconds;
            }
        }
        private void Start(string name) {phase=name;work=0;files=0;Pulse(true);}
        private IEnumerable<string> Walk(string path, int depth) {
            Need(depth<=64,"depth-limit"); OrdinaryData(path); Pulse(false);
            yield return path;
            if(!Directory.Exists(path)) yield break;
            var names=new List<string>();
            foreach(string entry in Directory.EnumerateFileSystemEntries(path)) {
                Need(names.Count<200000,"directory-entry-limit");
                Canonical(entry); names.Add(entry); Pulse(false);
            }
            names.Sort(StringComparer.Ordinal);
            foreach(string entry in names) foreach(string child in Walk(entry,depth+1)) yield return child;
        }
        private string Target(string targetRoot, int root, string source) {
            string relative=source.Substring(roots[root].Length);
            string result=Canonical(targetRoot+"\\r"+root.ToString(CultureInfo.InvariantCulture)+relative);
            Need(Within(result,targetRoot),"target-boundary"); return result;
        }
        private void Destination(string target) {
            Canonical(target); Plain(target,true);
            foreach(string root in roots) Need(!Within(target,root) && !Within(root,target),"destination-overlap");
            Need(!Directory.Exists(target) && !File.Exists(target),"destination-exists");
        }
        public Totals Inventory(string prospectiveTarget) {
            Canonical(prospectiveTarget);
            foreach(string root in roots) Need(!Within(prospectiveTarget,root)&&!Within(root,prospectiveTarget),"destination-overlap");
            Start("inventory"); var totals=new Totals();
            for(int i=0;i<roots.Length;i++) foreach(string path in Walk(roots[i],0)) {
                Target(prospectiveTarget,i,path);
                if(Directory.Exists(path)) totals.Directories++;
                else { checked {totals.Bytes+=new FileInfo(path).Length;totals.Files++;} }
                foreach(var fork in Streams(path)) {checked {totals.Bytes+=fork.Bytes;totals.NamedStreams++;}}
                files=totals.Files;work=totals.Bytes;Pulse(false);
                Need(totals.Files+totals.Directories+totals.NamedStreams<=5000000,"total-entry-limit");
            }
            Pulse(true);return totals;
        }
        public static long RequiredSpace(long bytes, long entries) {
            Need(bytes>=0 && entries>=0,"negative-size");
            // Two copies + growth + a conservative per-entry allocation/manifest
            // estimate + reserve. Not a quota guarantee; actual free space is rechecked.
            return checked(bytes*2 + bytes/10 + entries*16384 + 10L*1024*1024*1024);
        }
        public static void Space(string target, long remainingBytes) {
            Need(remainingBytes>=0,"negative-space");
            var drive=new DriveInfo(Path.GetPathRoot(target));
            Need(drive.DriveType==DriveType.Fixed && drive.DriveFormat=="NTFS","fixed-ntfs-required");
            Need(drive.AvailableFreeSpace>=checked(remainingBytes+10L*1024*1024*1024),"insufficient-space");
        }
        private static string B64(string text) {return Convert.ToBase64String(Utf8.GetBytes(text));}
        private static string Un64(string text) {return Utf8.GetString(Convert.FromBase64String(text));}
        private static string Security(string path, bool directory) {
            var sections=AccessControlSections.Access|AccessControlSections.Owner|AccessControlSections.Group;
            return directory ? Directory.GetAccessControl(path,sections).GetSecurityDescriptorSddlForm(sections) :
                File.GetAccessControl(path,sections).GetSecurityDescriptorSddlForm(sections);
        }
        private string Transfer(string source, string target, long length, bool copy) {
            OrdinaryData(source);
            FileStream output=null;
            using(var input=new FileStream(source,FileMode.Open,FileAccess.Read,FileShare.Read,1048576,FileOptions.SequentialScan))
            using(var sha=SHA256.Create()) {
                Need(input.Length==length,"source-length-changed");
                try {
                    if(copy) {Plain(target,true);Need(!File.Exists(target) && !Directory.Exists(target),"copy-target-exists");
                        Space(target,length);output=new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None,1048576,FileOptions.SequentialScan);}
                    var buffer=new byte[1048576];long left=length;
                    while(left>0) {
                        int read=input.Read(buffer,0,(int)Math.Min(buffer.Length,left));Need(read>0,"truncated-source");
                        sha.TransformBlock(buffer,0,read,buffer,0);if(output!=null) output.Write(buffer,0,read);
                        left-=read;work+=read;Pulse(false);
                    }
                    Need(input.Length==length && input.ReadByte()==-1,"growing-source");
                    sha.TransformFinalBlock(new byte[0],0,0);
                    if(output!=null) output.Flush(true);
                    return BitConverter.ToString(sha.Hash).Replace("-","");
                } finally {if(output!=null) output.Dispose();}
            }
        }
        private static void NewDirectory(string path) {Plain(path,true);Need(!Directory.Exists(path)&&!File.Exists(path),"directory-exists");Space(path,0);Directory.CreateDirectory(path);Plain(path,false);}
        private string Describe(string path, int root, string hash) {
            bool directory=Directory.Exists(path);var info=directory?(FileSystemInfo)new DirectoryInfo(path):new FileInfo(path);
            return String.Join("\t",new string[]{directory?"D":"F",root.ToString(CultureInfo.InvariantCulture),
                B64(path.Substring(roots[root].Length)),directory?"0":((FileInfo)info).Length.ToString(CultureInfo.InvariantCulture),
                info.CreationTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),info.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),
                ((int)info.Attributes).ToString(CultureInfo.InvariantCulture),B64(Security(path,directory)),hash});
        }
        public Totals Backup(string destination, string manifest) {
            Destination(destination);Plain(manifest,true);Need(!File.Exists(manifest),"manifest-exists");
            Need(Path.GetDirectoryName(manifest)==Path.GetDirectoryName(destination),"manifest-sibling-required");
            outputRoot=destination;Start("backup");NewDirectory(destination);var totals=new Totals();
            using(var stream=new FileStream(manifest,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            using(var writer=new StreamWriter(stream,Utf8,65536,true)) {
                writer.WriteLine("SFL-COLD-BACKUP-STREAMS-2");
                for(int i=0;i<roots.Length;i++) foreach(string source in Walk(roots[i],0)) {
                    string target=Target(destination,i,source);bool directory=Directory.Exists(source);
                    var forks=Streams(source);
                    string before=Describe(source,i,"-");string beforeForks=StreamShape(forks);string hash="-";
                    if(directory) {NewDirectory(target);totals.Directories++;}
                    else {long length=new FileInfo(source).Length;hash=Transfer(source,target,length,true);totals.Files++;checked {totals.Bytes+=length;}files++;}
                    var forkRows=new List<string>();
                    foreach(var fork in forks) {
                        string forkHash=TransferFork(source,target,fork,true);
                        forkRows.Add(String.Join("\t",new string[]{"A",i.ToString(CultureInfo.InvariantCulture),B64(source.Substring(roots[i].Length)),B64(fork.Name),fork.Bytes.ToString(CultureInfo.InvariantCulture),forkHash}));
                        checked {totals.Bytes+=fork.Bytes;totals.NamedStreams++;}
                    }
                    Need(Describe(source,i,"-")==before,"source-metadata-changed");
                    Need(StreamShape(Streams(source))==beforeForks,"source-stream-membership-changed");
                    string record=Describe(source,i,hash)+"\t"+forks.Length.ToString(CultureInfo.InvariantCulture);Need(record.Length<=65536,"manifest-record-size");
                    Space(destination,0);writer.WriteLine(record);
                    foreach(string forkRow in forkRows) {Need(forkRow.Length<=65536,"manifest-record-size");writer.WriteLine(forkRow);}
                    Pulse(false);
                }
                Space(destination,0);writer.Flush();stream.Flush(true);
            }
            totals.ManifestSha256=FileHash(manifest,Int64.MaxValue);Pulse(true);return totals;
        }
        private static string[] Record(string line) {
            Need(line!=null && line.Length<=65536,"manifest-line");
            string[] parts=line.Split('\t');Need(parts.Length==10 && (parts[0]=="D"||parts[0]=="F"),"manifest-record");
            int count;Need(Int32.TryParse(parts[9],NumberStyles.None,CultureInfo.InvariantCulture,out count) && count>=0 && count<=4096,"manifest-stream-count");
            Need(parts[0]=="D" ? parts[8]=="-" : System.Text.RegularExpressions.Regex.IsMatch(parts[8],"^[A-F0-9]{64}$"),"manifest-hash");
            return parts;
        }
        private static string[] ForkRecord(string line) {
            Need(line!=null && line.Length<=65536,"manifest-stream-line");
            string[] parts=line.Split('\t');Need(parts.Length==6 && parts[0]=="A","manifest-stream-record");
            StreamName(Un64(parts[3]));
            long size;Need(Int64.TryParse(parts[4],NumberStyles.None,CultureInfo.InvariantCulture,out size) && size>=0,"manifest-stream-size");
            Need(System.Text.RegularExpressions.Regex.IsMatch(parts[5],"^[A-F0-9]{64}$"),"manifest-stream-hash");
            return parts;
        }
        private void CheckForks(StreamReader reader, string[] parent, string source, string data, string restored, bool restore, Totals totals) {
            int count=Int32.Parse(parent[9],CultureInfo.InvariantCulture);
            var sourceForks=Streams(source);var dataForks=Streams(data);
            Need(sourceForks.Length==count,"source-stream-membership-drift");
            Need(dataForks.Length==count,"copy-stream-membership-drift");
            for(int j=0;j<count;j++) {
                string[] row=ForkRecord(reader.ReadLine());
                Need(row[1]==parent[1] && row[2]==parent[2],"stream-parent-binding");
                string name=Un64(row[3]);long length=Int64.Parse(row[4],CultureInfo.InvariantCulture);
                Need(sourceForks[j].Name==name && sourceForks[j].Bytes==length,"source-stream-membership-drift");
                Need(dataForks[j].Name==name && dataForks[j].Bytes==length,"copy-stream-membership-drift");
                Need(TransferFork(data,restored,dataForks[j],restore)==row[5],"copy-stream-hash-drift");
                Need(TransferFork(source,null,sourceForks[j],false)==row[5],"source-stream-hash-drift");
                checked {totals.NamedStreams++;totals.Bytes+=length;}
            }
            Need(StreamShape(Streams(source))==StreamShape(sourceForks),"source-stream-membership-changed");
            Need(StreamShape(Streams(data))==StreamShape(dataForks),"copy-stream-membership-changed");
            if(restore) Need(StreamShape(Streams(restored))==StreamShape(sourceForks),"restored-stream-membership-drift");
        }
        // Independently traverse the original roots, binding membership and bytes
        // to the manifest. Destination enumeration below detects extra/missing data.
        public Totals Verify(string manifest, string expectedHash, string dataRoot, string restoreRoot, bool restore) {
            Plain(manifest,false);Need(FileHash(manifest,Int64.MaxValue)==expectedHash,"manifest-pin");
            Canonical(dataRoot);foreach(string root in roots) Need(!Within(dataRoot,root)&&!Within(root,dataRoot),"verify-root-overlap");
            if(restore) {Destination(restoreRoot);Need(!Within(restoreRoot,dataRoot)&&!Within(dataRoot,restoreRoot),"restore-overlap");outputRoot=restoreRoot;guard();NewDirectory(restoreRoot);}
            Start(restore?"restore-copy":"source-and-restored-verification");var totals=new Totals();
            using(var stream=new FileStream(manifest,FileMode.Open,FileAccess.Read,FileShare.Read))
            using(var reader=new StreamReader(stream,Utf8,true,65536)) {
                Need(reader.ReadLine()=="SFL-COLD-BACKUP-STREAMS-2","manifest-header");
                for(int i=0;i<roots.Length;i++) foreach(string source in Walk(roots[i],0)) {
                    string[] r=Record(reader.ReadLine());
                    Need(r[1]==i.ToString(CultureInfo.InvariantCulture) && Un64(r[2])==source.Substring(roots[i].Length),"source-membership-changed");
                    string oldDescription=String.Join("\t",r.Take(8).Concat(new string[]{"-"}));
                    Need(Describe(source,i,"-")==oldDescription,"source-metadata-drift");
                    string data=Target(dataRoot,i,source);
                    bool dir=r[0]=="D";OrdinaryData(data);
                    Need(Directory.Exists(data)==dir,"backup-kind");
                    if(dir) {if(restore) NewDirectory(Target(restoreRoot,i,source));totals.Directories++;}
                    else {
                        long length=Int64.Parse(r[3],CultureInfo.InvariantCulture);Need(length>=0,"manifest-size");
                        string hash=Transfer(data,restore?Target(restoreRoot,i,source):null,length,restore);
                        Need(hash==r[8],"backup-or-restore-hash");
                        if(!restore) Need(Transfer(source,null,length,false)==r[8],"source-content-drift");
                        totals.Files++;totals.Bytes+=length;files++;
                    }
                    CheckForks(reader,r,source,data,restore?Target(restoreRoot,i,source):null,restore,totals);
                    Need(Describe(source,i,"-")==oldDescription,"source-metadata-drift-after-read");
                    Pulse(false);
                }
                Need(reader.ReadLine()==null,"manifest-extra-record");
            }
            VerifyMembership(manifest,dataRoot);
            if(restore) VerifyMembership(manifest,restoreRoot);
            Need(FileHash(manifest,Int64.MaxValue)==expectedHash,"manifest-changed");
            totals.ManifestSha256=expectedHash;Pulse(true);return totals;
        }
        private void VerifyMembership(string manifest, string dataRoot) {
            Plain(dataRoot,false);
            string[] top=Directory.GetFileSystemEntries(dataRoot);
            Need(top.Length==roots.Length,"copy-extra-root");
            using(var reader=new StreamReader(manifest,Utf8,true)) {
                Need(reader.ReadLine()=="SFL-COLD-BACKUP-STREAMS-2","manifest-header");
                for(int i=0;i<roots.Length;i++) {
                    string alias=dataRoot+"\\r"+i.ToString(CultureInfo.InvariantCulture);
                    foreach(string path in Walk(alias,0)) {
                        string[] r=Record(reader.ReadLine());
                        Need(r[1]==i.ToString(CultureInfo.InvariantCulture) && Un64(r[2])==path.Substring(alias.Length),"copy-membership");
                        Need((r[0]=="D")==Directory.Exists(path),"copy-member-kind");
                        var forks=Streams(path);int count=Int32.Parse(r[9],CultureInfo.InvariantCulture);
                        Need(forks.Length==count,"copy-stream-membership");
                        for(int j=0;j<count;j++) {
                            string[] row=ForkRecord(reader.ReadLine());
                            Need(row[1]==r[1] && row[2]==r[2] && Un64(row[3])==forks[j].Name && Int64.Parse(row[4],CultureInfo.InvariantCulture)==forks[j].Bytes,"copy-stream-binding");
                        }
                    }
                }
                Need(reader.ReadLine()==null,"copy-missing-record");
            }
        }
        public static string FileHash(string path, long maximum) {
            Plain(path,false);
            using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read))
            using(var sha=SHA256.Create()) {
                Need(stream.Length<=maximum,"hash-size-limit");
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","");
            }
        }
        public string EvidenceHash(string path) {
            Canonical(path);Need(roots.Any(root=>Within(path,root)),"evidence-outside-roots");
            Start("closeout-fact-hash");string hash=Transfer(path,null,new FileInfo(path).Length,false);Pulse(true);return hash;
        }
    }
}
