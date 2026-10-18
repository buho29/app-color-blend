import logging
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from CTkToolTip import CTkToolTip

from .color import Color
from .model import Model
from .widgets import (
    BG_EMPTY, BG_PANEL,
    CTKEyeDropper, CTkSpinbox, GalleryColor, ListBlend,
    color_tooltip, get_color_label, open_result_window,
)

logger = logging.getLogger(__name__)

# por encima de este número de mezclas se pide confirmación antes de buscar
MAX_COMBINATIONS = 2_000_000
# segundos de cálculo entre cada repintado de la ventana durante la búsqueda
SEARCH_SLICE = 0.04


class View(ctk.CTkFrame):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, **kwargs)
        self.model: Model = model


# busca la mejor combinacion de un color
class ViewFind(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.model.add_event(self.clear_results)

        self.eye_dropper = None
        self.tooltips = list()
        self.blends = None
        self.result_win = None

        # búsqueda en curso (generador de Model.iter_find_blend)
        self._search = None
        self._search_target = None

        self.target_color = Color(rgb=(255, 192, 203))  # pink

        # configure grid layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar_frame = ctk.CTkFrame(master=self, width=140, corner_radius=0)
        sidebar_frame.grid_rowconfigure(3, weight=1)
        sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")

        form_frame = ctk.CTkFrame(master=sidebar_frame)
        form_frame.grid(row=0, column=0, padx=20, pady=(20, 10))

        # (nombre, etiqueta, valor, mínimo, máximo, ayuda)
        fields = (
            ('max_delta_e', 'ΔE máx.', 10, 1, 50,
             'Diferencia máxima con el color buscado.\n'
             '<1 imperceptible, 1-2 solo de cerca, 2-10 a simple vista'),
            ('color_max', 'Colores máx.', 4, 1, 5,
             'Número máximo de pinturas distintas en la mezcla'),
            ('cant_max', 'Gotas máx.', 4, 1, 10,
             'Número máximo de gotas de cada pintura'),
        )
        self.inputs = {}
        for row, (name, text, value, min_value, max_value, help_text) in enumerate(fields):
            label = ctk.CTkLabel(form_frame, text=text)
            label.grid(row=row, column=0, padx=20, pady=(20, 20))
            CTkToolTip(label, message=help_text)
            spinbox = CTkSpinbox(master=form_frame, from_=min_value, to=max_value)
            spinbox.set(value)
            spinbox.grid(row=row, column=1, padx=10, pady=5)
            self.inputs[name] = spinbox

        self.btn_color = ctk.CTkButton(
            master=sidebar_frame, text='Seleccionar color',
            fg_color=self.target_color.get_hex(),
            text_color=get_color_label(self.target_color),
            command=self.select_color
        )
        self.btn_color.grid(row=1, column=0, padx=20, pady=(0, 10))
        self.btn_eye = ctk.CTkButton(
            master=sidebar_frame, text='Cuenta Gotas',
            fg_color=self.target_color.get_hex(),
            text_color=get_color_label(self.target_color),
            command=self.open_eye_dropper
        )
        self.btn_eye.grid(row=2, column=0, padx=20, pady=(0, 10))
        CTkToolTip(self.btn_eye, message='Clic para capturar un color de la pantalla\nEsc para cancelar')

        self.status = ctk.CTkLabel(master=sidebar_frame, text='', wraplength=220)
        self.status.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="s")

        self.btn_find = ctk.CTkButton(master=sidebar_frame, text='Buscar',
                                      command=self.find_color)
        self.btn_find.grid(row=4, column=0, padx=20, pady=(0, 10))

        # right frame
        right_frame = ctk.CTkFrame(master=self, corner_radius=0, fg_color=BG_PANEL)
        right_frame.grid_columnconfigure(1, weight=0)
        right_frame.grid_columnconfigure((0, 3), weight=1)
        right_frame.grid_rowconfigure(1, weight=0)
        right_frame.grid_rowconfigure((0, 3), weight=1)
        right_frame.grid(row=0, column=1, sticky="nsew")

        center_frame = ctk.CTkFrame(master=right_frame)
        center_frame.grid(row=1, column=1, sticky="nsew")

        self.grid_cells = list()
        index = 0
        # Cuadrícula de 3x3
        for i in range(3):
            for j in range(3):
                index += 1
                cell = ctk.CTkLabel(center_frame, text=f'{index} ', fg_color=BG_EMPTY,
                                    width=100, height=100)
                cell.bind("<Button-1>", self.show_blend)
                cell.grid(row=i, column=j)
                self.grid_cells.append(cell)
                tooltip = CTkToolTip(cell)
                tooltip.hide()
                self.tooltips.append(tooltip)

    def show_blend(self, events):
        index = None
        for row, label1 in enumerate(self.grid_cells):
            if events.widget.master is label1:
                index = row
                break

        if index is None or self.blends is None or index >= len(self.blends):
            return

        self.result_win = open_result_window(self.result_win, model=self.model)
        self.result_win.set_data(self.blends[index], self.target_color)
        self.result_win.focus()

    def set_target_color(self, rgb):
        self.target_color = Color(rgb=rgb)
        str_color = self.target_color.get_hex()
        txt_color = get_color_label(self.target_color)
        self.btn_color.configure(
            fg_color=str_color,
            text_color=txt_color
        )
        self.btn_eye.configure(
            fg_color=str_color,
            text_color=txt_color
        )

    def select_color(self):
        color = colorchooser.askcolor(
            initialcolor=self.target_color.get_hex(),
            title="Seleccionar color"
        )
        if color[0] is not None:
            self.set_target_color(color[0])

    def open_eye_dropper(self):
        if self.eye_dropper is None or not self.eye_dropper.winfo_exists():
            self.eye_dropper = CTKEyeDropper()  # create window if its None or destroyed
        else:
            self.eye_dropper.focus()  # if window exists focus it

        color = self.eye_dropper.get()
        if color is not None:
            self.set_target_color(color)

    #
    #         Búsqueda por pasos
    #
    # La búsqueda es un generador que se avanza a trozos desde el bucle de Tk.
    # No se usa un hilo porque, con el GIL, el hilo de cálculo frena cada
    # llamada de Tk y la ventana deja de responder igualmente.

    def find_color(self):
        if self._search is not None:
            # hay una búsqueda en marcha: el botón sirve para cancelarla
            self.stop_search('Búsqueda cancelada')
            return

        max_delta_e = self.inputs['max_delta_e'].get()
        co_max = self.inputs['color_max'].get()
        cant = self.inputs['cant_max'].get()
        if None in (max_delta_e, co_max, cant):
            self.status.configure(text='Revisa los valores: tienen que ser números')
            return

        total = Model.count_combinations(len(self.model.colors), co_max, cant)
        if total > MAX_COMBINATIONS and not messagebox.askyesno(
                'Búsqueda grande',
                f'Se van a probar {total:,} mezclas y puede tardar mucho.\n¿Continuar?'.replace(',', '.')):
            return

        self._search_target = self.target_color
        self._search = self.model.iter_find_blend(self._search_target, max_delta_e, co_max, cant)
        self.btn_find.configure(text='Cancelar')
        self.status.configure(text='Buscando…')
        self.after(1, self._step_search)

    def stop_search(self, message):
        if self._search is not None:
            self._search.close()
            self._search = None
            self.btn_find.configure(text='Buscar')
            self.status.configure(text=message)

    def _step_search(self):
        if self._search is None:
            return

        done, total = 0, 0
        end = time.perf_counter() + SEARCH_SLICE
        try:
            while time.perf_counter() < end:
                done, total = next(self._search)
        except StopIteration as e:
            self._search = None
            self.btn_find.configure(text='Buscar')
            self._show_search_result(e.value)
            return
        except Exception as e:  # se muestra en la UI
            logger.exception('error en la búsqueda')
            self.stop_search(f'Error en la búsqueda: {e}')
            return

        if total:
            self.status.configure(text=f'Buscando… {done * 100 // total}%')
        # repintar ya: con un after() siempre pendiente Tk no llega a sus tareas idle
        self.update_idletasks()
        self.after(5, self._step_search)

    def _show_search_result(self, result):
        target = self._search_target
        self.status.configure(text=f'{len(result)} mezclas encontradas' if result else
                              'Sin resultados: prueba a subir el ΔE máx. o las gotas')

        # el color buscado va en el centro de la cuadrícula
        self.blends = result[:8]
        self.blends.insert(min(4, len(self.blends)), {
            'colors': [
                {'color': target, 'amount': 1}
            ], 'delta_e': 0.0, 'new': target
        })
        self.update_result()

    def update_result(self):
        for index, cell in enumerate(self.grid_cells):
            tooltip = self.tooltips[index]
            if self.blends is not None and index < len(self.blends):
                blend = self.blends[index]
                color = blend['new']
                color_str = color.get_hex()
                cell.configure(fg_color=color_str, text=color_str,
                               text_color=get_color_label(color))
                tooltip.configure(message=color_tooltip(color, blend['delta_e']))
                tooltip.show()
            else:
                cell.configure(fg_color=BG_EMPTY, text='')
                tooltip.hide()

    # los resultados dejan de valer si cambia la paleta o el modo de mezcla
    def clear_results(self, event_name):
        if event_name in (Model.evt_colors_loaded, Model.evt_mix_mode_changed):
            self.stop_search('Paleta o modo cambiados: vuelve a buscar')
            if self.blends is not None:
                self.blends = None
                self.status.configure(text='Paleta o modo cambiados: vuelve a buscar')
                self.update_result()


