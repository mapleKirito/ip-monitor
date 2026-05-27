import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import sys
import platform
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional


CONFIG_FILE = 'config.json'
REFRESH_INTERVAL = 5000


@dataclass
class IPStatus:
    ip: str
    reachable: bool = False
    latency: Optional[float] = None
    last_check: float = 0


class ConfigManager:
    def __init__(self):
        self.config_path = self._get_config_path()
        self.config = self._load_or_create_config()

    def _get_config_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
        return CONFIG_FILE

    def _load_or_create_config(self):
        if not os.path.exists(self.config_path):
            config = {"monitored_ips": []}
            self._save_config(config)
            return config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"monitored_ips": []}

    def _save_config(self, config):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_monitored_ips(self):
        return self.config.get('monitored_ips', [])

    def add_ip(self, ip):
        if ip not in self.config['monitored_ips']:
            self.config['monitored_ips'].append(ip)
            self._save_config(self.config)

    def remove_ip(self, ip):
        if ip in self.config['monitored_ips']:
            self.config['monitored_ips'].remove(ip)
            self._save_config(self.config)


class PingChecker:
    @staticmethod
    def ping(ip, timeout=1000):
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '-w', str(timeout), ip]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:
                latency = PingChecker._parse_latency(result.stdout)
                return True, latency
            return False, None
        except Exception:
            return False, None

    @staticmethod
    def _parse_latency(output):
        try:
            if platform.system().lower() == 'windows':
                for line in output.split('\n'):
                    if '平均' in line or 'Average' in line:
                        parts = line.split('=')[-1].strip().split('ms')[0].strip()
                        return float(parts)
            else:
                for line in output.split('\n'):
                    if 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        return float(time_part)
        except Exception:
            pass
        return None


class IPMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IP 连通性监测工具")
        self.root.geometry("600x450")
        self.root.resizable(True, True)

        self.config_manager = ConfigManager()
        self.ip_statuses = {}
        self.refresh_thread = None
        self.should_refresh = True

        self._setup_ui()
        self._load_ips()
        self._start_auto_refresh()

    def _setup_ui(self):
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = tk.Label(
            header_frame,
            text="IP 连通性监测",
            font=("Arial", 14, "bold")
        )
        title_label.pack(side=tk.LEFT)

        add_button = tk.Button(
            header_frame,
            text="+ 添加 IP",
            command=self._add_ip,
            padx=10
        )
        add_button.pack(side=tk.RIGHT)

        self.list_frame = tk.Frame(main_frame)
        self.list_frame.pack(fill=tk.BOTH, expand=True)

        column_widths = [12, 10, 12, 10]
        self.headers = ["IP 地址", "状态", "延迟 (ms)", "操作"]
        for i, header in enumerate(self.headers):
            label = tk.Label(
                self.list_frame,
                text=header,
                font=("Arial", 10, "bold"),
                width=column_widths[i],
                relief=tk.RIDGE,
                bg="#f0f0f0"
            )
            label.grid(row=0, column=i, sticky='ew', padx=1, pady=1)

        self.status_label = tk.Label(
            main_frame,
            text="",
            font=("Arial", 9),
            fg="gray"
        )
        self.status_label.pack(pady=(10, 0))

    def _load_ips(self):
        for ip in self.config_manager.get_monitored_ips():
            self.ip_statuses[ip] = IPStatus(ip=ip)
            self._add_ip_row(ip)

    def _add_ip_row(self, ip):
        row = len(self.ip_statuses)

        ip_label = tk.Label(
            self.list_frame,
            text=ip,
            width=12,
            relief=tk.RIDGE
        )
        ip_label.grid(row=row + 1, column=0, sticky='ew', padx=1, pady=1)

        status_label = tk.Label(
            self.list_frame,
            text="检测中...",
            width=10,
            relief=tk.RIDGE,
            fg="gray"
        )
        status_label.grid(row=row + 1, column=1, sticky='ew', padx=1, pady=1)

        latency_label = tk.Label(
            self.list_frame,
            text="-",
            width=12,
            relief=tk.RIDGE
        )
        latency_label.grid(row=row + 1, column=2, sticky='ew', padx=1, pady=1)

        remove_button = tk.Button(
            self.list_frame,
            text="移除",
            command=lambda ip=ip: self._remove_ip(ip),
            width=10
        )
        remove_button.grid(row=row + 1, column=3, sticky='ew', padx=1, pady=1)

        self.ip_statuses[ip].widgets = {
            'status': status_label,
            'latency': latency_label
        }

    def _add_ip(self):
        ip = simpledialog.askstring(
            "添加 IP",
            "请输入要监测的 IP 地址：",
            parent=self.root
        )

        if ip:
            ip = ip.strip()
            if not ip:
                messagebox.showwarning("警告", "IP 地址不能为空！")
                return

            if ip in self.ip_statuses:
                messagebox.showwarning("警告", f"IP {ip} 已经在监测列表中！")
                return

            if not self._validate_ip(ip):
                messagebox.showwarning("警告", "请输入有效的 IP 地址！")
                return

            self.config_manager.add_ip(ip)
            self.ip_statuses[ip] = IPStatus(ip=ip)
            self._add_ip_row(ip)
            self._check_single_ip(ip)
            self._update_status()

    def _remove_ip(self, ip):
        if messagebox.askyesno("确认", f"确定要移除 {ip} 吗？"):
            self.config_manager.remove_ip(ip)
            self._clear_ip_row(ip)
            del self.ip_statuses[ip]
            self._rebuild_list()
            self._update_status()

    def _clear_ip_row(self, ip):
        if ip in self.ip_statuses and hasattr(self.ip_statuses[ip], 'widgets'):
            for widget in self.ip_statuses[ip].widgets.values():
                widget.destroy()

    def _rebuild_list(self):
        for widget in self.list_frame.grid_slaves():
            if int(widget.grid_info()['row']) > 0:
                widget.destroy()

        column_widths = [12, 10, 12, 10]
        for i, header in enumerate(self.headers):
            label = tk.Label(
                self.list_frame,
                text=header,
                font=("Arial", 10, "bold"),
                width=column_widths[i],
                relief=tk.RIDGE,
                bg="#f0f0f0"
            )
            label.grid(row=0, column=i, sticky='ew', padx=1, pady=1)

        for idx, ip in enumerate(self.ip_statuses.keys()):
            ip_label = tk.Label(
                self.list_frame,
                text=ip,
                width=12,
                relief=tk.RIDGE
            )
            ip_label.grid(row=idx + 1, column=0, sticky='ew', padx=1, pady=1)

            status_label = tk.Label(
                self.list_frame,
                text="检测中...",
                width=10,
                relief=tk.RIDGE,
                fg="gray"
            )
            status_label.grid(row=idx + 1, column=1, sticky='ew', padx=1, pady=1)

            latency_label = tk.Label(
                self.list_frame,
                text="-",
                width=12,
                relief=tk.RIDGE
            )
            latency_label.grid(row=idx + 1, column=2, sticky='ew', padx=1, pady=1)

            remove_button = tk.Button(
                self.list_frame,
                text="移除",
                command=lambda ip=ip: self._remove_ip(ip),
                width=10
            )
            remove_button.grid(row=idx + 1, column=3, sticky='ew', padx=1, pady=1)

            self.ip_statuses[ip].widgets = {
                'status': status_label,
                'latency': latency_label
            }

            if self.ip_statuses[ip].reachable:
                self._update_ip_display(ip)

    def _validate_ip(self, ip):
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False

    def _check_single_ip(self, ip):
        status = self.ip_statuses.get(ip)
        if not status:
            return

        reachable, latency = PingChecker.ping(ip)
        status.reachable = reachable
        status.latency = latency
        status.last_check = time.time()

        self.root.after(0, lambda: self._update_ip_display(ip))

    def _check_all_ips(self):
        for ip in self.ip_statuses.keys():
            threading.Thread(target=self._check_single_ip, args=(ip,), daemon=True).start()

    def _update_ip_display(self, ip):
        status = self.ip_statuses.get(ip)
        if not status or not hasattr(status, 'widgets'):
            return

        widgets = status.widgets
        if status.reachable:
            widgets['status'].config(text="✓ 在线", fg="green")
            latency_text = f"{status.latency:.1f}" if status.latency else "-"
            widgets['latency'].config(text=latency_text)
        else:
            widgets['status'].config(text="✗ 离线", fg="red")
            widgets['latency'].config(text="-")

    def _start_auto_refresh(self):
        self._check_all_ips()
        if self.should_refresh:
            self.root.after(REFRESH_INTERVAL, self._start_auto_refresh)

    def _update_status(self):
        total = len(self.ip_statuses)
        online = sum(1 for s in self.ip_statuses.values() if s.reachable)
        self.status_label.config(text=f"共监测 {total} 个 IP，{online} 个在线")

    def on_close(self):
        self.should_refresh = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = IPMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
