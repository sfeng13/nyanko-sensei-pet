# Windows x64 package size report

Version: v0.5.4
Generated (UTC): 2026-10-02 10:08:45

| Item | Exact size | Approximate size |
|---|---:|---:|
| Embedded Python + runtime dependencies (installed directory) | 519382736 bytes | 495 MiB |
| Full installed payload directory | 618380337 bytes | 590 MiB |
| Online setup download | 5974 bytes | 6 KiB |
| Offline package download | 288189427 bytes | 275 MiB |

The online setup is only a bootstrapper; first installation downloads the full offline payload and verifies its SHA-256 against SHA256SUMS.txt.
The offline archive includes the same payload and requires no preinstalled Python.
