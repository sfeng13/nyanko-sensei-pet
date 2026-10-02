# Windows x64 package size report

Version: v0.5.4
Generated (UTC): 2026-10-02 09:59:51

| Item | Exact size | Approximate size |
|---|---:|---:|
| Embedded Python + runtime dependencies (installed directory) | 522650214 bytes | 498 MiB |
| Full installed payload directory | 621645993 bytes | 593 MiB |
| Online setup download | 5949 bytes | 6 KiB |
| Offline package download | 288458102 bytes | 275 MiB |

The online setup is only a bootstrapper; first installation downloads the full offline payload and verifies its SHA-256 against SHA256SUMS.txt.
The offline archive includes the same payload and requires no preinstalled Python.
