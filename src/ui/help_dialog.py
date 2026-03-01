"""帮助/简介对话框"""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QApplication
from PyQt6.QtCore import Qt

from src.core.version import APP_NAME, APP_VERSION

_MIN_WIDTH = 720
_MIN_HEIGHT = 520


def _help_html(app_name: str, app_version: str) -> str:
    return f"""
<h2>{app_name} <small>v{app_version}</small></h2>
<p>用于备份/迁移 <b>通达信 T0002</b> 目录中的个人配置与数据。</p>

<h3>使用步骤</h3>
<ol>
  <li>选择有效的 <b>T0002</b> 目录（自动检测或手动浏览）。</li>
  <li>勾选需要迁移的数据项（悬停可查看说明）。</li>
  <li>导出为 ZIP / 导出到文件夹。</li>
  <li>在目标 T0002 中导入（导入前会自动备份，可回滚）。</li>
</ol>

<h3>对比/导入（两版本）</h3>
<ul>
  <li>用于在两套通达信之间迁移/同步：左→右、右→左、双向补齐缺失、双向覆盖同步。</li>
  <li>支持选择安装根目录或 T0002 目录，会自动定位到 <b>T0002</b>。</li>
  <li><b>user.ini</b> 永远不会参与对比导入（禁止项），请使用“user.ini extern 合并”。</li>
</ul>

<h3>安全等级说明</h3>
<ul>
  <li><b>安全</b>：默认全选，通常跨版本兼容。</li>
  <li><b>谨慎</b>：默认不选，跨版本/不同券商环境可能不兼容。</li>
  <li><b>禁止</b>：不允许直接复制（仅提示）。</li>
</ul>

<h3>重要注意事项</h3>
<ul>
  <li>导入/回滚前请先完全关闭通达信主程序。</li>
  <li>导入会覆盖同名文件；工具会先自动备份被覆盖文件。</li>
  <li>单文件 EXE 运行与对比导入会使用当前目录的 <code>temp</code> 文件夹作为临时目录，请确保可写。</li>
  <li><b>user.ini 禁止整体复制</b>：跨版本整体复制可能导致闪退。请使用“<b>user.ini extern 合并</b>”仅迁移 <code>extern_*</code> 段落。</li>
</ul>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("使用说明/简介")
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        app = QApplication.instance()
        app_name = app.applicationName() if app else APP_NAME
        app_version = app.applicationVersion() if app else APP_VERSION

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_help_html(app_name, app_version))
        layout.addWidget(browser)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
