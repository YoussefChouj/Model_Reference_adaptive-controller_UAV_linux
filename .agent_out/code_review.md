✗ List items in parent directory (shell)
  │ Get-ChildItem -Path .. -Force
  └ Permission denied and could not request permission from user

✗ List items in repo root (shell)
  │ Get-ChildItem -Path . -Force
  └ <exited with error: PowerShell 6+ (pwsh) is not available. Please install it
    from https://aka.ms/powershell. Error: Error: Command failed: pwsh.exe
    --version
    'pwsh.exe' is not recognized as an internal or external command,
    operable program or batch file.
    >

✗ List directory ~\Desktop\UAV_lab
  └ Permission denied and could not request permission from user

● List directory .
  └ 51 files found

● Search (glob)
  │ "**/.git"
  └ No matches found

● Search (glob)
  │ "**/*.uvprojx"
  └ 1 file found

● List directory raw
  └ 5 files found

● List directory ground_station
  └ 11 files found

● List directory tutorial
  └ 3 files found

● Search (grep)
  │ "github\.com"
  └ No matches found

● List directory NOTE
  └ 5 files found

● Search (glob)
  │ "**/main.c"
  └ 1 file found

● Read config
  │ .git\config
  └ 6 lines read

● Search (glob)
  │ "**/*.{zip,rar,7z,tar,tar.gz}"
  └ No matches found

● List directory raw\web

● Search (glob)
  │ "**/*rc*.*"
  └ 16 files found

● Search (grep)
  │ "\bRC\b|sbus|PPM|ppm|remote|receiver|rx|virtual rc|Virtual RC"
  └ 8 lines found

● Search (grep)
  │ "virtual\s*rc|Virtual\s*RC|sbus|SBUS|ppm|PPM|remoter|remote" in *.{c,h}
  └ 8 lines found

● Read copilot-tool-output-1779184585840-s6tb9a.txt
  │ ~\AppData\Local\Temp\copilot-tool-output-1779184585840-s6tb9a.txt
  └ 1 line read

● Read copilot-tool-output-1779184585840-s6tb9a.txt
  │ ~\AppData\Local\Temp\copilot-tool-output-1779184585840-s6tb9a.txt
  └ L1:200 (123 lines read)

● Search (grep)
  │ "repo|repository|upstream|fork" (docs, wiki, NOTE)
  └ 14 lines found

● Web Search (MCP: github-mcp-server) · GitHub repository "FreeRTOS---Six_Degrees_of_Freedom _Adapt…
  └ {"type":"output_text","text":{"value":"I could not find any GitHub repos...

● Read architecture.md
  │ docs\architecture.md
  └ 23 lines read

● Read virtual-rc-authority.md
  │ wiki\concepts\virtual-rc-authority.md
  └ 68 lines read

● Search (glob)
  │ "**/*{old,backup,legacy,previous,orig}*"
  └ No matches found

● Web Search (MCP: github-mcp-server) · "RemoterTask" sbus_lost repository · query: ""RemoterTask" …
  └ {"type":"output_text","text":{"value":"There is no well-known open-sourc...

● Web Search (MCP: github-mcp-server) · "virtual rc" sbus FreeRTOS UAV repository · query: ""virtua…
  └ {"type":"output_text","text":{"value":"Here are some useful open-source ...

● Web Search (MCP: github-mcp-server) · "Six Degrees of Freedom" FreeRTOS STM32 adaptive controller…
  └ {"type":"output_text","text":{"value":"There does not appear to be a pub...

Unable to produce the divergence table because only one repository is accessible in the workspace and no second repo exists under the current root; parent directories are not accessible, so there’s nothing to diff against.

Below are the RC‑critical firmware files identified in this repo (per the Virtual RC authority and SBUS control path). Once the second repo is available under the current workspace, I can diff these and fill the divergence columns.

| RC‑critical file | Role in RC path | Repo A (current) | Repo B | Divergence |
|---|---|---|---|---|
| `TASK\send_data.c` | Ground‑station command parsing, virtual RC gate | Present | Not available | Not computed |
| `TASK\StabilizerTask.c` | Effective stick selection (`sbus_lost` vs virtual) | Present | Not available | Not computed |
| `TASK\RemoterTask.c` | SBUS loss detection, channel normalization | Present | Not available | Not computed |
| `TASK\RemoterTask.h` | RC channel macros/definitions | Present | Not available | Not computed |
| `BSP\usart1.c` | SBUS frame decode + last‑valid tick | Present | Not available | Not computed |
| `BSP\usart1.h` | SBUS decode interface + channel array | Present | Not available | Not computed |
| `Global_file\global_declare.h` | SBUS constants + RC globals | Present | Not available | Not computed |
| `USER\main.c` | Remoter task wiring | Present | Not available | Not computed |
| `TASK\AutoflyTask.c` | RC‑gated auto‑flight actions | Present | Not available | Not computed |

