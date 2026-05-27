import os
import sys
import shutil
import subprocess


def clean_old_dist():
    if os.path.exists('dist'):
        print("清理旧的 dist 目录...")
        shutil.rmtree('dist')


def install_dependencies():
    print("安装依赖...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)


def build_executable():
    print("生成可执行文件...")
    executable_name = 'IPMonitor'

    cmd = [
        'pyinstaller',
        '--onefile',
        '--windowed',
        '--name', executable_name,
        'main.py'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("打包失败:")
        print(result.stderr)
        return False

    return True


def organize_dist():
    os.makedirs('dist/win', exist_ok=True)
    os.makedirs('dist/linux', exist_ok=True)
    os.makedirs('dist/macos', exist_ok=True)
    os.makedirs('dist/script', exist_ok=True)

    if os.name == 'nt':
        if os.path.exists('dist/IPMonitor.exe'):
            shutil.move('dist/IPMonitor.exe', 'dist/win/IPMonitor.exe')
        if os.path.exists('dist/IPMonitor'):
            shutil.move('dist/IPMonitor', 'dist/linux/IPMonitor')
    elif sys.platform == 'darwin':
        if os.path.exists('dist/IPMonitor'):
            shutil.move('dist/IPMonitor', 'dist/macos/IPMonitor')
        if os.path.exists('dist/IPMonitor.exe'):
            shutil.move('dist/IPMonitor.exe', 'dist/win/IPMonitor.exe')
    else:
        if os.path.exists('dist/IPMonitor'):
            shutil.move('dist/IPMonitor', 'dist/linux/IPMonitor')
        if os.path.exists('dist/IPMonitor.exe'):
            shutil.move('dist/IPMonitor.exe', 'dist/win/IPMonitor.exe')

    shutil.copy('config.json', 'dist/script/')
    shutil.copy('main.py', 'dist/script/')
    shutil.copy('requirements.txt', 'dist/script/')

    with open('dist/script/run.bat', 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('cd /d "%~dp0"\n')
        f.write('python main.py\n')
        f.write('pause\n')

    with open('dist/script/run.sh', 'w', encoding='utf-8') as f:
        f.write('#!/bin/bash\n')
        f.write('cd "$(dirname "$0")"\n')
        f.write('python3 main.py\n')

    if sys.platform != 'win32':
        os.chmod('dist/script/run.sh', 0o755)

    clean_build_files()


def clean_build_files():
    if os.path.exists('build'):
        shutil.rmtree('build')

    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.spec'):
                os.remove(os.path.join(root, file))


def main():
    try:
        clean_old_dist()
        install_dependencies()

        if build_executable():
            organize_dist()
            print("\n打包成功！")
            print("\n生成的文件结构:")
            print("dist/")
            print("├── win/")
            print("│   └── IPMonitor.exe")
            print("├── linux/")
            print("│   └── IPMonitor")
            print("├── macos/")
            print("│   └── IPMonitor")
            print("└── script/")
            print("    ├── main.py")
            print("    ├── config.json")
            print("    ├── requirements.txt")
            print("    ├── run.bat")
            print("    └── run.sh")
        else:
            sys.exit(1)

    except Exception as e:
        print(f"打包过程出错: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
