#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Advanced Image Editing Application
Main entry point for the application
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QToolBar, QToolButton, QWidget, QSizePolicy
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QIcon, QPixmap, QAction
from tempusloom.main_window import MainWindow
from tempusloom.utils.logger import setup_logger
from tempusloom.config import Config


def main():
    """Main entry point for the application"""
    # Set up logging
    setup_logger()
    
    # Load configuration
    config = Config()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("TempusLoom")
    app.setOrganizationName("TempusLoom")
    app.setOrganizationDomain("tempusloom.com")
    
    # Set application style and theme
    from tempusloom.ui.styling import apply_style
    apply_style(app, config.get('ui', 'theme', 'dark'))
    
    # Create and show main window
    window = MainWindow(config)
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 