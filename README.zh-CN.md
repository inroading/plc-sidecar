# PLC Sidecar

[English](README.md) | 简体中文

**开放的 PLC 工程辅助工具集。让工程文件更容易检查、修改和协作，把最终编译与 PLC 上传下载留给厂商软件。**

PLC 工程常被保存在难以阅读和比较的专有文件中。PLC Sidecar 希望提供一组独立的小工具，用于离线检查工程结构、生成可审查的修改副本，以及在交给厂商 IDE 前发现明显问题。项目从 Delta ISPSoft 的 `.isp` 工程文件开始，未来可以加入其他格式和工作流。

> 当前处于实验阶段。工具的结构校验不能代替 ISPSoft 编译、仿真或现场验证。

## 已有工具

### `ispsoft-isp-edit`

这是一个可供 Codex 调用的 skill，同时包含独立的 Python 命令行工具。它针对目前观察到的 ISPSoft 3.24 `.isp` 容器格式，支持：

- 查看工程名称、任务中的 POU 顺序、各 POU 的网络数量等信息；
- 提取完整工程内容或单个 POU，供脚本分析和编辑；
- 将修改后的内容重新封装为**新的** `.isp` 文件，检查长度、CRC32 和读取结果；
- 拒绝覆盖源工程，遇到未识别的文件布局时停止写入；
- 提供一组基于已观察样例的 LD 节点构造函数。

目前仅验证了一个 EC3 工程和六个随 ISPSoft 3.24 安装的示例工程：它们都能原样解包、重新封装并逐字节还原；单个 POU 的修改副本也通过了容器读取校验。这**不表示**修改后的工程已经通过 ISPSoft 编译。

## 快速开始

需要 Python 3.10 或更新版本；当前脚本只使用 Python 标准库。

```powershell
python .\skills\ispsoft-isp-edit\scripts\isp_project.py inspect .\example.isp
python .\skills\ispsoft-isp-edit\scripts\isp_project.py extract-pou .\example.isp MAIN .\MAIN.pou
# 用脚本编辑 MAIN.pou，保留原有字节编码和 CRLF 换行，保存为 MAIN-edited.pou
python .\skills\ispsoft-isp-edit\scripts\isp_project.py replace-pou .\example.isp MAIN .\MAIN-edited.pou .\example-edited.isp
```

`extract` 和 `pack` 命令可用于编辑整个解包后的工程内容。查看完整参数可运行 `python .\skills\ispsoft-isp-edit\scripts\isp_project.py --help`。解包内容虽然可读，但未必是 UTF-8；编辑前应检查工程声明的代码页，避免文本编辑器改变编码或换行。

在 Codex 中使用时，将 `skills/ispsoft-isp-edit` 目录放入个人的 `.codex/skills/`，然后在任务中指定 `$ispsoft-isp-edit`，并提供源工程与修改要求。

## 工作边界

- 本项目分析和处理用户提供的**工程文件**，不修改 ISPSoft 程序本体，也不把它作为编译器替代品。
- 工具默认产出新副本；用户应在 ISPSoft 中打开、编译并检查结果，再决定是否用于设备。
- 项目不会附带用户工程、PLC 程序或厂商示例工程。提交问题时请移除设备信息、口令和业务逻辑等敏感内容。
- ISPSoft 和 Delta 名称归其权利人所有；PLC Sidecar 是独立社区项目，与厂商没有关联。

## 接下来想做什么

1. 生成便于代码审查的 POU、网络和设备引用差异报告。
2. 增加任务顺序、设备冲突和通信状态处理等静态检查。
3. 让工程修改可以通过声明式配置生成，并在写入前预览差异。
4. 用匿名化测试样本逐步扩展格式覆盖范围，明确每种版本的支持状态。

欢迎提供可公开的最小复现样本、格式观察和测试结果。格式相关改动应说明样本来源、可复现的往返测试，以及仍未验证的部分。

## 许可证

正式发布前需要选择开源许可证并添加 `LICENSE` 文件。当前仓库草稿尚未确定许可证。