# mezcla colores manualmente
class ViewBlend(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.model.add_event(self.on_model_event)

        self.blends = list()

        # configure grid layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar_frame = ctk.CTkFrame(master=self, fg_color=('gray81', 'gray20'), corner_radius=0)
        sidebar_frame.grid_rowconfigure(1, weight=1)
        sidebar_frame.grid_columnconfigure(0, weight=1)
        sidebar_frame.grid(row=0, column=0, sticky="nsew")

        self.gallery_color = GalleryColor(master=sidebar_frame, width=260,
                                          fg_color=('gray81', 'gray20'), corner_radius=0)
        self.gallery_color.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")

        self.update_gallery()

        form_frame = ctk.CTkFrame(master=sidebar_frame)
        form_frame.grid(row=2, column=0, padx=(15, 20), pady=(10, 0), sticky="nsew")

        label = ctk.CTkLabel(form_frame, text='Cantidad')
        label.grid(row=0, column=0, padx=20, pady=5)

        self.cant = CTkSpinbox(master=form_frame, from_=1, to=10)
        self.cant.set(1)
        self.cant.grid(row=0, column=1, padx=10, pady=5)

        button = ctk.CTkButton(master=sidebar_frame, text='Agregar',
                               command=self.add_color)
        button.grid(row=3, column=0, padx=20, pady=10)

        right_frame = ctk.CTkFrame(master=self, corner_radius=0, fg_color=BG_PANEL)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=20)

        self.list_blend = ListBlend(master=right_frame, command_removed=self.removed_blend)
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.result = ctk.CTkLabel(master=right_frame, text='Result',
                                   height=100, fg_color=BG_EMPTY)
        self.result.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.result_tooltip = CTkToolTip(self.result)

        save = ctk.CTkButton(master=right_frame, text='Guardar fav.', command=self.add_favorite)
        save.grid(row=2, column=0, padx=5, pady=5)

    def on_model_event(self, event_name):
        if event_name == Model.evt_colors_loaded:
            self.update_gallery()
        elif event_name == Model.evt_mix_mode_changed:
            self.update_result()

    def update_gallery(self):
        self.gallery_color.remove_items()
        for color in self.model.colors:
            self.gallery_color.add_item(color)

    def removed_blend(self, index):
        del self.blends[index]
        self.update_result()

    def add_color(self):
        index = self.gallery_color.get()
        cant = self.cant.get()
        if index is None or cant is None:
            return
        color = self.model.colors[index]
        blend = {
            'color': color,
            'amount': cant
        }
        self.list_blend.add_item(blend)
        self.blends.append(blend)
        self.update_result()

    def update_result(self):
        if not self.blends:
            self.result.configure(text='Result', text_color=('black', 'white'), fg_color=BG_EMPTY)
            self.result_tooltip.configure(message='')
            return

        color = self.model.blend_colors(self.blends)
        color_str = color.get_hex()
        self.result.configure(text=color_str,
                              text_color=get_color_label(color),
                              fg_color=color_str)
        self.result_tooltip.configure(message=color_tooltip(color))

    def add_favorite(self, event=None):
        if self.blends:
            self.model.add_favorite(self.blends.copy())


