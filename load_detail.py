import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from PIL import Image, ImageTk
import json
import os
import glob
import logging
import sys
import traceback
import jmcomic
import threading

from time import time as get_time
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_detail(client, id, album_id, path):
    """下载漫画详情和封面"""
    try:
        # 创建目录
        os.makedirs(f"{path}{id}", exist_ok=True)
        
        # 下载详情
        download_detail_album(client, id, album_id, path)
        
        # 下载封面
        download_detail_cover(client, id, album_id, path)
        
        return True, ""
    except Exception as e:
        return False, str(e)

def download_detail_album(client, id, album_id, path):
    """下载漫画详情数据"""
    album: jmcomic.JmAlbumDetail = client.get_album_detail(album_id)
    album_json = {
        'id': album.album_id,
        'title': album.title,
        'author': album.author,
        'description': album.description,
        'tags': album.tags,
        'comment_count': album.comment_count,
        'likes': album.likes,
        'works': album.works,
        'related_list': album.related_list,
    }
    with open(f'{path}{id}\\album.json', 'w', encoding='utf-8') as f:
        json.dump(album_json, f, ensure_ascii=False, indent=4)

def download_detail_cover(client, id, album_id, path):
    """下载漫画封面"""
    photo: jmcomic.JmPhotoDetail = client.get_photo_detail(album_id)
    first_image: jmcomic.JmImageDetail = photo[0]
    client.download_by_image_detail(first_image, f'{path}{id}\\cover.png')

