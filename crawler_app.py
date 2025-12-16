import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from playwright.sync_api import sync_playwright
import time
import os
import sys
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import threading

# 确保打包后能找到 playwright 模块
try:
    import playwright.__main__
except ImportError:
    pass

# 设置 Playwright 浏览器下载路径为程序同级目录下的 browsers 文件夹
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_dir, "browsers")

# 注意：
# 本工具仅供学习、测试及合法的数据采集使用。
# 请勿用于克隆、抄袭或侵犯他人版权的网站内容。
# 遵守目标网站的 robots.txt 协议。

class BrowserCrawlerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("落地页获取器")
        self.root.geometry("800x600")

        self.playwright = None
        self.browser = None
        self.page = None
        self.context = None
        self.proxy_config = None # Store Playwright proxy config
        self.requests_proxy = None # Store requests proxy string

        # UI Components
        self.create_widgets()

    def create_widgets(self):
        # Create Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Tab 1: Crawler
        self.crawler_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.crawler_tab, text="采集器")
        self.create_crawler_widgets(self.crawler_tab)

        # Tab 2: Editor
        self.editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="编辑器")
        self.create_editor_widgets(self.editor_tab)

    def create_crawler_widgets(self, parent):
        # URL Input
        url_frame = ttk.LabelFrame(parent, text="目标网址")
        url_frame.pack(fill="x", padx=10, pady=5)
        
        self.url_var = tk.StringVar(value="https://www.example.com")
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        self.url_entry.pack(fill="x", padx=5, pady=5)

        # Settings Frame (UA + Proxy)
        settings_frame = ttk.LabelFrame(parent, text="浏览器设置")
        settings_frame.pack(fill="x", padx=10, pady=5)

        # User-Agent
        ttk.Label(settings_frame, text="User-Agent:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ua_map = {
            "PC (Windows Chrome)": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "MacOS (Chrome)": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "iOS (iPhone Safari)": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Android (Chrome Mobile)": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        }
        self.ua_var = tk.StringVar()
        self.ua_combobox = ttk.Combobox(settings_frame, textvariable=self.ua_var, state="readonly", width=40)
        self.ua_combobox['values'] = list(self.ua_map.keys())
        self.ua_combobox.current(0)
        self.ua_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Proxy
        ttk.Label(settings_frame, text="代理IP (可选):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.proxy_var = tk.StringVar()
        self.proxy_entry = ttk.Entry(settings_frame, textvariable=self.proxy_var, width=40)
        self.proxy_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(settings_frame, text="支持: http/socks5://user:pass@ip:port").grid(row=1, column=2, padx=5, pady=5, sticky="w")

        settings_frame.columnconfigure(1, weight=1)

        # Controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.btn_launch = ttk.Button(control_frame, text="启动浏览器", command=self.launch_browser)
        self.btn_launch.pack(side="left", padx=5)

        self.btn_navigate = ttk.Button(control_frame, text="访问页面", command=self.navigate_to_url, state="disabled")
        self.btn_navigate.pack(side="left", padx=5)

        self.btn_save = ttk.Button(control_frame, text="保存页面源码", command=self.save_content, state="disabled")
        self.btn_save.pack(side="left", padx=5)

        self.btn_close = ttk.Button(control_frame, text="关闭浏览器", command=self.close_browser, state="disabled")
        self.btn_close.pack(side="left", padx=5)

        # Status Log
        log_frame = ttk.LabelFrame(parent, text="日志")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def create_editor_widgets(self, parent):
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="打开 HTML 文件", command=self.load_html_for_editing).pack(side="left", padx=5)
        ttk.Button(toolbar, text="保存修改", command=self.save_edited_html).pack(side="left", padx=5)
        
        # Treeview for resources
        columns = ("type", "original", "new")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings")
        self.tree.heading("type", text="类型")
        self.tree.heading("original", text="原始值 (双击修改新值)")
        self.tree.heading("new", text="新值")
        
        self.tree.column("type", width=100, stretch=False)
        self.tree.column("original", width=300)
        self.tree.column("new", width=300)
        
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        scrollbar.place(relx=1, rely=0, relheight=1, anchor="ne")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Bind double click
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        self.current_soup = None
        self.current_html_path = None
        self.tree_items_map = {} # Map item ID to tag object

    def log(self, message):
        def _log():
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
        self.root.after(0, _log)

    def launch_browser(self):
        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()
            
            selected_ua_name = self.ua_var.get()
            ua = self.ua_map.get(selected_ua_name, selected_ua_name)
            
            proxy_input = self.proxy_var.get().strip()
            self.proxy_config = None
            self.requests_proxy = None
            
            if proxy_input:
                # 自动补全 scheme
                if "://" not in proxy_input:
                    proxy_input = f"http://{proxy_input}"
                
                try:
                    parsed = urlparse(proxy_input)
                    scheme = parsed.scheme
                    hostname = parsed.hostname
                    port = parsed.port
                    username = parsed.username
                    password = parsed.password
                    
                    if not hostname or not port:
                        self.log(f"代理地址格式错误: {proxy_input}")
                        # 继续尝试，可能 Playwright 能处理
                    
                    # 重组 server 地址 (去除 user:pass)
                    server_url = f"{scheme}://{hostname}:{port}"
                    
                    self.proxy_config = {
                        "server": server_url
                    }
                    if username:
                        self.proxy_config["username"] = username
                    if password:
                        self.proxy_config["password"] = password
                        
                    # 构造 requests 用的 proxy 字符串 (包含 auth)
                    # requests 格式: scheme://user:pass@host:port
                    if username and password:
                        self.requests_proxy = f"{scheme}://{username}:{password}@{hostname}:{port}"
                    else:
                        self.requests_proxy = server_url
                        
                    self.log(f"正在启动浏览器，模式: {selected_ua_name}")
                    self.log(f"代理: {server_url} (用户: {username if username else '无'})")
                    
                except Exception as e:
                    self.log(f"代理解析失败: {e}")
                    self.proxy_config = None
            else:
                self.log(f"正在启动浏览器，模式: {selected_ua_name}, 无代理")
            
            # Launch browser (headless=False means visible GUI)
            try:
                self.browser = self.playwright.chromium.launch(headless=False)
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    if messagebox.askyesno("提示", "检测到缺少浏览器内核，是否立即下载？\n(将下载到程序同级 browsers 文件夹，约 150MB)"):
                        self.install_browser_kernel()
                        return
                raise e
            
            # Create context with specific User-Agent and Proxy
            if self.proxy_config:
                self.context = self.browser.new_context(user_agent=ua, proxy=self.proxy_config)
            else:
                self.context = self.browser.new_context(user_agent=ua)
                
            self.page = self.context.new_page()
            
            self.log("浏览器已启动。")
            self.update_buttons(running=True)
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
            self.log(f"错误: {str(e)}")

    def install_browser_kernel(self):
        self.log("正在下载浏览器内核，请稍候...")
        self.btn_launch.config(state="disabled")
        
        def _install():
            try:
                # 在打包环境中，我们通过调用自身并传递特殊参数来触发安装
                # 或者直接调用 playwright 模块（如果能导入）
                # 这里使用 subprocess 调用自身副本或 python 解释器
                
                if getattr(sys, 'frozen', False):
                    # 打包后的 exe
                    subprocess.run([sys.executable, "--install-browsers"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    # 开发环境
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    
                self.log("浏览器内核下载完成！请重新点击启动。")
                messagebox.showinfo("成功", "浏览器内核下载完成！\n请重新点击'启动浏览器'。")
            except Exception as e:
                self.log(f"下载失败: {e}")
                messagebox.showerror("下载失败", f"无法下载浏览器内核: {e}\n请检查网络或手动下载。")
            finally:
                self.root.after(0, lambda: self.btn_launch.config(state="normal"))
                
        threading.Thread(target=_install, daemon=True).start()

    def navigate_to_url(self):
        if self.page:
            url = self.url_var.get()
            try:
                self.log(f"正在访问: {url}")
                self.page.goto(url)
                self.log("页面加载完成。")
            except Exception as e:
                self.log(f"访问失败: {str(e)}")

    def save_content(self):
        if not self.page:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        # 在主线程中获取所有必要数据，避免在子线程中调用 Playwright 对象
        try:
            content = self.page.content()
            base_url = self.page.url
            # 获取 cookies
            cookies = {c['name']: c['value'] for c in self.context.cookies()}
            # 获取当前使用的 UA
            selected_ua_name = self.ua_var.get()
            user_agent = self.ua_map.get(selected_ua_name, selected_ua_name)
            # 获取代理配置
            requests_proxy = self.requests_proxy
        except Exception as e:
            self.log(f"获取页面数据失败: {str(e)}")
            return

        # 使用线程避免阻塞 GUI
        threading.Thread(
            target=self._save_page_complete, 
            args=(file_path, content, base_url, cookies, user_agent, requests_proxy), 
            daemon=True
        ).start()

    def _save_page_complete(self, file_path, content, base_url, cookies, user_agent, requests_proxy):
        try:
            self.log("开始下载页面及资源...")
            
            # 2. 创建资源文件夹
            file_name = os.path.basename(file_path)
            file_dir = os.path.dirname(file_path)
            name_without_ext = os.path.splitext(file_name)[0]
            resources_dir_name = f"{name_without_ext}_files"
            resources_dir_path = os.path.join(file_dir, resources_dir_name)
            
            if not os.path.exists(resources_dir_path):
                os.makedirs(resources_dir_path)
            
            # 3. 解析 HTML
            soup = BeautifulSoup(content, "html.parser")
            
            # 4. 定义需要下载的标签和属性
            tags_to_download = [
                ("img", "src"),
                ("link", "href"),
                ("script", "src"),
            ]
            
            count = 0
            # 5. 遍历并下载资源
            for tag_name, attr_name in tags_to_download:
                for tag in soup.find_all(tag_name):
                    url = tag.get(attr_name)
                    if not url:
                        continue
                        
                    # 跳过 data: 和 javascript: 开头的链接
                    if url.startswith("data:") or url.startswith("javascript:") or url.startswith("#"):
                        continue
                        
                    # 转换为绝对路径
                    abs_url = urljoin(base_url, url)
                    
                    # 获取文件名
                    parsed_url = urlparse(abs_url)
                    resource_filename = os.path.basename(parsed_url.path)
                    if not resource_filename:
                        resource_filename = f"resource_{count}.dat"
                    
                    # 处理文件名冲突或非法字符
                    resource_filename = "".join(c for c in resource_filename if c.isalnum() or c in "._-")
                    if not resource_filename:
                         resource_filename = f"res_{count}"
                    
                    # 确保文件名唯一
                    save_name = resource_filename
                    counter = 1
                    while os.path.exists(os.path.join(resources_dir_path, save_name)):
                        name, ext = os.path.splitext(resource_filename)
                        save_name = f"{name}_{counter}{ext}"
                        counter += 1
                        
                    local_resource_path = os.path.join(resources_dir_path, save_name)
                    
                    try:
                        headers = {"User-Agent": user_agent}
                        
                        # 配置代理
                        proxies = None
                        if requests_proxy:
                            proxies = {
                                "http": requests_proxy,
                                "https": requests_proxy
                            }
                        
                        response = requests.get(abs_url, headers=headers, cookies=cookies, proxies=proxies, timeout=10, verify=False)
                        if response.status_code == 200:
                            with open(local_resource_path, "wb") as f:
                                f.write(response.content)
                            
                            # 修改 HTML 中的链接为相对路径
                            tag[attr_name] = f"{resources_dir_name}/{save_name}"
                            count += 1
                            self.log(f"已下载: {resource_filename}")
                    except Exception as e:
                        print(f"资源下载失败 {abs_url}: {e}")
                        # 下载失败则保留原链接
                        pass

            # 6. 保存修改后的 HTML
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(soup))
                
            self.log(f"保存完成！HTML 已保存至: {file_path}")
            self.log(f"资源文件已保存至: {resources_dir_path}")
            self.log(f"共下载资源: {count} 个")
            
        except Exception as e:
            self.log(f"保存过程中出错: {str(e)}")

    def load_html_for_editing(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.current_html_path = file_path
            self.current_soup = BeautifulSoup(content, "html.parser")
            self.tree_items_map.clear()
            
            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            # Find images
            for i, img in enumerate(self.current_soup.find_all("img")):
                src = img.get("src")
                if src:
                    item_id = self.tree.insert("", "end", values=("Image", src, src))
                    self.tree_items_map[item_id] = (img, "src")
                    
            # Find links
            for i, a in enumerate(self.current_soup.find_all("a")):
                href = a.get("href")
                if href:
                    item_id = self.tree.insert("", "end", values=("Link", href, href))
                    self.tree_items_map[item_id] = (a, "href")
                    
            messagebox.showinfo("成功", "HTML 文件加载成功，双击列表项可修改。")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        column = self.tree.identify_column(event.x)
        if column == "#3": # "New Value" column
            self.edit_tree_item(item_id)

    def edit_tree_item(self, item_id):
        # Get current values
        values = self.tree.item(item_id, "values")
        current_val = values[2]
        
        # Create a popup window for editing
        edit_window = tk.Toplevel(self.root)
        edit_window.title("修改值")
        edit_window.geometry("400x100")
        
        ttk.Label(edit_window, text="请输入新值:").pack(pady=5)
        entry = ttk.Entry(edit_window, width=50)
        entry.insert(0, current_val)
        entry.pack(pady=5, padx=10)
        entry.focus()
        
        def save_edit():
            new_val = entry.get()
            self.tree.item(item_id, values=(values[0], values[1], new_val))
            edit_window.destroy()
            
        ttk.Button(edit_window, text="确定", command=save_edit).pack(pady=5)
        edit_window.bind("<Return>", lambda e: save_edit())

    def save_edited_html(self):
        if not self.current_soup or not self.current_html_path:
            messagebox.showwarning("警告", "请先加载 HTML 文件。")
            return
            
        try:
            # Update soup from treeview
            for item_id in self.tree.get_children():
                tag_obj, attr_name = self.tree_items_map.get(item_id)
                if tag_obj:
                    new_val = self.tree.item(item_id, "values")[2]
                    tag_obj[attr_name] = new_val
            
            # Save to file
            with open(self.current_html_path, "w", encoding="utf-8") as f:
                f.write(str(self.current_soup))
                
            messagebox.showinfo("成功", f"修改已保存至: {self.current_html_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def close_browser(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            self.playwright = None
            self.browser = None
            self.page = None
            self.context = None
            
            self.log("浏览器已关闭。")
            self.update_buttons(running=False)
        except Exception as e:
            self.log(f"关闭时出错: {str(e)}")

    def update_buttons(self, running):
        if running:
            self.btn_launch.config(state="disabled")
            self.btn_navigate.config(state="normal")
            self.btn_save.config(state="normal")
            self.btn_close.config(state="normal")
            self.ua_combobox.config(state="disabled")
        else:
            self.btn_launch.config(state="normal")
            self.btn_navigate.config(state="disabled")
            self.btn_save.config(state="disabled")
            self.btn_close.config(state="disabled")
            self.ua_combobox.config(state="normal")

    def on_closing(self):
        if self.browser:
            self.close_browser()
        self.root.destroy()

if __name__ == "__main__":
    # 处理安装浏览器的特殊参数
    if "--install-browsers" in sys.argv:
        try:
            from playwright.__main__ import main
            sys.argv = ["playwright", "install", "chromium"]
            sys.exit(main())
        except ImportError:
            print("Error: Cannot import playwright.__main__")
            sys.exit(1)
        except SystemExit as e:
            sys.exit(e.code)

    root = tk.Tk()
    app = BrowserCrawlerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
