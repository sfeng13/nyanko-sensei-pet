using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class NyankoLauncher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, @"runtime\python313\pythonw.exe");
            string script = Path.Combine(root, "launch.pyw");
            if (!File.Exists(python) || !File.Exists(script))
                throw new FileNotFoundException("请重新安装猫咪老师桌宠，程序文件不完整。");
            var start = new ProcessStartInfo(python, "\"" + script + "\"");
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            Process.Start(start);
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "猫咪老师启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
