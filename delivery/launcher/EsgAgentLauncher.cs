using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

[assembly: AssemblyTitle("ESG Agent Launcher")]
[assembly: AssemblyDescription("Local launcher for ESG Agent")]
[assembly: AssemblyCompany("ESG Agent")]
[assembly: AssemblyProduct("ESG Agent")]
[assembly: AssemblyCopyright("Copyright 2026")]
[assembly: AssemblyVersion("1.5.0.0")]
[assembly: AssemblyFileVersion("1.5.0.0")]
[assembly: AssemblyInformationalVersion("1.5")]

internal static class Program
{
    private const int LayoutInvalid = 10;
    private const int PowerShellNotFound = 11;
    private const int PowerShellPolicyBlocked = 12;
    private const int LauncherProcessFailed = 13;
    private const int InvalidArguments = 64;
    private const int SummaryLimit = 8192;

    private sealed class LaunchSpec
    {
        internal string ScriptName;
        internal string FixedArgument;
        internal string StatusText;
    }

    private sealed class LaunchResult
    {
        internal int ExitCode;
        internal string StandardOutput;
        internal string StandardError;
    }

    [STAThread]
    private static int Main(string[] args)
    {
        bool nonInteractive = string.Equals(
            Environment.GetEnvironmentVariable("ESG_AGENT_LAUNCHER_NONINTERACTIVE"),
            "1",
            StringComparison.Ordinal
        );
        LaunchSpec spec = ParseArguments(args);
        if (spec == null)
        {
            return ReportLauncherError(InvalidArguments, "INVALID_ARGUMENTS", nonInteractive);
        }

        if (nonInteractive)
        {
            LaunchResult result = RunAction(spec);
            WriteSanitized(result.StandardOutput, false);
            WriteSanitized(result.StandardError, true);
            return result.ExitCode;
        }

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using (LauncherForm form = new LauncherForm(spec))
        {
            Application.Run(form);
            return form.ExitCode;
        }
    }

    private static LaunchSpec ParseArguments(string[] args)
    {
        if (args.Length == 0)
        {
            return new LaunchSpec
            {
                ScriptName = "Start-EsgAgent.ps1",
                FixedArgument = "-OpenBrowser",
                StatusText = "正在检查并启动服务…"
            };
        }
        if (args.Length != 1)
        {
            return null;
        }
        if (string.Equals(args[0], "--no-browser", StringComparison.Ordinal))
        {
            return new LaunchSpec
            {
                ScriptName = "Start-EsgAgent.ps1",
                FixedArgument = null,
                StatusText = "正在检查并启动服务…"
            };
        }
        if (string.Equals(args[0], "--status", StringComparison.Ordinal))
        {
            return new LaunchSpec
            {
                ScriptName = "Test-EsgAgent.ps1",
                FixedArgument = null,
                StatusText = "正在检查服务状态…"
            };
        }
        if (string.Equals(args[0], "--stop", StringComparison.Ordinal))
        {
            return new LaunchSpec
            {
                ScriptName = "Stop-EsgAgent.ps1",
                FixedArgument = null,
                StatusText = "正在停止应用服务…"
            };
        }
        return null;
    }

