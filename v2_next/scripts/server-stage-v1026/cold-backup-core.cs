// .NET Framework 4.x, Windows only. No application control or network access.
// Main helper supplies exact roots and a runtime guard. This is a byte-level cold
// backup/rehearsal, NOT a VSS snapshot, ACL restoration or application restore test.
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

namespace SflColdBackupV1 {
    public sealed class Totals {
        public long Files, Directories, Bytes;
        public string ManifestSha256;
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
        public static void OrdinaryData(string path) {
            Plain(path,false);
            FileAttributes attr=File.GetAttributes(path);
            Need((attr & (FileAttributes.ReparsePoint|FileAttributes.Encrypted|FileAttributes.SparseFile|FileAttributes.Offline|FileAttributes.Device))==0,"unsupported-file-attributes");
            StreamData data;
            IntPtr handle=FindFirstStreamW(path,0,out data,0);
            if(handle==new IntPtr(-1)) {
                int error=Marshal.GetLastWin32Error();
                Need(error==38,"stream-enumeration-failed"); return;
            }
            try {
                do { Need(data.Name=="::$DATA","alternate-data-stream"); }
                while(FindNextStreamW(handle,out data));
                Need(Marshal.GetLastWin32Error()==38,"stream-enumeration-incomplete");
            } finally { FindClose(handle); }
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
                files=totals.Files;work=totals.Bytes;Pulse(false);
                Need(totals.Files+totals.Directories<=5000000,"total-entry-limit");
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
        private static string HashText(byte[] bytes) {using(var sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","");}
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
                writer.WriteLine("SFL-COLD-BACKUP-1");
                for(int i=0;i<roots.Length;i++) foreach(string source in Walk(roots[i],0)) {
                    string target=Target(destination,i,source);bool directory=Directory.Exists(source);
                    string before=Describe(source,i,"-");string hash="-";
                    if(directory) {NewDirectory(target);totals.Directories++;}
                    else {long length=new FileInfo(source).Length;hash=Transfer(source,target,length,true);totals.Files++;totals.Bytes+=length;files++;}
                    Need(Describe(source,i,"-")==before,"source-metadata-changed");
                    string record=Describe(source,i,hash);Need(record.Length<=65536,"manifest-record-size");
                    Space(destination,0);writer.WriteLine(record);Pulse(false);
                }
                Space(destination,0);writer.Flush();stream.Flush(true);
            }
            totals.ManifestSha256=FileHash(manifest,Int64.MaxValue);Pulse(true);return totals;
        }
        private static string[] Record(string line) {
            Need(line!=null && line.Length<=65536,"manifest-line");
            string[] parts=line.Split('\t');Need(parts.Length==9 && (parts[0]=="D"||parts[0]=="F"),"manifest-record");
            Need(parts[0]=="D" ? parts[8]=="-" : System.Text.RegularExpressions.Regex.IsMatch(parts[8],"^[A-F0-9]{64}$"),"manifest-hash");
            return parts;
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
                Need(reader.ReadLine()=="SFL-COLD-BACKUP-1","manifest-header");
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
                Need(reader.ReadLine()=="SFL-COLD-BACKUP-1","manifest-header");
                for(int i=0;i<roots.Length;i++) {
                    string alias=dataRoot+"\\r"+i.ToString(CultureInfo.InvariantCulture);
                    foreach(string path in Walk(alias,0)) {
                        string[] r=Record(reader.ReadLine());
                        Need(r[1]==i.ToString(CultureInfo.InvariantCulture) && Un64(r[2])==path.Substring(alias.Length),"copy-membership");
                        Need((r[0]=="D")==Directory.Exists(path),"copy-member-kind");
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
