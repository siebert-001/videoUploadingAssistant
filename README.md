# VideoInfoAssistant

光厂 (vjshi) 待上架视频的浏览器自动化助手，带可视化操作界面。

## 本地运行

```powershell
cd d:\www\python\VideoInfoAssistant
.\run.bat
```

或：

```powershell
.venv\Scripts\activate
python main.py
```

## 使用步骤

1. 在「视频信息」→「本地设置」中填写个人授权价（默认 80）、创作时间（默认 2026，需与网页下拉选项一致）；其余字段由程序自动填写。
2. 点击 **开始上架**，自动打开浏览器并处理列表中全部待上架视频。
3. 若未登录，在浏览器中完成微信扫码，然后点击 **登录完成，继续上架**（登录自动保存，下次可免登录；需换账号时点 **清除登录**）。
4. 运行中按钮变为 **停止上架**，点击可中断自动化。
5. 每个视频填写完成后自动点击 **提交**，再处理列表中下一个；列表全部提交完成后停止。
6. 要改间隔、是否提交、去自动化等：编辑 `src/config.py` 顶部常量后重新运行或重新打包。

## 首次环境

需已安装 **Google Chrome**（程序通过 Playwright 调用本机 Chrome）。

`run.bat` 会自动创建虚拟环境；也可手动：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

（无需 `playwright install chromium`）

## 配置

**全部写死在 `src/config.py`**。登录信息写入 **`login.json`**（Windows：exe 同目录；macOS：`~/Library/Application Support/VjshiVideoTool/`）。界面 **清除登录** 可删除，下次需重新登录。

| 想改什么 | 改哪里 |
|----------|--------|
| 点击间隔、视频间休息、是否提交 | `src/config.py` 顶部常量 |
| 去自动化特征 | `BROWSER_REDUCE_AUTOMATION_FLAGS` |
| 个人授权价、创作时间 | 界面「本地设置」里改（默认 80 / 2026，不保存文件） |
| 清除登录 | 窗口底部 **开始上架** 上方的按钮 |

## 打包为 exe

在项目目录双击或在 PowerShell 中执行：

```powershell
.\build.bat
```

完成后生成 **`dist\光厂视频上架助手.exe`** 单文件（**不含 Chromium**）：

- 直接双击 exe 运行（首次启动会稍慢）
- **电脑需已安装 Google Chrome**
- 分发单个 exe 即可

改参数请编辑 `src/config.py` 后重新执行 `build.bat` 打包。

## macOS 打包说明

- 建议将 `.app` **拖入「应用程序」** 再打开。
- 需本机已安装 **Google Chrome**。
- 登录信息保存在 `~/Library/Application Support/VjshiVideoTool/login.json`。

## 任务栏 / exe 图标

- 默认图标：`assets/icon.ico`（蓝色上传样式）
- 换成自己的图：准备 **256×256** 的 PNG，执行  
  `python scripts/generate_icon.py 你的图.png`  
  然后重新运行或 `build.bat` 打包（exe 文件图标与窗口任务栏图标会一起更新）