    private static LaunchResult RunAction(LaunchSpec spec)
    {
        string root = Path.GetFullPath(AppContext.BaseDirectory);
        string scriptsRoot = Path.GetFullPath(Path.Combine(root, "scripts", "delivery"));
        string scriptPath = Path.GetFullPath(Path.Combine(scriptsRoot, spec.ScriptName));
        string rootPrefix = root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!scriptPath.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase) || !File.Exists(scriptPath))
        {
            return ErrorResult(LayoutInvalid, "LAUNCHER_LAYOUT_INVALID");
        }

        string windowsRoot = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        string powerShell = Path.Combine(
            windowsRoot,
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe"
        );
        if (string.IsNullOrWhiteSpace(windowsRoot) || !File.Exists(powerShell))
        {
            return ErrorResult(PowerShellNotFound, "POWERSHELL_NOT_FOUND");
        }

        string arguments = string.Join(
            " ",
            new[]
            {
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                QuoteArgument(scriptPath),
                spec.FixedArgument ?? string.Empty
            }
        ).Trim();
        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = powerShell,
            Arguments = arguments,
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        StringBuilder standardOutput = new StringBuilder();
        StringBuilder standardError = new StringBuilder();
        object outputLock = new object();
        object errorLock = new object();
        ManualResetEvent outputClosed = new ManualResetEvent(false);
        ManualResetEvent errorClosed = new ManualResetEvent(false);

        try
        {
            using (Process process = new Process { StartInfo = startInfo })
            {
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    if (eventArgs.Data == null)
                    {
                        outputClosed.Set();
                    }
                    else
                    {
                        lock (outputLock) { AppendBounded(standardOutput, eventArgs.Data); }
                    }
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs eventArgs)
                {
                    if (eventArgs.Data == null)
                    {
                        errorClosed.Set();
                    }
                    else
                    {
                        lock (errorLock) { AppendBounded(standardError, eventArgs.Data); }
                    }
                };
                if (!process.Start())
                {
                    return ErrorResult(LauncherProcessFailed, "LAUNCHER_PROCESS_FAILED");
                }
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit(int.MaxValue);
                FinishAsyncRead(process, outputClosed, true);
                FinishAsyncRead(process, errorClosed, false);

                string stderr = Sanitize(standardError.ToString(), root);
                string stdout = Sanitize(standardOutput.ToString(), root);
                if (process.ExitCode != 0 && IsPolicyBlocked(stderr))
                {
                    return new LaunchResult
                    {
                        ExitCode = PowerShellPolicyBlocked,
                        StandardOutput = stdout,
                        StandardError = "POWERSHELL_POLICY_BLOCKED"
                    };
                }
                return new LaunchResult
                {
                    ExitCode = process.ExitCode,
                    StandardOutput = stdout,
                    StandardError = stderr
                };
            }
        }
        catch
        {
            return ErrorResult(LauncherProcessFailed, "LAUNCHER_PROCESS_FAILED");
        }
    }

    private static void FinishAsyncRead(Process process, ManualResetEvent streamClosed, bool standardOutput)
    {
        if (streamClosed.WaitOne(500))
        {
            return;
        }
        try
        {
            if (standardOutput)
            {
                process.CancelOutputRead();
            }
            else
            {
                process.CancelErrorRead();
            }
        }
        catch (InvalidOperationException)
        {
            // The asynchronous reader already completed between the bounded wait and cancellation.
        }
    }

    private static bool IsPolicyBlocked(string text)
    {
        return text.IndexOf("running scripts is disabled", StringComparison.OrdinalIgnoreCase) >= 0 ||
            text.IndexOf("AuthorizationManager check failed", StringComparison.OrdinalIgnoreCase) >= 0;
    }

    private static string QuoteArgument(string value)
    {
        if (value.IndexOf('"') >= 0)
        {
            throw new InvalidOperationException("Fixed path contains an invalid quote character.");
        }
        return "\"" + value + "\"";
    }

    private static void AppendBounded(StringBuilder builder, string line)
    {
        if (builder.Length >= SummaryLimit)
        {
            return;
        }
        int remaining = SummaryLimit - builder.Length;
        string value = line.Length > remaining ? line.Substring(0, remaining) : line;
        builder.AppendLine(value);
    }

    private static string Sanitize(string value, string root)
    {
        string sanitized = value ?? string.Empty;
        if (!string.IsNullOrEmpty(root))
        {
            sanitized = sanitized.Replace(root, "<delivery-root>\\");
            sanitized = sanitized.Replace(root.TrimEnd(Path.DirectorySeparatorChar), "<delivery-root>");
        }
        sanitized = Regex.Replace(
            sanitized,
            @"postgres(?:ql)?(?:\+\w+)?://[^\s]+",
            "<redacted-database-url>",
            RegexOptions.IgnoreCase
        );
        foreach (DictionaryEntry entry in Environment.GetEnvironmentVariables())
        {
            string name = Convert.ToString(entry.Key) ?? string.Empty;
            string secret = Convert.ToString(entry.Value) ?? string.Empty;
            if (secret.Length >= 4 && Regex.IsMatch(name, "KEY|PASSWORD|SECRET|TOKEN", RegexOptions.IgnoreCase))
            {
                sanitized = sanitized.Replace(secret, "<redacted>");
            }
        }
        return sanitized.Length > SummaryLimit ? sanitized.Substring(0, SummaryLimit) : sanitized;
    }

    private static LaunchResult ErrorResult(int exitCode, string code)
    {
        return new LaunchResult { ExitCode = exitCode, StandardOutput = string.Empty, StandardError = code };
    }

    private static int ReportLauncherError(int exitCode, string code, bool nonInteractive)
    {
        if (nonInteractive)
        {
            Console.Error.WriteLine(code);
        }
        else
        {
            MessageBox.Show(
                code + "\n\n日志位于 backend/data/runtime/logs/。",
                "ESG Agent",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
        }
        return exitCode;
    }

    private static void WriteSanitized(string value, bool error)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return;
        }
        if (error) { Console.Error.WriteLine(value.TrimEnd()); }
        else { Console.Out.WriteLine(value.TrimEnd()); }
    }

    private sealed class LauncherForm : Form
    {
        private readonly LaunchSpec _spec;
        private readonly Label _status;
        internal int ExitCode { get; private set; }

        internal LauncherForm(LaunchSpec spec)
        {
            _spec = spec;
            ExitCode = LauncherProcessFailed;
            Text = "ESG Agent";
            Width = 420;
            Height = 145;
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;

            _status = new Label
            {
                AutoSize = false,
                Text = spec.StatusText,
                Left = 24,
                Top = 22,
                Width = 360,
                Height = 24
            };
            ProgressBar progress = new ProgressBar
            {
                Left = 24,
                Top = 58,
                Width = 360,
                Height = 18,
                Style = ProgressBarStyle.Marquee,
                MarqueeAnimationSpeed = 24
            };
            Controls.Add(_status);
            Controls.Add(progress);
            Shown += OnShown;
        }

        private async void OnShown(object sender, EventArgs eventArgs)
        {
            LaunchResult result = await Task.Run(() => RunAction(_spec));
            ExitCode = result.ExitCode;
            if (result.ExitCode == 0)
            {
                Close();
                return;
            }
            string code = string.IsNullOrWhiteSpace(result.StandardError)
                ? "LAUNCHER_PROCESS_FAILED"
                : result.StandardError.Trim().Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)[0];
            MessageBox.Show(
                code + "\n\n启动未完成。日志位于 backend/data/runtime/logs/。",
                "ESG Agent",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            Close();
        }
    }
}