# galeria de favoritos
class ViewFavorite(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.result_win = None
        self.model.add_event(self.update_fav)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.list_blend = ListBlend(
            master=self, width=650, corner_radius=0,
            fg_color=('gray81', 'gray20'),
            command_removed=self.removed_blend,
            command=self.show_blend
        )
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="ns")

        form_frame = ctk.CTkFrame(master=self)
        form_frame.grid(row=1, column=0, padx=(15, 20), pady=(10, 0), sticky="ew")
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_rowconfigure(0, weight=1)

        bt = ctk.CTkButton(master=form_frame, text='Borrar todos', command=self.clear_all)
        bt.grid(row=0, column=0, padx=10, pady=10)

        self.update_fav()

    def removed_blend(self, index):
        self.model.remove_favorite(index)

    def clear_all(self):
        if self.model.favorite and messagebox.askyesno(
                'Borrar favoritos', '¿Borrar todos los favoritos?'):
            self.model.clear_favorites()

    def update_fav(self, event_name=None):
        if event_name in (None,
                          Model.evt_fav_added,
                          Model.evt_fav_removed,
                          Model.evt_fav_loaded,
                          Model.evt_mix_mode_changed):
            self.list_blend.remove_items()
            for blend in self.model.favorite:
                self.list_blend.add_item(color=blend['new'])

    def show_blend(self, index):
        self.result_win = open_result_window(self.result_win, model=self.model, target=False)
        self.result_win.set_data(self.model.favorite[index])
        self.result_win.focus()


