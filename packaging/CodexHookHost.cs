using System;
using System.Diagnostics;
using System.IO;
using System.Text;

// Windowed .NET Framework shim: runs the embedded Python hook without flashing
// a console while forwarding Codex's JSON stdin/stdout byte-for-byte.
internal static class CodexHookHost
{
    private static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\')
            {
                slashes++;
                continue;
            }
            if (ch == '"')
            {
                result.Append('\\', slashes * 2 + 1);
                result.Append('"');
                slashes = 0;
                continue;
            }
            result.Append('\\', slashes);
            slashes = 0;
            result.Append(ch);
        }
        result.Append('\\', slashes * 2);
        result.Append('"');
        return result.ToString();
    }

    private static int Main(string[] args)
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, @"runtime\python313\python.exe");
            string script = Path.Combine(root, "nyanko_codex_hook.py");
            if (!File.Exists(python) || !File.Exists(script) || args.Length < 1)
                return 0;

            var start = new ProcessStartInfo();
            start.FileName = python;
            start.Arguments = Quote(script) + " " + Quote(args[0]);
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardInput = true;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;

            using (var child = Process.Start(start))
            {
                if (child == null) return 0;
                Stream input = Console.OpenStandardInput();
                Stream output = Console.OpenStandardOutput();
                input.CopyTo(child.StandardInput.BaseStream);
                child.StandardInput.Close();
                child.StandardOutput.BaseStream.CopyTo(output);
                output.Flush();
                child.WaitForExit();
                return 0; // a visual status hook must never interrupt Codex
            }
        }
        catch
        {
            return 0;
        }
    }
}
