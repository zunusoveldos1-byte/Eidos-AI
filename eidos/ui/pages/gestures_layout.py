"""Video-first camera workspace with a separate full-height settings page."""
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QGridLayout, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QStackedWidget, QScrollArea, QGraphicsDropShadowEffect)
from eidos.ui.localized import QWidget
from ..components import ResponsiveRow, label, button
from .settings_layout import clear_page


def rebuild(page):
    fields = [(title, getattr(page, name)) for title, name in (
        ('Ведущая рука', 'hand'), ('Разрешение', 'resolution'), ('Анализ, кадров/с', 'fps'),
        ('Чувствительность курсора', 'sensitivity'), ('Сглаживание (больше — быстрее)', 'smoothing'),
        ('Мёртвая зона громкости, %', 'volume_dead'), ('Интервал громкости, с', 'volume_interval'),
        ('Удержание ладони, с', 'hold'), ('Защита повтора, с', 'cooldown'),
        ('Минимум расстояния / ладонь', 'pinch_min'), ('Максимум расстояния / ладонь', 'pinch_max'),
        ('Монитор курсора (физические пиксели)', 'monitor'), ('Аварийное отключение', 'emergency_key'),
        ('Отображение', 'mirror'), ('Разметка', 'overlay'), ('Управление', 'mode'))]
    controls = [c for _, c in fields] + [page.preview, page.camera, page.camera_button,
        page.refresh_button, page.control, page.emergency_button, page.details_button,
        page.parameters, page.save_button, page.calibration_text, page.calibrate_button,
        page.calibrate_next, page.calibrate_skip, page.calibrate_reset,
        page.gesture_status, page.metrics, page.feedback]
    for control in controls:
        control.setParent(page.content)
    clear_page(page, keep_header=True)
    page.details_button.toggled.disconnect()
    for c in (page.camera_status, page.recognition_status, page.hand_status,
              page.action_status, page.volume_status, page.hotkey_status, page.emergency_button):
        c.hide()
    page.camera_pages = QStackedWidget()
    page.camera_pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page.body.addWidget(page.camera_pages, 1)
    video_page = QWidget()
    video_layout = QVBoxLayout(video_page)
    video_layout.setContentsMargins(0, 0, 0, 0)
    page.preview.setMinimumHeight(180)
    page.preview.setMaximumHeight(16777215)
    page.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    video_layout.addWidget(page.preview, 1)
    page.preview.show()
    page.camera_pages.addWidget(video_page)

    page.video_toolbar = QWidget(page.preview)
    page.video_toolbar.setObjectName('videoToolbar')
    page.video_toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    toolbar = QGridLayout(page.video_toolbar)
    toolbar.setContentsMargins(12, 10, 12, 10)
    toolbar.setSpacing(12)
    page.camera.setFixedWidth(180)
    page._camera_button_state(False)
    page.camera_button.setObjectName('cameraAction')
    page.camera_button.setStyleSheet('QPushButton { background: #0F1714; color: #E2E8F0; '
        'border: 1px solid #1E2923; border-radius: 22px; padding: 0; } '
        'QPushButton[active="true"] { background: #164A35; border-color: #10B981; } '
        'QPushButton:hover { border-color: #10B981; }')
    for control in (page.camera_button, page.refresh_button):
        control.setFixedSize(44, 44)
    page.refresh_button.setToolTip('Обновить устройства')
    page.refresh_button.setAccessibleName('Обновить устройства')
    page.refresh_button.setText('')
    toolbar_controls = [page.camera, page.camera_button, page.control, page.refresh_button, page.details_button]
    def reflow(width):
        compact = width < 650
        if getattr(page.video_toolbar, '_compact', None) == compact: return
        page.video_toolbar._compact = compact
        while toolbar.count(): toolbar.takeAt(0)
        if compact:
            toolbar.addWidget(page.camera, 0, 0, 1, 4)
            for index, control in enumerate(toolbar_controls[1:]): toolbar.addWidget(control, 1, index)
        else:
            for index, control in enumerate(toolbar_controls): toolbar.addWidget(control, 0, index)
    page.video_toolbar.reflow = reflow
    reflow(page.width())
    for control in (page.camera, page.camera_button, page.control, page.refresh_button, page.details_button):
        control.show()
    shadow = QGraphicsDropShadowEffect(page.video_toolbar)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 5)
    shadow.setColor(QColor(0, 0, 0, 150))
    page.video_toolbar.setGraphicsEffect(shadow)
    page.preview.toolbar = page.video_toolbar
    page.video_toolbar.show()
    for badge in (page.gesture_status, page.metrics):
        badge.setParent(page.preview)
        badge.setStyleSheet('background: rgba(11,17,15,205); color: #E2E8F0; '
                           'border: 1px solid rgba(37,230,161,70); border-radius: 9px; padding: 6px 10px; font-size: 12px;')
        badge.show()
    page.preview.gesture_badge, page.preview.metrics_badge = page.gesture_status, page.metrics
    page.metrics.setText('— FPS | — мс')
    page.preview.position_badges()

    page.calibration_page = QWidget()
    page.camera_pages.addWidget(page.calibration_page)
    settings_layout = QVBoxLayout(page.calibration_page)
    settings_layout.setContentsMargins(0, 0, 0, 0)
    settings_layout.setSpacing(12)
    heading = QHBoxLayout()
    page.back_to_camera = button('Камера и жесты', 'chevron-left')
    heading.addWidget(page.back_to_camera)
    heading.addWidget(label('Параметры и калибровка', 'h2'), 1)
    settings_layout.addLayout(heading)
    page.calibration_scroll = QScrollArea()
    page.calibration_scroll.setWidgetResizable(True)
    page.calibration_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    settings_layout.addWidget(page.calibration_scroll, 1)
    settings_host = QWidget()
    settings_host.setObjectName('cameraSettings')
    settings_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    outer = QVBoxLayout(settings_host)
    outer.setContentsMargins(4, 4, 4, 4)
    outer.setSpacing(16)
    page.calibration_scroll.setWidget(settings_host)
    for caption in page.parameters.findChildren(QLabel): caption.hide()
    sip.delete(page.parameters.layout())
    grid = QGridLayout(page.parameters)
    grid.setContentsMargins(16, 20, 16, 16)
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(16)
    cells = []
    for index, (title, control) in enumerate(fields):
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(label(title, 'muted'))
        layout.addWidget(control)
        control.setMinimumWidth(0)
        control.show()
        grid.addWidget(group, index // 3, index % 3)
        cells.append(group)
    page.mirror.setToolTip(page.mirror.source_text())
    page.mirror.setText('Зеркальный предпросмотр')
    outer.addWidget(page.parameters)
    page.parameters.show()
    outer.addWidget(page.calibration_text)
    outer.addWidget(ResponsiveRow([page.calibrate_button, page.calibrate_next,
        page.calibrate_skip, page.calibrate_reset], threshold=600, spacing=10))
    outer.addStretch()
    settings_layout.addWidget(page.save_button)
    page.save_button.setStyleSheet('background: #10B981; color: #061B12; border-radius: 8px; padding: 12px;')
    for c in (page.calibration_text, page.calibrate_button, page.calibrate_next,
              page.calibrate_skip, page.calibrate_reset, page.save_button): c.show()
    page.details_button.toggled.connect(lambda opened: page.camera_pages.setCurrentIndex(1 if opened else 0))
    page.back_to_camera.clicked.connect(lambda: page.details_button.setChecked(False))

    def resize_content(expanded):
        columns = 2 if page.width() < 900 else 3
        if getattr(page, '_parameter_columns', 3) != columns:
            while grid.count(): grid.takeAt(0)
            for index, cell in enumerate(cells): grid.addWidget(cell, index // columns, index % columns)
            page._parameter_columns = columns
        # Keep the whole main surface within the viewport; only the settings grid scrolls.
        page.content.setMinimumHeight(0)
        page.video_toolbar.reflow(page.preview.width())
        page.preview.toolbar.adjustSize()
        page.preview.toolbar.move(max(8, (page.preview.width() - page.preview.toolbar.width()) // 2),
                                  max(8, page.preview.height() - page.preview.toolbar.height() - 20))
    page._resize_preview = resize_content
    page.setStyleSheet('''
        QWidget { font-size: 12px; }
        QLabel#h1 { font-size: 24px; } QLabel#subtitle { font-size: 13px; }
        QWidget#videoToolbar { background: rgba(11,17,15,225); border: 1px solid #1E2923; border-radius: 16px; }
        QWidget#cameraSettings { background: #0B110F; }
        QScrollArea { background: transparent; border: none; }
        QGroupBox { background: #0B110F; border: 1px solid #1E2923; border-radius: 12px; }
        QPushButton { padding: 8px 10px; }
        QPushButton#cameraAction { background: #0F1714; border: 1px solid #1E2923; border-radius: 22px; padding: 0; }
        QPushButton#cameraAction[active="true"] { background: #164A35; border-color: #10B981; }
        QPushButton:hover { border-color: #10B981; }
        QComboBox { padding: 6px 24px 6px 8px; }
    ''')