# importar exportar
class ViewExImport(View):
    file_types = [('JSON', '*.json'), ('Todos', '*.*')]

    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.form = ctk.CTkFrame(self)
        self.form.grid(padx=10, pady=10)
        self.form.grid_columnconfigure((0, 1), weight=1)

        rows = (
            ('Favoritos', self.model.get_json_favorite, self.model.set_json_favorite),
            ('Colores', self.model.get_json_colors, self.model.set_json_colors),
        )
        for row, (name, get_json, set_json) in enumerate(rows):
            self.add_button(f'Copiar {name}', row * 2, 0,
                            lambda g=get_json: self.copy_clipboard_json(g()))
            self.add_button(f'Pegar {name}', row * 2, 1,
                            lambda s=set_json, n=name: self.past_clipboard_json(s, n))
            self.add_button(f'Exportar {name.lower()} a archivo…', row * 2 + 1, 0,
                            lambda g=get_json, n=name: self.export_file(g, n))
            self.add_button(f'Importar {name.lower()} de archivo…', row * 2 + 1, 1,
                            lambda s=set_json, n=name: self.import_file(s, n))

    def add_button(self, text, row, column, cmd=None):
        bt = ctk.CTkButton(self.form, text=text, command=cmd)
        bt.grid(row=row, column=column, padx=10, pady=10, sticky="ew")

    def copy_clipboard_json(self, str_json):
        self.clipboard_clear()
        self.clipboard_append(str_json)
        self.update()  # now it stays on the clipboard after the window is closed

    def past_clipboard_json(self, set_json, name):
        try:
            str_json = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning('Pegar', 'El portapapeles está vacío o no contiene texto')
            return
        self._load(set_json, str_json, name)

    def export_file(self, get_json, name):
        path = filedialog.asksaveasfilename(
            title=f'Exportar {name.lower()}', defaultextension='.json',
            initialfile=f'{name.lower()}.json', filetypes=self.file_types)
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(get_json())
        except OSError as e:
            messagebox.showerror('Exportar', f'No se pudo guardar el archivo:\n{e}')

    def import_file(self, set_json, name):
        path = filedialog.askopenfilename(
            title=f'Importar {name.lower()}', filetypes=self.file_types)
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                str_json = f.read()
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror('Importar', f'No se pudo leer el archivo:\n{e}')
            return
        self._load(set_json, str_json, name)

    @staticmethod
    def _load(set_json, str_json, name):
        try:
            set_json(str_json)
        except ValueError as e:
            messagebox.showerror('Importar', f'No son {name.lower()} válidos:\n{e}')
