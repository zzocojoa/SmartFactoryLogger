// Windows/.NET Framework. Read-only observation, never a recoverable backup.
// Uses the separately pinned stream engine for its canonical path/NTFS checks.
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
using Core = SflColdCopyStreamsV2.Engine;

namespace SflColdObservationV1 {
    public sealed class Totals {
        public long Files, Directories, NamedStreams, Bytes;
        public string ManifestSha256;
        public bool RecoverableBackupCreated = false;
    }
    public sealed class Observer {
        private readonly string[] roots;
        private readonly Action guard;
        private readonly Action<string,long,long,long> progress;
        private readonly Stopwatch clock = Stopwatch.StartNew();
        private readonly UTF8Encoding utf = new UTF8Encoding(false,true);
        private long lastPulse = -5000, readBytes;
        private Totals totals;
        private const long MaxManifestBytes = 1024L*1024*1024;
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        private static extern SafeFileHandle CreateFileW(string path, uint access, uint share,
            IntPtr security, uint disposition, uint flags, IntPtr template);
        private static void Need(bool ok, string code) {
            if(!ok) throw new InvalidOperationException("COLD_OBSERVATION:"+code);
        }
        public Observer(string[] sourceRoots, Action runtimeGuard, Action<string,long,long,long> onProgress) {
            Need(sourceRoots!=null && sourceRoots.Length>0 && sourceRoots.Length<=8,"root-count");
            roots=sourceRoots.Select(Core.Canonical).ToArray();
            guard=runtimeGuard;progress=onProgress;
            Need(guard!=null && progress!=null,"callbacks-required");
            for(int i=0;i<roots.Length;i++) {
                Core.Plain(roots[i],false);Need(Directory.Exists(roots[i]),"missing-root");
                for(int j=0;j<i;j++) Need(!Core.Within(roots[i],roots[j]) &&
                    !Core.Within(roots[j],roots[i]),"overlapping-roots");
            }
        }
        private void Pulse(bool force) {
            if(force || clock.ElapsedMilliseconds-lastPulse>=5000) {
                guard();progress("observe-original",readBytes,totals.Files,clock.ElapsedMilliseconds);
                lastPulse=clock.ElapsedMilliseconds;
            }
        }
        private string B64(string value) {return Convert.ToBase64String(utf.GetBytes(value));}
        private IEnumerable<string> Walk(string path,int depth) {
            Need(depth<=64,"depth-limit");Core.OrdinaryData(path);Pulse(false);
            yield return path;
            if(!Directory.Exists(path)) yield break;
            var names=new List<string>();
            foreach(string entry in Directory.EnumerateFileSystemEntries(path)) {
                Need(names.Count<200000,"directory-entry-limit");Core.Canonical(entry);
                names.Add(entry);Pulse(false);
            }
            names.Sort(StringComparer.Ordinal);
            foreach(string entry in names) foreach(string child in Walk(entry,depth+1)) yield return child;
        }
        private string Metadata(string path) {
            bool directory=Directory.Exists(path);
            FileSystemInfo info=directory?(FileSystemInfo)new DirectoryInfo(path):new FileInfo(path);
            var sections=AccessControlSections.Access|AccessControlSections.Owner|AccessControlSections.Group;
            string security=directory?Directory.GetAccessControl(path,sections).GetSecurityDescriptorSddlForm(sections):
                File.GetAccessControl(path,sections).GetSecurityDescriptorSddlForm(sections);
            return String.Join("\t",new[]{directory?"D":"F",
                directory?"0":((FileInfo)info).Length.ToString(CultureInfo.InvariantCulture),
                info.CreationTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),
                info.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture),
                ((int)info.Attributes).ToString(CultureInfo.InvariantCulture),B64(security)});
        }
        private static string Shape(SflColdCopyStreamsV2.DataStream[] forks) {
            return String.Join("|",forks.Select(f=>Convert.ToBase64String(Encoding.UTF8.GetBytes(f.Name))+":"+f.Bytes.ToString(CultureInfo.InvariantCulture)));
        }
        private string Hash(string path,string fork,long length) {
            Core.Plain(path,false);
            // The suffix comes only from Core.Streams; no manifest-provided path is opened.
            string nativePath=@"\\?\"+path+(fork??"");
            var handle=CreateFileW(nativePath,0x80000000u,1u,IntPtr.Zero,3u,0x02000000u,IntPtr.Zero);
            if(handle.IsInvalid) {
                int error=Marshal.GetLastWin32Error();handle.Dispose();
                throw new System.ComponentModel.Win32Exception(error,"COLD_OBSERVATION:read-open");
            }
            using(handle)
            using(var stream=new FileStream(handle,FileAccess.Read,1048576,false))
            using(var hash=SHA256.Create()) {
                Need(stream.Length==length,"length-before");
                var buffer=new byte[1048576];long left=length;
                while(left>0) {
                    int count=stream.Read(buffer,0,(int)Math.Min(left,buffer.Length));
                    Need(count>0,"truncated-read");hash.TransformBlock(buffer,0,count,buffer,0);
                    left-=count;readBytes+=count;Pulse(false);
                }
                Need(stream.Length==length && stream.ReadByte()==-1,"length-after");
                hash.TransformFinalBlock(new byte[0],0,0);
                return BitConverter.ToString(hash.Hash).Replace("-","");
            }
        }
        private IEnumerable<string> Rows() {
            yield return "SFL-COLD-OBSERVATION-1";
            foreach(string root in roots) yield return "ROOT\t"+B64(root);
            for(int i=0;i<roots.Length;i++) foreach(string path in Walk(roots[i],0)) {
                string before=Metadata(path);bool directory=Directory.Exists(path);
                var forks=Core.Streams(path);string shape=Shape(forks);
                long length=directory?0:new FileInfo(path).Length;
                string digest=directory?"-":Hash(path,null,length);
                string key=i.ToString(CultureInfo.InvariantCulture)+"\t"+B64(path.Substring(roots[i].Length));
                var rows=new List<string>();
                rows.Add("ENTRY\t"+key+"\t"+before+"\t"+digest+"\t"+forks.Length);
                foreach(var fork in forks) {
                    rows.Add("ADS\t"+key+"\t"+B64(fork.Name)+"\t"+fork.Bytes.ToString(CultureInfo.InvariantCulture)+"\t"+Hash(path,fork.Name,fork.Bytes));
                    checked {totals.Bytes+=fork.Bytes;totals.NamedStreams++;}
                }
                Core.Plain(path,false);
                Need(Metadata(path)==before,"metadata-changed-during-read");
                Need(Shape(Core.Streams(path))==shape,"streams-changed-during-read");
                if(directory) totals.Directories++;
                else {checked {totals.Files++;totals.Bytes+=length;}}
                Need(totals.Files+totals.Directories+totals.NamedStreams<=5000000,"entry-limit");
                foreach(string row in rows) {Need(row.Length<=65536,"record-limit");yield return row;}
            }
        }
        private void ManifestPath(string path,bool creating) {
            Core.Plain(path,creating);
            foreach(string root in roots) Need(!Core.Within(path,root) && !Core.Within(root,path),"manifest-overlap");
            if(creating) Need(!File.Exists(path) && !Directory.Exists(path),"manifest-exists");
        }
        public Totals Capture(string manifest) {
            ManifestPath(manifest,true);Core.Space(manifest,0);
            totals=new Totals();readBytes=0;Pulse(true);long written=0;
            using(var stream=new FileStream(manifest,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            using(var writer=new StreamWriter(stream,utf,65536,true)) {
                writer.NewLine="\n";
                foreach(string row in Rows()) {
                    checked {written+=utf.GetByteCount(row)+1;}
                    Need(written<=MaxManifestBytes,"manifest-size-limit");
                    if(written%1048576<65536) Core.Space(manifest,0);
                    writer.WriteLine(row);
                }
                writer.Flush();stream.Flush(true);
            }
            Pulse(true);totals.ManifestSha256=Core.FileHash(manifest,MaxManifestBytes);return totals;
        }
        public Totals Verify(string manifest,string expectedSha256) {
            ManifestPath(manifest,false);
            Need(expectedSha256!=null && System.Text.RegularExpressions.Regex.IsMatch(expectedSha256,"^[A-F0-9]{64}$"),"manifest-pin-format");
            using(var stream=new FileStream(manifest,FileMode.Open,FileAccess.Read,FileShare.Read))
            using(var hash=SHA256.Create()) {
                Need(stream.Length>0 && stream.Length<=MaxManifestBytes,"manifest-size-limit");
                Need(BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","")==expectedSha256,"manifest-pin");
                stream.Position=0;totals=new Totals();readBytes=0;Pulse(true);
                using(var reader=new StreamReader(stream,utf,false,65536,true)) {
                    foreach(string expected in Rows()) {
                        // Bounded comparison avoids allocating an untrusted, arbitrarily long line.
                        foreach(char character in expected) Need(reader.Read()==character,"original-drift");
                        Need(reader.Read()=='\n',"original-drift");
                    }
                    Need(reader.Read()==-1,"manifest-extra-record");
                }
            }
            Pulse(true);totals.ManifestSha256=expectedSha256;return totals;
        }
    }
}
