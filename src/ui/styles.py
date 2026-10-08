class ModernStyles:
    """CSS styling tokens and modern dark theme for AutoDraw V2."""

    MAIN_STYLE = """
    QMainWindow, QDialog {
        background-color: #0F1017;
        color: #E2E8F0;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    QWidget {
        color: #E2E8F0;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    /* Cards & Containers */
    QFrame#Card {
        background-color: #171926;
        border: 1px solid #2A2D42;
        border-radius: 12px;
    }

    QFrame#CardHeader {
        background-color: #1E2034;
        border-bottom: 1px solid #2A2D42;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }

    /* Dropdown ComboBox */
    QComboBox {
        background-color: #1E2034;
        color: #FFFFFF;
        border: 1px solid #3F4468;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 13px;
        font-weight: 600;
        min-width: 140px;
    }

    QComboBox:hover {
        border-color: #6366F1;
        background-color: #262940;
    }

    QComboBox::drop-down {
        border: none;
        width: 24px;
    }

    QComboBox QAbstractItemView {
        background-color: #1E2034;
        color: #FFFFFF;
        selection-background-color: #4F46E5;
        border: 1px solid #3F4468;
        border-radius: 6px;
        padding: 4px;
    }

    /* Labels */
    QLabel {
        color: #E2E8F0;
        font-size: 13px;
    }

    QLabel#HeaderTitle {
        font-size: 24px;
        font-weight: bold;
        color: #FFFFFF;
    }

    QLabel#HeaderSubtitle {
        font-size: 13px;
        color: #94A3B8;
    }

    QLabel#SectionTitle {
        font-size: 14px;
        font-weight: 600;
        color: #C7D2FE;
    }

    QLabel#Badge {
        background-color: #262940;
        border: 1px solid #3F4468;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        color: #A5B4FC;
    }

    QLabel#BadgeSuccess {
        background-color: #143224;
        border: 1px solid #1E5E3A;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
        color: #4ADE80;
    }

    QLabel#BadgeWarning {
        background-color: #3B2012;
        border: 1px solid #7C3D12;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
        color: #FDBA74;
    }

    /* Buttons */
    QPushButton {
        background-color: #282B40;
        color: #F1F5F9;
        border: 1px solid #3F4468;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }

    QPushButton:hover {
        background-color: #323652;
        border-color: #6366F1;
        color: #FFFFFF;
    }

    QPushButton:pressed {
        background-color: #1E2034;
    }

    QPushButton#PrimaryButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
        color: #FFFFFF;
        border: none;
        font-weight: bold;
        font-size: 15px;
        border-radius: 10px;
        padding: 12px 24px;
    }

    QPushButton#PrimaryButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366F1, stop:1 #8B5CF6);
    }

    QPushButton#PrimaryButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338CA, stop:1 #6D28D9);
    }

    QPushButton#PrimaryButton:disabled {
        background: #25283B;
        color: #64748B;
        border: 1px solid #334155;
    }

    QPushButton#DangerButton {
        background-color: #7F1D1D;
        color: #FEE2E2;
        border: 1px solid #991B1B;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
    }

    QPushButton#DangerButton:hover {
        background-color: #991B1B;
        border-color: #EF4444;
    }

    QPushButton#PillButton {
        background-color: #1E2034;
        color: #94A3B8;
        border: 1px solid #2A2D42;
        border-radius: 14px;
        padding: 4px 10px;
        font-size: 11px;
    }

    QPushButton#PillButton:hover {
        background-color: #282B40;
        color: #E2E8F0;
        border-color: #4F46E5;
    }

    QPushButton#TabButton {
        background-color: #171926;
        color: #94A3B8;
        border: 1px solid #2A2D42;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
    }

    QPushButton#TabButton:checked {
        background-color: #3730A3;
        color: #FFFFFF;
        border-color: #6366F1;
        font-weight: bold;
    }

    /* Radio Buttons & Checkboxes */
    QRadioButton, QCheckBox {
        color: #CBD5E1;
        font-size: 13px;
        spacing: 8px;
    }

    QRadioButton::indicator, QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid #475569;
        background-color: #1E2034;
    }

    QRadioButton::indicator:checked, QCheckBox::indicator:checked {
        background-color: #6366F1;
        border-color: #818CF8;
    }

    /* Sliders */
    QSlider::groove:horizontal {
        height: 6px;
        background: #23263B;
        border-radius: 3px;
    }

    QSlider::sub-page:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #8B5CF6);
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        background: #FFFFFF;
        border: 2px solid #6366F1;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }

    QSlider::handle:horizontal:hover {
        background: #E0E7FF;
        border-color: #818CF8;
    }

    /* Progress Bar */
    QProgressBar {
        border: 1px solid #2D314E;
        background-color: #171926;
        border-radius: 8px;
        text-align: center;
        color: #FFFFFF;
        font-weight: bold;
        height: 22px;
    }

    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #10B981);
        border-radius: 7px;
    }
    """
