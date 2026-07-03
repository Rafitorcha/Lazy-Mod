import os
import zipfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input
from textual.containers import Vertical, Center, Container  # 👈 Container AQUÍ
from textual.binding import Binding


# --- CONFIGURACIÓN DE RUTAS (GLOBALES) ---
DOWNLOADS_DIR = Path.home() / "Downloads"
MODS_DIR = Path.home() / ".local/share/Steam/steamapps/compatdata/3580745457/pfx/drive_c/users/steamuser/Local Settings/Application Data/RivalsofAether/workshop"


class FileItem(ListItem):
    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.file_path = file_path
        self.selected_for_extraction = False
        self.label = Label(f"  [ ]  {self.file_path.name}")

    def compose(self) -> ComposeResult:
        yield self.label

    def toggle_selection(self) -> None:
        self.selected_for_extraction = not self.selected_for_extraction
        status = "[X]" if self.selected_for_extraction else "[ ]"
        self.label.update(f"  {status}  {self.file_path.name}")
        
        if self.selected_for_extraction:
            self.add_class("selected")
        else:
            self.remove_class("selected")


class ModalScreen(Screen):
    """Pantalla de modal para entrada de texto"""
    
    def __init__(self, title: str, prompt: str, placeholder: str, callback):
        super().__init__()
        self.title_text = title
        self.prompt_text = prompt
        self.placeholder = placeholder
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        yield Container(
            Center(
                Vertical(
                    Label(self.title_text, classes="modal-title"),
                    Label(self.prompt_text, classes="modal-prompt"),
                    Input(placeholder=self.placeholder, id="modal-input"),
                    Label("Enter: Accept  •  Escape: Cancel", classes="modal-hint"),
                    classes="modal-box"
                )
            ),
            id="modal-container"
        )
    
    def on_mount(self) -> None:
        """Enfocar el input al montar"""
        self.query_one("#modal-input").focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter acepta"""
        if event.input.id == "modal-input":
            value = event.input.value.strip()
            if value:
                self.callback(value)
            self.dismiss()
    
    def on_key(self, event) -> None:
        """Escape cancela"""
        if event.key == "escape":
            self.dismiss()


class LazyModManager(App):
    """Aplicacion TUI fluida controlada 100% por teclado."""
    
    BINDINGS = [
        Binding("up,↑", "navigate_up", "Arriba", show=True),
        Binding("down,↓", "navigate_down", "Abajo", show=True),
        Binding("space", "toggle_file", "Marcar Mod", show=True),
        Binding("d", "toggle_delete_mode", "Modo Borrar", show=True),
        Binding("enter", "trigger_extraction", "Instalar", show=True),
        Binding("s", "set_source_dir", "Ruta Origen", show=True),
        Binding("t", "set_target_dir", "Ruta Destino", show=True),
        Binding("r", "reset_paths", "Resetear", show=True),
        Binding("R", "refresh", "Refrescar", show=True),
        Binding("q", "quit", "Salir", show=True),
    ]

    CSS = """
    Screen {
        background: #1b1b1b;
    }
    #banner {
        color: #fabd2f;
        text-style: bold;
        margin: 1 0 0 4;
        height: auto;
    }
    #instrucciones {
        margin: 0 2 1 2;
        color: #a89984;
        background: #282828;
        padding: 0 1;
    }
    #list-container {
        border: heavy #fe8019;
        margin: 0 2 1 2;
        padding: 1;
        height: 65%;
    }
    ListView {
        background: #1b1b1b;
    }
    ListView:focus {
        border: none;
    }
    ListItem {
        padding: 0 1;
        color: #a89984;
    }
    ListView > ListItem:hover {
        background: #3c3836;
        color: #ebdbb2;
    }
    ListView:focus > ListItem:focus {
        background: #504945;
        color: #fabd2f;
        text-style: bold;
    }
    ListItem.selected {
        color: #fe8019 !important;
    }
    
    /* ===== MODAL SCREEN ===== */
    #modal-container {
        width: 100%;
        height: 100%;
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    .modal-box {
        background: #282828;
        border: heavy #fabd2f;
        padding: 3;
        width: 70%;
        height: auto;
        align: center middle;
    }
    .modal-title {
        color: #fabd2f;
        text-style: bold;
        text-align: center;
        margin-bottom: 2;
    }
    .modal-prompt {
        color: #a89984;
        text-align: center;
        margin-bottom: 1;
    }
    .modal-hint {
        color: #888888;
        text-style: italic;
        text-align: center;
        margin-top: 1;
    }
    #modal-input {
        background: #1b1b1b;
        color: #ebdbb2;
        border: solid #fe8019;
        width: 100%;
        margin-bottom: 1;
    }
    #modal-input:focus {
        border: solid #fabd2f;
    }
    """

    def __init__(self):
        super().__init__()
        # Configuración persistente
        self.config_file = Path.home() / ".config" / "lazy-mod-manager" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Variables de estado
        self.delete_mode = False
        self.file_list = None
        self.instrucciones_label = None
        self._modal_callback = None
        self._is_ready = False
        
        # Cargar configuración
        self.load_config()

    def load_config(self):
        """Carga configuración si existe"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    global DOWNLOADS_DIR, MODS_DIR
                    if "downloads_dir" in config:
                        DOWNLOADS_DIR = Path(config["downloads_dir"])
                    if "mods_dir" in config:
                        MODS_DIR = Path(config["mods_dir"])
                    if "delete_mode" in config:
                        self.delete_mode = config["delete_mode"]
            except:
                pass

    def save_config(self):
        """Guarda configuración"""
        try:
            config = {
                "downloads_dir": str(DOWNLOADS_DIR),
                "mods_dir": str(MODS_DIR),
                "delete_mode": self.delete_mode
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Banner
        delete_status = "[+] DELETE ON" if self.delete_mode else "[-] DELETE OFF"
        yield Label(
            "█████                                          ██████   ██████              █████\n"
            "░░███                                          ░░██████ ██████              ░░███\n"
            "░███         ██████    █████████ █████ ████    ░███░█████░███   ██████   ███████   █████\n" 
            "░███        ░░░░░███  ░█░░░░███ ░░███ ░███     ░███░░███ ░███  ███░░███ ███░░███  ███░░\n"
            "░███         ███████  ░   ███░   ░███ ░███     ░███ ░░░  ░███ ░███ ░███░███ ░███ ░░█████\n"
            "░███      █ ███░░███    ███░   █ ░███ ░███     ░███      ░███ ░███ ░███░███ ░███  ░░░░███\n"
            "███████████░░████████  █████████ ░░███████     █████     █████░░██████ ░░████████ ██████\n"
            "░░░░░░░░░░░  ░░░░░░░░  ░░░░░░░░░   ░░░░░███    ░░░░░     ░░░░░  ░░░░░░   ░░░░░░░░ ░░░░░░\n"
            "                                   ███ ░███                                             \n"
            "                                  ░░██████                                               \n"
            "                                    ░░░░░░                                               \n"
            f"  [>] Source: {DOWNLOADS_DIR}  •  {delete_status}\n"
            f"  Watch out with Caps Lock • Use 'pwd' for paths • Avoid trailing '/'\n",
            id="banner"
        )
        
        # Instrucciones
        self.instrucciones_label = Label(
            self._build_instructions_text(),
            id="instrucciones"
        )
        yield self.instrucciones_label
        
        # Lista
        self.file_list = ListView()
        yield Vertical(self.file_list, id="list-container")
        
        yield Footer()

    def _build_instructions_text(self) -> str:
        estado = "[+] DELETE YES" if self.delete_mode else "[-] DELETE NO"
        return (
            f"[>] ↑/↓ Navigate  •  Space Mark  •  D {estado}  •  "
            f"Enter Install  •  S Source  •  T Target  •  R Refresh  •  Q Quit"
        )

    def _update_instructions(self) -> None:
        if self.instrucciones_label:
            self.instrucciones_label.update(self._build_instructions_text())

    def on_mount(self) -> None:
        self._is_ready = True
        self.refresh_list()
        if self.delete_mode:
            self.notify("[+] Delete Mode: ENABLED (from last session)", severity="warning")
        else:
            self.notify("[*] Delete Mode: DISABLED (from last session)")

    def refresh_list(self) -> None:
        """Refresca la lista de archivos"""
        if self.file_list is None:
            return
        
        self.file_list.clear()
        
        if not DOWNLOADS_DIR.exists():
            self.file_list.append(ListItem(Label("[!] Downloads directory not found")))
            self.file_list.append(ListItem(Label(f"[>] Current path: {DOWNLOADS_DIR}")))
            return

        zips = list(DOWNLOADS_DIR.glob("*.zip"))
        
        if not zips:
            self.file_list.append(ListItem(Label("[*] No ZIP files found in Downloads")))
        else:
            for zip_file in sorted(zips):
                self.file_list.append(FileItem(zip_file))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.process_extraction()

    # ===== ACCIONES =====

    def action_toggle_file(self) -> None:
        if not self.file_list:
            return
        active_item = self.file_list.highlighted_child
        if isinstance(active_item, FileItem):
            active_item.toggle_selection()
            self.file_list.refresh()

    def action_trigger_extraction(self) -> None:
        self.process_extraction()

    def action_toggle_delete_mode(self) -> None:
        self.delete_mode = not self.delete_mode
        self.save_config()
        
        if self.delete_mode:
            self.notify("[+] Delete Mode: ENABLED", severity="warning")
        else:
            self.notify("[*] Delete Mode: DISABLED")
        
        self._update_instructions()
        self._update_banner()

    def _update_banner(self):
        """Actualiza el banner con el estado actual"""
        delete_status = "[+] DELETE ON" if self.delete_mode else "[-] DELETE OFF"
        banner = self.query_one("#banner")
        if banner:
            banner.update(
                "█████                                          ██████   ██████              █████\n"
                "░░███                                          ░░██████ ██████              ░░███\n"
                "░███         ██████    █████████ █████ ████    ░███░█████░███   ██████   ███████   █████\n" 
                "░███        ░░░░░███  ░█░░░░███ ░░███ ░███     ░███░░███ ░███  ███░░███ ███░░███  ███░░\n"
                "░███         ███████  ░   ███░   ░███ ░███     ░███ ░░░  ░███ ░███ ░███░███ ░███ ░░█████\n"
                "░███      █ ███░░███    ███░   █ ░███ ░███     ░███      ░███ ░███ ░███░███ ░███  ░░░░███\n"
                "███████████░░████████  █████████ ░░███████     █████     █████░░██████ ░░████████ ██████\n"
                "░░░░░░░░░░░  ░░░░░░░░  ░░░░░░░░░   ░░░░░███    ░░░░░     ░░░░░  ░░░░░░   ░░░░░░░░ ░░░░░░\n"
                "                                   ███ ░███                                             \n"
                "                                  ░░██████                                               \n"
                "                                    ░░░░░░                                               \n"
                f"  [>] Source: {DOWNLOADS_DIR}  •  {delete_status}\n"
                f"  Watch out with Caps Lock • Use 'pwd' for paths • Avoid trailing '/'\n"
            )

    def action_set_source_dir(self) -> None:
        """Cambia la ruta de origen - Como pantalla separada"""
        def callback(value: str) -> None:
            global DOWNLOADS_DIR
            new_path = Path(value.strip())
            if new_path.exists():
                DOWNLOADS_DIR = new_path
                self.save_config()
                self.notify(f"[+] Source updated: {DOWNLOADS_DIR}")
                self.refresh_list()
                self._update_banner()
            else:
                self.notify("[-] Directory does not exist", severity="error")
        
        modal = ModalScreen(
            "Change Source Directory",
            "Enter new source directory (Downloads):",
            str(DOWNLOADS_DIR),
            callback
        )
        self.push_screen(modal)

    def action_set_target_dir(self) -> None:
        """Cambia la ruta de destino - Como pantalla separada"""
        def callback(value: str) -> None:
            global MODS_DIR
            new_path = Path(value.strip())
            MODS_DIR = new_path
            self.save_config()
            self.notify(f"[+] Target updated: {MODS_DIR}")
        
        modal = ModalScreen(
            "Change Target Directory",
            "Enter new target directory (Mods):",
            str(MODS_DIR),
            callback
        )
        self.push_screen(modal)

    def action_reset_paths(self) -> None:
        global DOWNLOADS_DIR, MODS_DIR
        DOWNLOADS_DIR = Path.home() / "Downloads"
        MODS_DIR = Path.home() / ".local/share/Steam/steamapps/compatdata/3580745457/pfx/drive_c/users/steamuser/Local Settings/Application Data/RivalsofAether/workshop"
        self.save_config()
        self.notify("[*] Paths reset to defaults")
        self.refresh_list()
        self._update_banner()

    def action_refresh(self) -> None:
        self.refresh_list()
        self.notify("[*] List refreshed")

    def process_extraction(self) -> None:
        """Procesa la extracción de los mods seleccionados"""
        if not self.file_list:
            return
            
        extracted_count = 0
        deleted_count = 0
        MODS_DIR.mkdir(parents=True, exist_ok=True)

        for item in self.file_list.children:
            if isinstance(item, FileItem) and item.selected_for_extraction:
                try:
                    zip_name_without_ext = item.file_path.stem
                    clean_id_name = zip_name_without_ext.replace("_", " ").split(" ")[0]
                    base_target_folder = MODS_DIR / clean_id_name
                    
                    if base_target_folder.exists():
                        shutil.rmtree(base_target_folder)
                    base_target_folder.mkdir(parents=True, exist_ok=True)

                    with zipfile.ZipFile(item.file_path, 'r') as zip_ref:
                        zip_ref.extractall(base_target_folder)

                    subfolders = [x for x in base_target_folder.iterdir() if x.is_dir()]
                    if subfolders:
                        long_name_folder = subfolders[0]
                        for file_or_dir in long_name_folder.iterdir():
                            dest = base_target_folder / file_or_dir.name
                            if dest.exists():
                                if dest.is_dir():
                                    shutil.rmtree(dest)
                                else:
                                    dest.unlink()
                            file_or_dir.rename(dest)
                        long_name_folder.rmdir()

                    extracted_count += 1

                    if self.delete_mode:
                        item.file_path.unlink()
                        deleted_count += 1

                except Exception as e:
                    self.notify(f"[-] Error: {e}", severity="error")

        if extracted_count > 0:
            if self.delete_mode:
                self.notify(f"[+] {extracted_count} mods installed, {deleted_count} zips deleted")
            else:
                self.notify(f"[+] {extracted_count} mods installed successfully")
            self.refresh_list()
        else:
            self.notify("[-] No files selected with [Space]", severity="warning")


if __name__ == "__main__":
    app = LazyModManager()
    app.run()