# 配置日志系统
def setup_logger():
    # 创建日志目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 配置日志
    logger = logging.getLogger("ComicBrowser")
    logger.setLevel(logging.DEBUG)
    
    # 文件日志处理器
    file_handler = logging.FileHandler(os.path.join(log_dir, "comic_browser.log"), encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 创建日志记录器
logger = setup_logger()

class ComicBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("JMComic 漫画详情浏览器")
        self.root.geometry("1200x800")
        self.root.configure(bg="#ffffff")
        self.start_time=int(get_time())
        self.json_path=str(self.start_time)+'.json'
        # 设置应用图标
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "comic_icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                logger.warning("应用图标文件未找到: comic_icon.ico")
        except Exception as e:
            logger.error(f"加载应用图标失败: {str(e)}")
        
        # 设置样式
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#ffffff")
        self.style.configure("TLabel", background="#ffffff", font=("Microsoft YaHei", 10))
        self.style.configure("Title.TLabel", background="#ffffff", font=("Microsoft YaHei", 14, "bold"))
        self.style.configure("Header.TLabel", background="#f0f0f0", font=("Microsoft YaHei", 11, "bold"))
        self.style.configure("TButton", font=("Microsoft YaHei", 10))
        self.style.configure("Treeview", font=("Microsoft YaHei", 10), rowheight=30)
        self.style.configure("Treeview.Heading", font=("Microsoft YaHei", 10, "bold"))
        self.style.map("Treeview", 
               background=[("selected", "#e6f7ff")],
               foreground=[("selected", "black")])
        
        # 创建主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建左侧列表和右侧详情区域
        self.create_list_panel()
        self.create_detail_panel()
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var.set("就绪")
        
        # 加载漫画数据
        self.comics = []
        self.current_comic = None
        self.load_comics()
        
        # 设置初始状态 - 修复选择逻辑
        if self.comic_list.get_children():
            self.comic_list.selection_set(self.comic_list.get_children()[0])
            self.show_comic_details(0)
    
    def log_action(self, action, success=True, message=""):
        """记录操作日志"""
        status = "成功" if success else "失败"
        log_message = f"{action} {status}"
        if message:
            log_message += f" - {message}"
        logger.info(log_message)
        self.status_var.set(log_message)
        
    def create_list_panel(self):
        """创建左侧漫画列表面板"""
        try:
            # 左侧面板 - 漫画列表
            list_frame = ttk.Frame(self.main_frame, width=300)
            list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            
            # 标题和搜索框
            list_header = ttk.Frame(list_frame)
            list_header.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(list_header, text="漫画列表", style="Title.TLabel").pack(side=tk.LEFT, anchor=tk.W)
            
            # 搜索框
            search_frame = ttk.Frame(list_header)
            search_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            
            self.search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=15)
            search_entry.pack(side=tk.LEFT, padx=(10, 0))
            search_entry.bind("<KeyRelease>", self.filter_comics)
            
            search_btn = ttk.Button(search_frame, text="搜索", width=6, command=self.filter_comics)
            search_btn.pack(side=tk.LEFT, padx=(5, 0))
            
            # 漫画列表
            list_container = ttk.Frame(list_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            
            # 创建滚动条
            scrollbar = ttk.Scrollbar(list_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 创建列表树
            columns = ("id", "title")
            self.comic_list = ttk.Treeview(
                list_container, 
                columns=columns, 
                show="headings", 
                selectmode="browse",
                yscrollcommand=scrollbar.set
            )
            
            self.comic_list.heading("id", text="ID")
            self.comic_list.heading("title", text="标题")
            self.comic_list.column("id", width=60, anchor=tk.CENTER)
            self.comic_list.column("title", width=220, anchor=tk.W)
            
            self.comic_list.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.comic_list.yview)
            
            # 绑定选择事件
            self.comic_list.bind("<<TreeviewSelect>>", self.on_comic_select)
            
            logger.debug("左侧漫画列表面板创建完成")
        except Exception as e:
            logger.error(f"创建左侧面板失败: {str(e)}")
            traceback.print_exc()
    
    def create_detail_panel(self):
        """创建右侧详情面板"""
        try:
            # 右侧面板 - 漫画详情
            detail_frame = ttk.Frame(self.main_frame)
            detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 详情头部（标题和操作按钮）
            detail_header = ttk.Frame(detail_frame)
            detail_header.pack(fill=tk.X, pady=(0, 15))
            
            self.title_label = ttk.Label(detail_header, text="", style="Title.TLabel")
            self.title_label.pack(side=tk.LEFT, anchor=tk.W)
            
            button_frame = ttk.Frame(detail_frame)
            button_frame.pack(fill=tk.X, pady=(0, 15))
        
            ttk.Button(button_frame, text="刷新数据", command=self.reload_comics).pack(side=tk.LEFT, padx=(5, 0))
            ttk.Button(button_frame, text="删除详情", command=self.delete_comic).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="打开目录", command=self.open_directory).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="下载漫画", command=self.download_comic).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="添加下载列表", command=self.add_to_list).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="切换下载列表", command=self.change_json).pack(side=tk.LEFT, padx=(0, 5))

            # 详情内容区域
            detail_content = ttk.Frame(detail_frame)
            detail_content.pack(fill=tk.BOTH, expand=True)
            
            # 封面图片区域
            cover_frame = ttk.Frame(detail_content)
            cover_frame.pack(fill=tk.X, pady=(0, 15))
            
            self.cover_label = ttk.Label(cover_frame, text="封面加载中...")
            self.cover_label.pack()
            
            # 元数据区域
            meta_frame = ttk.Frame(detail_content)
            meta_frame.pack(fill=tk.X, pady=(0, 15))
            
            # 作者信息
            author_frame = ttk.Frame(meta_frame)
            author_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(author_frame, text="作者:", width=8, anchor=tk.E).pack(side=tk.LEFT)
            self.author_label = ttk.Label(author_frame, text="")
            self.author_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # 标签信息
            tags_frame = ttk.Frame(meta_frame)
            tags_frame.pack(fill=tk.X, pady=5)
            ttk.Label(tags_frame, text="标签:", width=8, anchor=tk.E).pack(side=tk.LEFT)
            self.tags_label = ttk.Label(tags_frame, text="")
            self.tags_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # 点赞和评论
            stats_frame = ttk.Frame(meta_frame)
            stats_frame.pack(fill=tk.X, pady=5)
            ttk.Label(stats_frame, text="点赞:", width=8, anchor=tk.E).pack(side=tk.LEFT)
            self.likes_label = ttk.Label(stats_frame, text="")
            self.likes_label.pack(side=tk.LEFT, padx=(5, 0))
            
            ttk.Label(stats_frame, text="评论:", width=8, anchor=tk.E).pack(side=tk.LEFT, padx=(20, 0))
            self.comments_label = ttk.Label(stats_frame, text="")
            self.comments_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # 作品信息 - 恢复竖直排列方式
            works_frame = ttk.Frame(detail_content)
            works_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            
            # 添加标题
            works_header = ttk.Frame(works_frame)
            works_header.pack(fill=tk.X)
            ttk.Label(works_header, text="相关作品", style="Header.TLabel").pack(anchor=tk.W)
            
            # 修正按钮绑定
            self.download_selected_btn = ttk.Button(works_header, text="下载选中详情", command=self.download_selected_comic_detail)
            self.download_selected_btn.pack(side=tk.RIGHT, padx=(0, 5))
            
            self.download_all_btn = ttk.Button(works_header, text="下载所有详情", command=self.download_all_related_comics)
            self.download_all_btn.pack(side=tk.RIGHT, padx=5)
            
            # 创建滚动区域
            works_container = ttk.Frame(works_frame)
            works_container.pack(fill=tk.BOTH, expand=True)
            
            # 滚动条
            scrollbar = ttk.Scrollbar(works_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 创建作品列表树
            self.works_tree = ttk.Treeview(
                works_container,
                columns=("id", "title", "author"),
                show="headings",
                yscrollcommand=scrollbar.set,
                height=6
            )
            scrollbar.config(command=self.works_tree.yview)
            
            # 设置列
            self.works_tree.heading("id", text="作品ID")
            self.works_tree.heading("title", text="作品标题")
            self.works_tree.heading("author", text="作者")
            self.works_tree.column("id", width=80, anchor=tk.CENTER)
            self.works_tree.column("title", width=350, anchor=tk.W)
            self.works_tree.column("author", width=120, anchor=tk.W)
            
            self.works_tree.pack(fill=tk.BOTH, expand=True)
            
            logger.debug("右侧详情面板创建完成")
        except Exception as e:
            logger.error(f"创建右侧面板失败: {str(e)}")
            traceback.print_exc()
    
    def load_comics(self):
        """加载details文件夹下的所有漫画数据"""
        try:
            self.comics = []
            self.comic_list.delete(*self.comic_list.get_children())
            
            # 检查details文件夹是否存在
            details_dir = "details"
            if not os.path.exists(details_dir):
                logger.warning(f"漫画详情文件夹不存在: {details_dir}")
                self.comic_list.insert("", tk.END, values=("", "详情文件夹不存在"))
                self.status_var.set(f"错误: 详情文件夹不存在 - {details_dir}")
                return
            
            # 获取所有子文件夹
            comic_dirs = glob.glob(os.path.join(details_dir, "*"))
            logger.info(f"在 {details_dir} 中找到 {len(comic_dirs)} 个文件夹")
            
            if not comic_dirs:
                self.comic_list.insert("", tk.END, values=("", "未找到漫画数据"))
                self.status_var.set("未找到漫画数据")
                return
            
            loaded_count = 0
            for dir_path in comic_dirs:
                if os.path.isdir(dir_path):
                    comic_id = os.path.basename(dir_path)
                    json_path = os.path.join(dir_path, "album.json")
                    
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                comic_data = json.load(f)
                            
                            # 添加到漫画列表
                            self.comics.append({
                                "id": comic_id,
                                "dir": dir_path,
                                "data": comic_data
                            })
                            
                            # 添加到列表视图
                            self.comic_list.insert("", tk.END, values=(comic_id, comic_data.get("title", "无标题")))
                            loaded_count += 1
                        
                        except Exception as e:
                            logger.error(f"加载漫画数据出错: {json_path}, {str(e)}")
                    else:
                        logger.warning(f"在文件夹中未找到album.json: {dir_path}")
            
            # 更新状态
            self.status_var.set(f"已加载 {loaded_count}/{len(comic_dirs)} 个漫画")
            logger.info(f"成功加载 {loaded_count} 个漫画")
            
            # 如果没有漫画，显示提示信息
            if not self.comics:
                self.comic_list.insert("", tk.END, values=("", "请先下载漫画详情"))
                self.status_var.set("未找到有效漫画数据")
        
        except Exception as e:
            logger.error(f"加载漫画数据失败: {str(e)}")
            traceback.print_exc()
            self.status_var.set(f"错误: {str(e)}")
    
    def filter_comics(self, event=None):
        """根据搜索框内容过滤漫画列表"""
        try:
            search_term = self.search_var.get().lower()
            
            # 清空当前列表
            self.comic_list.delete(*self.comic_list.get_children())
            
            # 如果没有漫画数据
            if not self.comics:
                self.comic_list.insert("", tk.END, values=("", "无漫画数据"))
                return
            
            # 重新添加匹配的漫画
            matched = 0
            for comic in self.comics:
                title = comic["data"].get("title", "").lower()
                if search_term in comic["id"].lower() or search_term in title:
                    self.comic_list.insert("", tk.END, values=(comic["id"], title))
                    matched += 1
            
            # 更新状态
            self.status_var.set(f"找到 {matched}/{len(self.comics)} 个匹配的漫画")
            logger.info(f"搜索 '{search_term}' - 找到 {matched} 个结果")
            
            # 如果没有匹配项
            if matched == 0:
                self.comic_list.insert("", tk.END, values=("", "未找到匹配的漫画"))
            
            # 自动选择第一个匹配项
            if matched > 0:
                self.comic_list.selection_set(self.comic_list.get_children()[0])
                self.show_comic_details(0)
        
        except Exception as e:
            logger.error(f"过滤漫画列表失败: {str(e)}")
            self.status_var.set(f"错误: {str(e)}")
    
    def on_comic_select(self, event):
        """当用户选择一个漫画时显示详情"""
        try:
            selection = self.comic_list.selection()
            if selection:
                # 获取选中项的索引
                selected_index = self.comic_list.index(selection[0])
                self.show_comic_details(selected_index)
        except Exception as e:
            logger.error(f"选择漫画失败: {str(e)}")
            self.status_var.set(f"错误: {str(e)}")
    
    def show_comic_details(self, index):
        """显示指定索引的漫画详情"""
        try:
            if index < 0 or index >= len(self.comics):
                logger.warning(f"无效的漫画索引: {index}")
                self.status_var.set("错误: 无效的漫画索引")
                return
                
            comic = self.comics[index]
            self.current_comic = comic
            data = comic["data"]
            
            # 更新标题
            title = data.get("title", "无标题")
            self.title_label.config(text=title)
            
            # 更新作者信息
            author = data.get("author", "未知")
            self.author_label.config(text=author)
            
            # 更新标签信息
            tags = data.get("tags", [])
            self.tags_label.config(text=", ".join(tags) if tags else "无标签")
            
            # 更新统计信息
            likes = data.get("likes", 0)
            comments = data.get("comment_count", 0)
            self.likes_label.config(text=str(likes))
            self.comments_label.config(text=str(comments))
            
            # 加载封面图片
            cover_path = os.path.join(comic["dir"], "cover.png")
            self.load_cover_image(cover_path)
            
            # 更新作品列表 - 使用Treeview显示
            self.works_tree.delete(*self.works_tree.get_children())
            works = data.get("related_list", [])
            
            if works:
                for work in works:
                    # 提取作品信息
                    work_id = work.get("id", "")
                    work_title = work.get("name", "未知标题")
                    work_author = work.get("author", "未知作者")
                    
                    # 添加到作品列表
                    self.works_tree.insert("", tk.END, values=(work_id, work_title, work_author))
            else:
                # 如果没有作品信息
                self.works_tree.insert("", tk.END, values=("", "无相关作品", ""))
            
            # 更新状态
            self.status_var.set(f"正在显示: {title}")
            logger.info(f"显示漫画详情: {title} (ID: {comic['id']})")
        
        except Exception as e:
            logger.error(f"显示漫画详情失败: {str(e)}")
            self.status_var.set(f"错误: 显示详情失败")
    
    def load_cover_image(self, path):
        """加载并显示封面图片"""
        try:
            if os.path.exists(path):
                # 使用PIL打开图片并调整大小
                img = Image.open(path)
                # 计算保持宽高比的缩放比例
                max_width, max_height = 200, 300
                width, height = img.size
                
                # 计算新尺寸
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                img = img.resize((new_width, new_height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                # 更新标签图片
                self.cover_label.config(image=photo)
                self.cover_label.image = photo
                logger.debug(f"封面图片加载成功: {path}")
            else:
                self.cover_label.config(image="", text="封面不存在")
                logger.warning(f"封面图片不存在: {path}")
        except Exception as e:
            self.cover_label.config(image="", text="封面加载失败")
            logger.error(f"加载封面图片出错: {path}, {str(e)}")
    
    def reload_comics(self):
        """重新加载漫画数据"""
        try:
            self.load_comics()
            
            # 尝试重新选择当前漫画
            if self.current_comic and self.comics:
                for i, comic in enumerate(self.comics):
                    if comic["id"] == self.current_comic["id"]:
                        children = self.comic_list.get_children()
                        if i < len(children):
                            self.comic_list.selection_set(children[i])
                            self.show_comic_details(i)
                        break
            
            self.log_action("刷新漫画数据", True, f"已加载 {len(self.comics)} 个漫画")
        except Exception as e:
            self.log_action("刷新漫画数据", False, str(e))
            logger.error(f"刷新漫画数据失败: {str(e)}")
    
    def download_selected_comic_detail(self):
        """下载选中的相关作品详情（非阻塞）"""
        selection = self.works_tree.selection()
        if not selection:
            messagebox.showwarning("下载失败", "请先选择一个相关作品")
            self.log_action("下载选中详情", False, "未选择作品")
            return
        
        # 获取选中项的数据
        selected_item = self.works_tree.item(selection[0])
        values = selected_item['values']
        
        if not values or values[0] == "":
            messagebox.showwarning("下载失败", "请选择一个有效作品")
            self.log_action("下载选中详情", False, "选择的作品无效")
            return
            
        comic_id = str(values[0])
        comic_title = str(values[1])
        
        # 禁用按钮防止重复点击
        self.download_selected_btn.config(state=tk.DISABLED)
        self.download_all_btn.config(state=tk.DISABLED)
        self.status_var.set(f"开始下载: {comic_title} (ID: {comic_id})")
        
        # 创建新线程执行下载任务
        threading.Thread(
            target=self._download_comic_detail, 
            args=(comic_id, comic_title),
            daemon=True
        ).start()
    
    def _download_comic_detail(self, comic_id, comic_title):
        """后台线程执行下载任务"""
        try:
            option = jmcomic.JmOption.default()
            client = option.new_jm_client()
            details_path = "details\\"
            
            # 调用下载函数
            success, error = download_detail(client, comic_id, comic_id, details_path)
            
            if success:
                self.root.after(0, lambda: self.status_var.set(f"下载成功: {comic_title}"))
                self.root.after(0, self.reload_comics)  # 重新加载列表
            else:
                self.root.after(0, lambda: self.status_var.set(f"下载失败: {comic_title} - {error}"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"下载异常: {str(e)}"))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: [
                self.download_selected_btn.config(state=tk.NORMAL),
                self.download_all_btn.config(state=tk.NORMAL)
            ])
    
    def download_all_related_comics(self):
        """下载所有相关作品详情（15线程并发）"""
        if not self.current_comic:
            messagebox.showwarning("下载失败", "请先选择一个漫画以获取相关作品列表")
            return
        
        # 获取当前漫画的所有相关作品
        related_list = self.current_comic["data"].get("related_list", [])
        if not related_list:
            messagebox.showinfo("下载", "当前漫画没有相关作品")
            return
        
        # 准备下载任务
        tasks = []
        for work in related_list:
            work_id = work.get("id", "")
            if work_id:  # 确保有有效的ID
                tasks.append({
                    "id": str(work_id),
                    "title": work.get("name", "未知标题")
                })
        
        if not tasks:
            messagebox.showinfo("下载", "没有找到有效的相关作品ID")
            return
        
        # 确认下载
        confirm = messagebox.askyesno(
            "确认下载", 
            f"确定要下载所有相关作品详情吗？\n\n共 {len(tasks)} 个作品"
        )
        if not confirm:
            return
        
        # 禁用按钮防止重复点击
        self.download_selected_btn.config(state=tk.DISABLED)
        self.download_all_btn.config(state=tk.DISABLED)
        self.status_var.set(f"开始批量下载: {len(tasks)} 个作品...")
        
        # 创建新线程执行批量下载
        threading.Thread(
            target=self._download_all_comics, 
            args=(tasks,),
            daemon=True
        ).start()
    
    def _download_all_comics(self, tasks):
        """后台线程执行批量下载任务（15线程并发）"""
        try:
            # 创建线程池（最大15个线程）
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {}
                
                # 提交所有任务到线程池
                for task in tasks:
                    future = executor.submit(
                        self._download_single_comic, 
                        task["id"], 
                        task["title"]
                    )
                    futures[future] = task
                
                # 跟踪进度
                completed = 0
                total = len(tasks)
                failed = []
                
                # 等待任务完成并更新状态
                for future in as_completed(futures):
                    task = futures[future]
                    comic_id, comic_title = task["id"], task["title"]
                    
                    try:
                        success, error = future.result()
                        if success:
                            self.root.after(0, lambda cid=comic_id, ct=comic_title: 
                                self.status_var.set(f"完成: {ct} (ID: {cid})"))
                        else:
                            failed.append((comic_id, comic_title, error))
                            self.root.after(0, lambda cid=comic_id, ct=comic_title, e=error: 
                                self.status_var.set(f"失败: {ct} - {e}"))
                    except Exception as e:
                        failed.append((comic_id, comic_title, str(e)))
                        self.root.after(0, lambda cid=comic_id, ct=comic_title, e=str(e): 
                            self.status_var.set(f"异常: {ct} - {e}"))
                    
                    completed += 1
                    self.root.after(0, lambda c=completed, t=total: 
                        self.status_var.set(f"批量下载中: {c}/{t} 已完成"))
            
            # 全部完成
            self.root.after(0, lambda: [
                self.status_var.set(f"批量下载完成! 成功: {total - len(failed)}, 失败: {len(failed)}"),
                self.reload_comics()
            ])
            
            # 如果有失败的任务，显示错误报告
            if failed:
                error_report = "\n".join([f"ID: {f[0]}, 标题: {f[1]}, 错误: {f[2]}" for f in failed])
                self.root.after(0, lambda: messagebox.showwarning(
                    "部分下载失败", 
                    f"以下 {len(failed)} 个作品下载失败:\n\n{error_report}"
                ))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"批量下载异常: {str(e)}"))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: [
                self.download_selected_btn.config(state=tk.NORMAL),
                self.download_all_btn.config(state=tk.NORMAL)
            ])
    
    def _download_single_comic(self, comic_id, comic_title):
        """下载单个漫画详情（供线程池使用）"""
        try:
            option = jmcomic.JmOption.default()
            client = option.new_jm_client()
            details_path = "details\\"
            os.makedirs(details_path, exist_ok=True)
            
            # 调用下载函数
            return download_detail(client, comic_id, comic_id, details_path)
        except Exception as e:
            return False, str(e)
    
    def delete_comic(self):
        """删除当前选中的漫画详情"""
        try:
            if not self.current_comic:
                messagebox.showwarning("删除失败", "请先选择一个漫画")
                self.log_action("删除详情", False, "未选择漫画")
                return
                
            comic_id = self.current_comic["id"]
            comic_title = self.current_comic["data"].get("title", "无标题")
            comic_dir = self.current_comic["dir"]
            
            # 确认删除
            #confirm = messagebox.askyesno(
            #    "确认删除", 
            #    f"确定要删除漫画详情吗？\n\nID: {comic_id}\n标题: {comic_title}\n\n此操作将删除整个目录及其中所有文件，无法恢复！"
            #)
            
            #if not confirm:
            if False:
                self.log_action("删除详情", False, "用户取消操作")
                return
                
            # 删除目录及其中所有文件
            if os.path.exists(comic_dir):
                import shutil
                try:
                    shutil.rmtree(comic_dir)
                    self.log_action("删除详情", True, f"已删除 {comic_dir}")
                    #messagebox.showinfo("删除成功", f"已成功删除漫画详情:\n{comic_title}")
                    
                    # 重新加载漫画列表
                    current_selection = self.comic_list.selection()
                    current_index = self.comic_list.index(current_selection[0]) if current_selection else 0
                    
                    self.load_comics()
                    
                    # 尝试保持相近位置的选择
                    children = self.comic_list.get_children()
                    if children:
                        # 如果原来有选择项且不是最后一项，则选择相同索引项
                        if current_selection and current_index < len(children):
                            self.comic_list.selection_set(children[current_index])
                            self.show_comic_details(current_index)
                        else:
                            # 否则选择第一项
                            self.comic_list.selection_set(children[0])
                            self.show_comic_details(0)
                            
                except Exception as e:
                    self.log_action("删除详情", False, str(e))
                    messagebox.showerror("删除失败", f"删除过程中出错:\n{str(e)}")
                    logger.error(f"删除目录失败: {str(e)}")
            else:
                self.log_action("删除详情", False, "目录不存在")
                messagebox.showerror("删除失败", "目录不存在")
                
        except Exception as e:
            self.log_action("删除详情", False, str(e))
            logger.error(f"删除详情失败: {str(e)}")
    
    def export_json(self):
        """导出当前漫画的JSON数据"""
        try:
            if not self.current_comic:
                messagebox.showwarning("导出失败", "请先选择一个漫画")
                self.log_action("导出JSON", False, "未选择漫画")
                return
                
            default_filename = f"{self.current_comic['id']}_album.json"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
                initialfile=default_filename
            )
            
            if file_path:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(self.current_comic["data"], f, ensure_ascii=False, indent=4)
                    
                    self.log_action("导出JSON", True, f"导出到 {file_path}")
                    messagebox.showinfo("导出成功", f"JSON数据已导出到:\n{file_path}")
                except Exception as e:
                    self.log_action("导出JSON", False, str(e))
                    messagebox.showerror("导出失败", f"导出过程中出错:\n{str(e)}")
                    logger.error(f"导出JSON失败: {str(e)}")
        except Exception as e:
            self.log_action("导出JSON", False, str(e))
            logger.error(f"导出JSON失败: {str(e)}")
    
    def open_directory(self):
        """打开当前漫画的目录"""
        try:
            if not self.current_comic:
                messagebox.showwarning("打开失败", "请先选择一个漫画")
                self.log_action("打开目录", False, "未选择漫画")
                return
                
            dir_path = self.current_comic["dir"]
            if os.path.exists(dir_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(dir_path)
                    elif sys.platform == "darwin":
                        os.system(f"open '{dir_path}'")
                    else:
                        os.system(f"xdg-open '{dir_path}'")
                    
                    self.log_action("打开目录", True, dir_path)
                except:
                    messagebox.showinfo("打开目录", f"目录路径:\n{dir_path}")
            else:
                self.log_action("打开目录", False, "目录不存在")
                messagebox.showerror("打开失败", "目录不存在")
        except Exception as e:
            self.log_action("打开目录", False, str(e))
            logger.error(f"打开目录失败: {str(e)}")
    def download_comic(self):
        """下载当前选中的漫画"""
        try:
            # 检查是否选择了漫画
            if not self.current_comic:
                messagebox.showwarning("下载失败", "请先选择一个漫画")
                self.log_action("下载漫画", False, "未选择漫画")
                return
                
            # 检查是否存在setting.yml配置文件
            if not os.path.exists('setting.yml'):
                # 如果不存在，则创建默认配置文件
                jmcomic.JmOption.default().to_file('setting.yml')
                
            # 从配置文件创建选项对象
            option = jmcomic.create_option_by_file('setting.yml')
            
            # 获取当前选中漫画的ID
            comic_id = self.current_comic["id"]
            comic_title = self.current_comic["data"].get("title", "未知标题")
            
            # 确认下载
            confirm = messagebox.askyesno(
                "确认下载", 
                f"确定要下载这部漫画吗？\n\nID: {comic_id}\n标题: {comic_title}"
            )
            
            if not confirm:
                self.log_action("下载漫画", False, "用户取消操作")
                return
                
            # 禁用下载按钮防止重复点击
            # 注意：这里需要找到下载按钮并禁用，根据UI代码，应该是找到"下载漫画"按钮
            self.status_var.set(f"开始下载: {comic_title} (ID: {comic_id})")
            
            # 创建新线程执行下载任务
            threading.Thread(
                target=self._download_comic_thread, 
                args=(comic_id, comic_title, option),
                daemon=True
            ).start()
            
        except Exception as e:
            self.log_action("下载漫画", False, str(e))
            logger.error(f"下载漫画失败: {str(e)}")
            messagebox.showerror("下载失败", f"下载过程中出错:\n{str(e)}")

    def _download_comic_thread(self, comic_id, comic_title, option):
        """后台线程执行漫画下载任务"""
        try:
            # 使用jmcomic下载漫画
            #client = option.new_jm_client()
            #album_detail = client.get_album_detail(comic_id)
            
            # 执行下载
            jmcomic.download_album(comic_id, option)
            
            # 在主线程中更新UI
            self.root.after(0, lambda: [
                self.status_var.set(f"下载完成: {comic_title}"),
                messagebox.showinfo("下载完成", f"漫画下载完成:\n{comic_title}")
            ])
            
            self.log_action("下载漫画", True, f"已下载 {comic_title} (ID: {comic_id})")
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: [
                self.status_var.set(f"下载失败: {comic_title}"),
                messagebox.showerror("下载失败", f"下载过程中出错:\n{error_msg}")
            ])
            self.log_action("下载漫画", False, error_msg)
            logger.error(f"下载漫画失败: {error_msg}")
    def add_to_list(self):
        """下载当前选中的漫画"""
        try:
            # 检查是否选择了漫画
            if not self.current_comic:
                messagebox.showwarning("添加失败", "请先选择一个漫画")
                self.log_action("添加漫画", False, "未选择漫画")
                return

            
            # 获取当前选中漫画的ID
            comic_id = self.current_comic["id"]
            comic_title = self.current_comic["data"].get("title", "未知标题")
            comic_tag = self.current_comic["data"].get("tags", "")
            if os.path.exists(self.json_path):
                logging.info(f"获取列表{self.json_path}")
                with open(self.json_path,'r',encoding='utf-8')as f:
                    json_data = json.load(f)
                    already_downloaded=False
                    for i in json_data:
                        if i["id"] == comic_id:
                            already_downloaded = True
                            break
                    if not already_downloaded:
                        json_data.append({"id": comic_id, "title": comic_title,'tags':comic_tag})
            else:
                logging.info(f"创建列表{self.json_path}")
                json_data = [{"id": comic_id, "title": comic_title,'tags':comic_tag}]
            json.dump(json_data, open(self.json_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
        except Exception as e:
            self.log_action("下载漫画", False, str(e))
            logger.error(f"下载漫画失败: {str(e)}")
            messagebox.showerror("下载失败", f"下载过程中出错:\n{str(e)}")
    def change_json(self):
        json_path=self.select_json_file()
        try:
            if os.path.exists(json_path):
                self.json_path = json_path
                logging.info(f"已选择JSON文件: {json_path}")
            else:
                logging.error(f"JSON文件不存在: {json_path}")
        except:
            logging.error("选择JSON文件时出错")
    def select_json_file(self):
        """
        弹出文件选择窗口，选择JSON文件并返回文件路径
        """
        try:
            logging.info("选择JSON文件")
            # 弹出文件选择对话框，只允许选择JSON文件
            file_path = filedialog.askopenfilename(
                title="选择JSON文件",
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
            )
            
            # 如果用户选择了文件
            if file_path:
                self.status_var.set(f"已选择文件: {file_path}")
                logger.info(f"用户选择了JSON文件: {file_path}")
                return file_path
            else:
                self.status_var.set("未选择文件")
                logger.info("用户取消了文件选择")
                return None
                
        except Exception as e:
            error_msg = f"选择文件时出错: {str(e)}"
            self.status_var.set(error_msg)
            logger.error(error_msg)
            messagebox.showerror("错误", f"选择文件时发生错误:\n{str(e)}")
            return None
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ComicBrowser(root)
        root.mainloop()
    except Exception as e:
        logger.critical(f"应用程序崩溃: {str(e)}")
        traceback.print_exc()
        messagebox.showerror("应用程序错误", f"程序遇到严重错误:\n{str(e)}\n\n请查看日志文件获取详细信息。")