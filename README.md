# PLC Sidecar

English | [简体中文](README.zh-CN.md)

**Open tools for working with PLC projects. Inspect, edit, and review project files outside the vendor IDE; use the vendor software for final compilation and PLC upload/download.**

PLC projects are often stored in proprietary files that are difficult to read and compare. PLC Sidecar is a collection of small, independent tools for inspecting project structure offline, creating reviewable copies, and catching obvious issues before opening a project in the vendor IDE. It starts with Delta ISPSoft `.isp` files and may grow to support other formats and workflows.

> Experimental: a valid file structure does not mean a project has passed ISPSoft compilation, simulation, or testing on hardware.

## Available tool

### `ispsoft-isp-edit`

This Codex skill also includes a standalone Python CLI. For the ISPSoft 3.24 `.isp` container variant observed so far, it can:

- Show the project name, task POU order, and network counts;
- Extract the whole project payload or one POU for scripted inspection and editing;
- Write an edited payload to a **new** `.isp` file and check lengths, CRC32, and read-back results;
- Refuse to overwrite the source file or write an unrecognized layout;
- Construct selected LD node patterns based on observed examples.

Testing so far covers one EC3 project and six examples installed with ISPSoft 3.24. Each could be unpacked and repacked to reproduce its original bytes. An edited single-POU copy also passed container read-back checks. **These checks do not establish that ISPSoft can compile the edited project.**

## Quick start

Requires Python 3.10 or later. The current scripts use only the Python standard library.

```powershell
python .\skills\ispsoft-isp-edit\scripts\isp_project.py inspect .\example.isp
python .\skills\ispsoft-isp-edit\scripts\isp_project.py extract-pou .\example.isp MAIN .\MAIN.pou
# Edit MAIN.pou with a script, preserving its byte encoding and CRLF line endings; save it as MAIN-edited.pou.
python .\skills\ispsoft-isp-edit\scripts\isp_project.py replace-pou .\example.isp MAIN .\MAIN-edited.pou .\example-edited.isp
```

Use `extract` and `pack` to work with the complete payload. Run `python .\skills\ispsoft-isp-edit\scripts\isp_project.py --help` for all commands. The extracted data is readable but may not be UTF-8. Check the code page declared by the project before editing, so a text editor does not silently change its encoding or line endings.

To use the skill in Codex, copy `skills/ispsoft-isp-edit` to your personal `.codex/skills/` directory. Then mention `$ispsoft-isp-edit` in a task and provide the source project and requested change.

## Scope and boundaries

- This project analyzes **project files** supplied by users. It does not modify the ISPSoft application or replace its compiler.
- Tools create a new copy by default. Open and compile the result in ISPSoft, then inspect it before deciding whether to use it on a device.
- This repository does not include user projects, PLC programs, or vendor example projects. Remove device details, passwords, and business logic before sharing a bug report.
- ISPSoft and Delta are names of their respective owners. PLC Sidecar is an independent community project with no vendor affiliation.

## Roadmap

1. Produce reviewable diffs for POUs, networks, and device references.
2. Add static checks for task order, device conflicts, and communication state handling.
3. Generate changes from declarative inputs and preview differences before writing a file.
4. Expand format coverage with anonymized fixtures and state exactly which variants are supported.

Contributions of publishable minimal fixtures, format observations, and test results are welcome. A format change should identify its evidence, provide a reproducible round-trip check, and state what remains unverified.

## License

An open-source license and `LICENSE` file must be chosen before public release. This repository draft does not yet have a license.
