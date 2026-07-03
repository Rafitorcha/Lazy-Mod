import os
import zipfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input
from textual.containers import Vertical, Center
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


class LazyModManager(App):
    """Aplicacion TUI fluida controlada 100% por teclado."""
    
    BINDINGS = [
        Binding("up,k", "navigate_up", "Arriba", show=True),
        Binding("down,j", "navigate_down", "Abajo", show=True),
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
        margin: 10 0 0 4;
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
    
    /* ===== MODAL OVERLAY - Cubre toda la pantalla ===== */
    #modal-overlay {
        background: rgba(0, 0, 0, 0.85);  /* Fondo semitransparente oscuro */
        align: center middle;
        width: 100%;
        height: 100%;
        layer: modal;  /* Se superpone sobre todo */
    }
    #modal-box {
        background: #282828;
        border: heavy #fabd2f;
        padding: 3;
        width: 70%;
        height: auto;
        align: center middle;
    }
    #modal-box Label {
        color: #a89984;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }
    #modal-box Label.title {
        color: #fabd2f;
        text-style: bold;
        margin-bottom: 2;
    }
    #modal-box Input {
        background: #1b1b1b;
        color: #ebdbb2;
        border: solid #fe8019;
        width: 100%;
        margin-bottom: 1;
    }
    #modal-box Input:focus {
        border: solid #fabd2f;
    }
    #modal-box .hint {
        color: #888888;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(self):
        super().__init__()
        # Configuración persistente
        self.config_file = Path.home() / ".config" / "lazy-mod-manager" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_config()
        
        # Variables de estado
        self.delete_mode = False
        self.file_list = None
        self.instrucciones_label = None
        self._modal_callback = None
        self._is_ready = False

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
            f"  [>] Source: {DOWNLOADS_DIR}\n",
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

    def action_set_source_dir(self) -> None:
        """Cambia la ruta de origen - Modal overlay"""
        def callback(value: str) -> None:
            global DOWNLOADS_DIR
            new_path = Path(value.strip())
            if new_path.exists():
                DOWNLOADS_DIR = new_path
                self.save_config()
                self.notify(f"[+] Source updated: {DOWNLOADS_DIR}")
                self.refresh_list()
                # Actualizar el banner
                banner = self.query_one("#banner")
                if banner:
                    # Reconstruir banner con nueva ruta
                    pass
            else:
                self.notify("[-] Directory does not exist", severity="error")
        
        self._show_modal(
            "Change Source Directory",
            "Enter new source directory (Downloads):",
            str(DOWNLOADS_DIR),
            callback
        )

    def action_set_target_dir(self) -> None:
        """Cambia la ruta de destino - Modal overlay"""
        def callback(value: str) -> None:
            global MODS_DIR
            new_path = Path(value.strip())
            MODS_DIR = new_path
            self.save_config()
            self.notify(f"[+] Target updated: {MODS_DIR}")
        
        self._show_modal(
            "Change Target Directory",
            "Enter new target directory (Mods):",
            str(MODS_DIR),
            callback
        )

    def action_reset_paths(self) -> None:
        global DOWNLOADS_DIR, MODS_DIR
        DOWNLOADS_DIR = Path.home() / "Downloads"
        MODS_DIR = Path.home() / ".local/share/Steam/steamapps/compatdata/3580745457/pfx/drive_c/users/steamuser/Local Settings/Application Data/RivalsofAether/workshop"
        self.save_config()
        self.notify("[*] Paths reset to defaults")
        self.refresh_list()

    def action_refresh(self) -> None:
        self.refresh_list()
        self.notify("[*] List refreshed")

    def _show_modal(self, title: str, prompt: str, placeholder: str, callback) -> None:
        """Muestra un modal overlay que cubre toda la pantalla"""
        self._modal_callback = callback
        
        # Crear el overlay con el modal centrado
        overlay = Vertical(
            Center(
                Vertical(
                    Label(title, classes="title"),
                    Label(prompt),
                    Input(placeholder=placeholder, id="modal-input"),
                    Label("Enter to Accept  •  Escape to Cancel", classes="hint"),
                    id="modal-box"
                )
            ),
            id="modal-overlay"
        )
        self.mount(overlay)
        
        # Enfocar el input
        input_widget = self.query_one("#modal-input", Input)
        input_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Maneja Enter en el Input (aceptar)"""
        if event.input.id == "modal-input" and self._modal_callback:
            value = event.input.value.strip()
            if value:
                self._modal_callback(value)
            # Cerrar el modal
            overlay = self.query_one("#modal-overlay")
            overlay.remove()
            self._modal_callback = None

    def on_key(self, event) -> None:
        """Maneja teclas globales cuando el modal está activo"""
        # Si el modal está activo y presionan Escape
        if event.key == "escape":
            try:
                overlay = self.query_one("#modal-overlay")
                overlay.remove()
                self._modal_callback = None
                self.notify("[*] Cancelled")
                event.prevent_default()
            except:
                pass  # No hay modal activo

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