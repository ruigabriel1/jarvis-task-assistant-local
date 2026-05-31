import os
import subprocess
import sys

def main():
    print("Verificando se PyInstaller está instalado...")
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller não encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    project_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    
    app_pyw = os.path.join(project_dir, 'src', 'ui', 'app.pyw')
    icon_path = os.path.join(project_dir, 'assets', 'icon.ico')
    
    # CustomTkinter usually requires its assets included explicitly
    # But usually PyInstaller 5.0+ handles it. We'll add assets manually just in case
    # data_add = f"assets{os.pathsep}assets"  # This is for internal PyInstaller bundling, but we are using external folder
    
    print("Iniciando build do Jarvis.exe...")
    
    # We don't bundle assets internally because config and models should be modifiable,
    # and icons/images are already loaded using sys.executable paths.
    # Actually, we should bundle the icon or just copy it. 
    # For now, just generate the exe without internal assets, as our code expects 'assets/icon.png' next to the exe.
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--noconfirm",
        "--name", "Jarvis",
        "--icon", icon_path,
        app_pyw
    ]
    
    subprocess.check_call(cmd, cwd=project_dir)
    
    # Copy essential external folders and files to dist/Jarvis
    import shutil
    dist_dir = os.path.join(project_dir, 'dist', 'Jarvis')
    print("Copiando assets e configurações para a pasta de distribuição...")
    
    assets_src = os.path.join(project_dir, 'assets')
    assets_dst = os.path.join(dist_dir, 'assets')
    if os.path.exists(assets_src):
        if os.path.exists(assets_dst):
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
        
    config_src = os.path.join(project_dir, 'config.json')
    config_dst = os.path.join(dist_dir, 'config.json')
    if os.path.exists(config_src):
        shutil.copy2(config_src, config_dst)
        
    print("Build finalizado com sucesso. O executável está na pasta dist/Jarvis.")

if __name__ == "__main__":
    main()
