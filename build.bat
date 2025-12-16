@echo off
chcp 65001
echo 正在打包程序...
pyinstaller --noconsole --onefile --name "LandingPageFetcher" crawler_app.py
echo.
echo 打包完成！
echo 可执行文件位于 dist 文件夹中：dist\LandingPageFetcher.exe
echo.
pause
