---
name: tdx-hevo-sync
description: 通达信 T0002 本地配置备份/迁移/对比工具（TdxHevoSyncTool，PyQt6 GUI，本机 git repo）。导出/导入 T0002 个人配置（自选股+自定板块、自编指标与指标模板、指标 DLL、自定义数据、配色方案、策略股池、金融记事本、条件选股 *.czs/*.cos、版面/栏目等）为 ZIP 或文件夹（带 manifest.json 文件哈希校验）；导入前自动备份、可一键回滚；支持两套 T0002 差异对比与单向导入/双向同步；user.ini 禁止整体复制，仅允许「user.ini 定向同步」按 section 迁移。触发词=通达信备份/通达信配置备份/通达信配置迁移/T0002备份/T0002迁移/通达信换电脑/通达信配置同步/通达信配置转移/tdx备份/tdx配置迁移。
---

# tdx-hevo-sync（通达信 T0002 配置备份/迁移工具）

**仓库**：独立 git repo，remote `git@github.com:leonsong09/TdxHevoSyncTool.git`（克隆到本机任意目录即可）

> 家族成员之一，家族总入口见上级 `README.md`（同花顺/通达信 本地客户端工具族）。

## 1. 用途

备份 / 迁移 **通达信 `T0002` 目录**里的个人配置数据，用于「老版本→新版本」「本机→另一台电脑」的迁移与同步。

## 2. 入口

```powershell
# 开发模式（GUI）
python main.py                 # 需先: python -m pip install -r requirements.txt

# 已打包单文件 EXE（免装环境）
.\dist\TdxHevoSyncTool.exe

# 打包（生成单文件 EXE）
.\build_gui.bat                # 或 PyInstaller TdxHevoSyncTool.spec
```

> 使用前**必须先关闭通达信主程序**。

## 2.1 命令行（CLI，GA/脚本无头调用）

与 GUI 共用 `src/core` 全部逻辑，不弹窗。入口 `cli.py`（仓库根目录）：

```powershell
python cli.py items                                  # 列出全部数据项（id/安全级别/路径）
python cli.py discover                               # 自动检测本机 T0002
python cli.py export --t0002 <T0002> --out <目录> [--items a,b | --level safe | --all] [--mode zip|folder]
python cli.py import --src <zip|目录> --t0002 <T0002> [--items a,b] [--apply]
python cli.py compare --left <T0002> --right <T0002> [--items a,b]
python cli.py plan    --left <T0002> --right <T0002> --mode l2r|r2l|bi-missing|bi-sync
                      [--strategy diff|missing|full] [--conflict left|right|mtime]
python cli.py rollback --backup <.tdx_backup_xxx> --t0002 <T0002> [--apply]
python cli.py userini  --src <user.ini> --dst <user.ini> [--apply]
```

- **约定**：所有**写**操作（`import`/`rollback`/`userini`）默认**预演**，必须显式加 `--apply` 才落盘；`export` 只读源配置、写新包（安全）。
- 缺省数据项 = `safe` 全选；`--level caution` 才含谨慎项；`forbidden`（user.ini）永不被选中。
- 检测到通达信进程在运行会直接报错退出（与 GUI 同一判据）。
- 退出码：`0` 成功 / `1` 业务失败 / `2` 用法错误。
- 已实测：items / discover / export / import(预演+`--apply`) / compare / plan / rollback / userini(预演+`--apply`) 全通。
- `pip install -e .` 后也可用入口名 `tdx-sync-cli`。

## 3. 核心操作

| 操作 | 说明 |
|---|---|
| 选择 T0002 | 自动检测 + 手动选择；支持选**安装根目录**或 **T0002 目录**（自动定位） |
| 导出 | 打包为 ZIP / 导出到文件夹，附 `manifest.json`（含每文件相对路径/大小/mtime/SHA256） |
| 导入 | 从 ZIP / 文件夹导入到目标 T0002；导入前**自动备份**，失败可「回滚上次导入」 |
| 对比/导入（两版本） | 左右各选一套 T0002 → 差异摘要 + 文件预览 → 单向导入（仅差异/仅补齐缺失/全量覆盖）或双向同步（仅补齐缺失/覆盖同步：以左/以右/按修改时间较新） |

## 4. 数据项与安全等级

- **安全（默认全选）**：`blocknew`(自定板块+自选股,含 `blocknew.cfg`)、`indicators`(PriBand/PriCS/PriGS/PriLoc/PriPack 等)、`indicator_dll`(`dll`/`dlls`)、`signals`(自定义数据)、`scheme`(配色方案)、`tpool`(策略股池)、`note`(金融记事本)、`cmd`(配置工具脚本)、条件选股 `*.czs`/`*.cos`
- **谨慎（默认不选）**：`pad`/`cloud_pad*`(版面配置)、`colwidth`(栏目定制) 等 —— 跨版本/跨券商环境可能不兼容，导入后异常请回滚
- **禁止（仅提示）**：`user.ini` —— 跨版本整体复制可能闪退，**不允许**直接导入/导出

### user.ini 定向同步（唯一允许的 user.ini 操作）

- 普通 section：只替换目标中**已存在且值不同**的键
- `extern_*`：替换同名异值键，并追加目标中缺失的键
- 目标中不存在的 section 会跳过，**不新增段落**

## 5. 关键口径

- 所有路径均为**相对 T0002** 的路径；`manifest.json` 记录工具版本/创建时间/源路径/选中分类/每文件 SHA256
- 导入时按 manifest 做 SHA256 校验
- 新版本目录名变化已兼容：`dll`↔`dlls`、`PriPack def.dat`↔`PriPack_def.dat`、`Scheme.dat`↔`scheme.dat`

## 6. 测试

```powershell
python -m unittest discover -s tests -v
```

## 7. 边界

- 本工具**只读写用户自己的 T0002 配置**，不触碰行情数据、不联网上传
- 打包/发布前先关通达信；导入目标机若目录不存在，需先正常启动一次通达信
