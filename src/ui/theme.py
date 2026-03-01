"""全局浅色主题（QSS）"""
from __future__ import annotations

_BG = "#F8FAFC"
_CARD = "#FFFFFF"
_TEXT = "#0F172A"
_TEXT_MUTED = "#475569"
_BORDER = "#E5E7EB"
_BORDER_STRONG = "#CBD5E1"
_PRIMARY = "#1E40AF"
_PRIMARY_HOVER = "#1D4ED8"
_CTA = "#F59E0B"
_CTA_HOVER = "#FBBF24"
_DANGER = "#EF4444"
_DANGER_BG = "#FEF2F2"
_SELECT = "#DBEAFE"

_RADIUS = 10
_RADIUS_SM = 8
_PADDING = "6px 10px"

APP_STYLE_SHEET = f"""
QMainWindow, QWidget {{
  background: {_BG};
  color: {_TEXT};
  font-size: 12px;
}}

QGroupBox {{
  background: {_CARD};
  border: 1px solid {_BORDER};
  border-radius: {_RADIUS}px;
  margin-top: 12px;
  padding: 10px;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 12px;
  padding: 0 6px;
  color: {_TEXT_MUTED};
}}

QLineEdit, QComboBox, QTextEdit, QTextBrowser, QTreeWidget {{
  background: {_CARD};
  border: 1px solid {_BORDER};
  border-radius: {_RADIUS_SM}px;
  padding: {_PADDING};
}}

QComboBox::drop-down {{
  border: 0px;
  width: 22px;
}}

QHeaderView::section {{
  background: #F1F5F9;
  color: {_TEXT_MUTED};
  padding: 8px 10px;
  border: 0px;
  font-weight: 600;
}}

QTreeWidget::item {{
  padding: 6px 6px;
}}
QTreeWidget::item:selected {{
  background: {_SELECT};
  color: {_TEXT};
}}

QSplitter::handle {{
  background: transparent;
}}

QPushButton {{
  background: {_CARD};
  border: 1px solid {_BORDER_STRONG};
  border-radius: {_RADIUS_SM}px;
  padding: {_PADDING};
}}
QPushButton:hover {{
  background: #F1F5F9;
  border-color: #94A3B8;
}}
QPushButton:pressed {{
  background: #E2E8F0;
}}
QPushButton:disabled {{
  color: #94A3B8;
  background: {_BG};
  border-color: {_BORDER};
}}

QPushButton#primaryButton {{
  background: {_PRIMARY};
  border-color: {_PRIMARY};
  color: #FFFFFF;
  font-weight: 600;
}}
QPushButton#primaryButton:hover {{
  background: {_PRIMARY_HOVER};
  border-color: {_PRIMARY_HOVER};
}}

QPushButton#warningButton {{
  background: {_CTA};
  border-color: {_CTA};
  color: #111827;
  font-weight: 600;
}}
QPushButton#warningButton:hover {{
  background: {_CTA_HOVER};
  border-color: {_CTA_HOVER};
}}

QPushButton#dangerButton {{
  background: {_DANGER_BG};
  border-color: {_DANGER};
  color: #B91C1C;
  font-weight: 600;
}}
QPushButton#dangerButton:hover {{
  background: #FEE2E2;
}}

QPushButton#linkButton {{
  background: transparent;
  border: 1px solid transparent;
  color: {_PRIMARY};
  text-decoration: underline;
  padding: 6px 8px;
}}
QPushButton#linkButton:hover {{
  background: #EFF6FF;
  border-color: #BFDBFE;
  border-radius: {_RADIUS_SM}px;
  text-decoration: none;
}}
"""
