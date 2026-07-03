import os
import zipfile
import shutil
import json
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input
from textual.containers import Vertical, Center, Container
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
        self.query_one("#modal-input").focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "modal-input":
            value = event.input.value.strip()
            if value:
                self.callback(value)
            self.dismiss()
    
    def on_key(self, event) -> None:
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
        Binding("h", "show_history_modal", "Historial", show=True),
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
        self.config_file = Path.home() / ".config" / "lazy-mod-manager" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.delete_mode = False
        self.file_list = None
        self.instrucciones_label = None
        
        # Historial
        self.path_history = []
        self.max_history = 20
        
        self.load_config()

    def load_config(self):
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
                    if "path_history" in config:
                        self.path_history = config["path_history"]
            except Exception as e:
                print(f"[DEBUG] Error loading config: {e}")

    def save_config(self):
        try:
            config = {
                "downloads_dir": str(DOWNLOADS_DIR),
                "mods_dir": str(MODS_DIR),
                "delete_mode": self.delete_mode,
                "path_history": self.path_history[-10:]
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"[DEBUG] Error saving config: {e}")

    def _add_to_history(self, path: Path, path_type: str = "source") -> None:
        """Añade una ruta al historial"""
        path_str = str(path)
        
        for i, item in enumerate(self.path_history):
            if item.get("path") == path_str:
                self.path_history.pop(i)
                break
        
        self.path_history.append({"path": path_str, "type": path_type})
        
        if len(self.path_history) > self.max_history:
            self.path_history.pop(0)
        
        self.save_config()
        print(f"[DEBUG] Historial: {self.path_history}")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
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
        
        self.instrucciones_label = Label(
            self._build_instructions_text(),
            id="instrucciones"
        )
        yield self.instrucciones_label
        
        self.file_list = ListView()
        yield Vertical(self.file_list, id="list-container")
        
        yield Footer()

    def _build_instructions_text(self) -> str:
        estado = "[+] DELETE YES" if self.delete_mode else "[-] DELETE NO"
        return (
            f"[>] ↑/↓ Navigate  •  Space Mark  •  D {estado}  •  "
            f"Enter Install  •  S Source  •  T Target  •  "
            f"h History  •  R Refresh  •  Q Quit"
        )

    def _update_instructions(self) -> None:
        if self.instrucciones_label:
            self.instrucciones_label.update(self._build_instructions_text())

    def on_mount(self) -> None:
        self.refresh_list()
        
        # Agregar rutas iniciales al historial
        if not self.path_history:
            self._add_to_history(DOWNLOADS_DIR, "source")
            self._add_to_history(MODS_DIR, "destination")
        
        if self.delete_mode:
            self.notify("[+] Delete Mode: ENABLED (from last session)", severity="warning")
        else:
            self.notify("[*] Delete Mode: DISABLED (from last session)")

    def refresh_list(self) -> None:
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

    # ===== ACCIONES DE NAVEGACIÓN =====
    
    def action_navigate_up(self) -> None:
        if self.file_list and self.file_list.index is not None and self.file_list.index > 0:
            self.file_list.index -= 1

    def action_navigate_down(self) -> None:
        if self.file_list and self.file_list.index is not None and self.file_list.index < len(self.file_list.children) - 1:
            self.file_list.index += 1
    # ===== ACCIONES PRINCIPALES =====

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
        def callback(value: str) -> None:
            global DOWNLOADS_DIR
            new_path = Path(value.strip())
            if new_path.exists():
                DOWNLOADS_DIR = new_path
                self._add_to_history(DOWNLOADS_DIR, "source")
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
        def callback(value: str) -> None:
            global MODS_DIR
            new_path = Path(value.strip())
            if new_path.exists():
                MODS_DIR = new_path
                self._add_to_history(MODS_DIR, "destination")
                self.save_config()
                self.notify(f"[+] Target updated: {MODS_DIR}")
            else:
                self.notify("[-] Directory does not exist", severity="error")
        
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
        self._add_to_history(DOWNLOADS_DIR, "source")
        self._add_to_history(MODS_DIR, "destination")
        self.save_config()
        self.notify("[*] Paths reset to defaults")
        self.refresh_list()
        self._update_banner()

    def action_refresh(self) -> None:
        self.refresh_list()
        self.notify("[*] List refreshed")

    # ===== HISTORIAL CON SELECCIÓN =====
    
    def action_show_history_modal(self) -> None:
        """Muestra el historial con opción de seleccionar"""
        if not self.path_history:
            self.notify("[*] No hay historial de directorios aún", severity="warning")
            return
        
        # Construir el mensaje con las rutas numeradas
        msg = "Historial de directorios:\n\n"
        for i, entry in enumerate(self.path_history, 1):
            path = entry["path"]
            path_type = entry.get("type", "source")
            type_label = "📁 Origen" if path_type == "source" else "📂 Destino"
            
            # Marcar si es la ruta actual
            is_current = path == str(DOWNLOADS_DIR) or path == str(MODS_DIR)
            marker = "→ " if is_current else "  "
            msg += f"{marker}{i}. {type_label}: {path}\n"
        
        msg += "\nEscribe el número de la ruta y presiona Enter"
        msg += "\n[S] Origen  •  [T] Destino (ej: '3s' o '5t')"
        
        # Mostrar modal con el historial
        self._show_history_selection_modal(msg)

    def _show_history_selection_modal(self, msg: str) -> None:
        """Muestra un modal para seleccionar del historial"""
        
        def callback(value: str) -> None:
            value = value.strip().lower()
            
            # Determinar si tiene S o T al final
            apply_type = None
            number_str = value
            
            if value.endswith('s'):
                apply_type = "source"
                number_str = value[:-1]
            elif value.endswith('t'):
                apply_type = "destination"
                number_str = value[:-1]
            
            # Si no tiene S/T, preguntar
            if apply_type is None:
                self.notify("[*] Especifica 's' para Origen o 't' para Destino", severity="warning")
                self.notify("[*] Ejemplo: '3s' o '5t'", severity="warning")
                return
            
            # Obtener el número
            try:
                index = int(number_str) - 1
            except ValueError:
                self.notify("[-] Debes escribir un número", severity="error")
                return
            
            # Validar índice
            if 0 <= index < len(self.path_history):
                self._apply_history_selection(index, apply_type)
            else:
                self.notify(f"[-] Número inválido. Hay {len(self.path_history)} rutas", severity="error")
        
        # Mostrar el modal
        modal = ModalScreen(
            "History Selection",
            msg,
            "Ej: 3s (origen) o 5t (destino)",
            callback
        )
        self.push_screen(modal)

    def _apply_history_selection(self, index: int, apply_type: str) -> None:
        """Aplica la selección del historial"""
        if 0 <= index < len(self.path_history):
            entry = self.path_history[index]
            selected_path = Path(entry["path"])
            
            if not selected_path.exists():
                self.notify(f"[-] La ruta ya no existe: {selected_path}", severity="error")
                self.path_history.pop(index)
                self.save_config()
                return
            
            if apply_type == "source":
                global DOWNLOADS_DIR
                DOWNLOADS_DIR = selected_path
                self._add_to_history(DOWNLOADS_DIR, "source")
                self.save_config()
                self.notify(f"[+] Origen cargado del historial: {DOWNLOADS_DIR}")
                self.refresh_list()
                self._update_banner()
            else:
                global MODS_DIR
                MODS_DIR = selected_path
                self._add_to_history(MODS_DIR, "destination")
                self.save_config()
                self.notify(f"[+] Destino cargado del historial: {MODS_DIR}")

    # ===== EXTRACCIÓN =====
    
    def process_extraction(self) -> None:
        if not self.file_list:
            return
            
        if not MODS_DIR.exists():
            self.notify(f"[-] Target directory does not exist: {MODS_DIR}", severity="error")
            self.notify("[*] Create it first or check your path", severity="warning")
            return
        
        extracted_count = 0
        deleted_count = 0

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
                    self.notify(f"[-] Error with {item.file_path.name}: {e}", severity="error")

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