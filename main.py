"""启动可视化操作界面。"""
from src.config import init_app, setup_playwright_env
from src.gui import main

if __name__ == "__main__":
    init_app()
    setup_playwright_env()
    main()
