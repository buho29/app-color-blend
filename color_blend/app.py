import logging
import sys

import customtkinter as ctk

from . import storage
from .mixing import MIX_PIGMENT, MIX_RGB
from .model import Model
from .palettes import VALLEJO_GAME_COLOR
from .views import ViewBlend, ViewExImport, ViewFavorite, ViewFind

logger = logging.getLogger(__name__)

MIX_LABELS = {MIX_PIGMENT: 'Pigmento', MIX_RGB: 'Luz (RGB)'}


class App(ctk.CTk):
    def __init__(self, data_path=None):
        super().__init__()

        self.data_path = data_path or storage.default_path()

        if sys.platform.startswith("win"):
            self.title("Color blend")
            self.geometry(f"{800}x{600}")
        else:  # android
            ctk.deactivate_automatic_dpi_awareness()
            ctk.set_widget_scaling(2.5)
            ctk.set_window_scaling(1.5)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.model = Model()
        self.load_state()
        self.model.add_event(self.on_model_event)

        # modo de mezcla (afecta a todas las pestañas)
        top_frame = ctk.CTkFrame(master=self, fg_color='transparent')
        top_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="e")
        ctk.CTkLabel(top_frame, text='Modo de mezcla').grid(row=0, column=0, padx=10)
        self.mix_mode = ctk.CTkSegmentedButton(
            top_frame, values=list(MIX_LABELS.values()), command=self.set_mix_mode)
        self.mix_mode.set(MIX_LABELS[self.model.mix_mode])
        self.mix_mode.grid(row=0, column=1)

        self.tabview = ctk.CTkTabview(master=self, )
        self.tabview.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")

        # create tabs
        self.create_tab("Buscar Color", ViewFind)
        self.create_tab("Mezclar Color", ViewBlend)
        self.create_tab("Favoritos", ViewFavorite)
        self.create_tab("Export/Import", ViewExImport)

        self.tabview.set("Mezclar Color")  # set currently visible tab

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_tab(self, title, view_class):
        tab = self.tabview.add(title)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        # add widgets on tab
        _frame = view_class(tab, self.model)
        _frame.grid(row=0, column=0, padx=10, pady=0, sticky="nsew")

    def set_mix_mode(self, label):
        mode = next(k for k, v in MIX_LABELS.items() if v == label)
        self.model.set_mix_mode(mode)

    #
    #         Guardado

    def load_state(self):
        try:
            text = storage.read(self.data_path)
        except OSError:
            logger.exception('no se pudo leer %s', self.data_path)
            text = None

        if text is not None:
            try:
                self.model.set_json_state(text)
                return
            except ValueError as e:
                # se guarda una copia para no perder los datos al sobrescribir
                logger.warning('datos dañados en %s (%s), se renombra a .bak', self.data_path, e)
                try:
                    storage.backup(self.data_path)
                except OSError:
                    logger.exception('no se pudo renombrar %s', self.data_path)

        self.model.set_data(VALLEJO_GAME_COLOR)

    def save_state(self):
        try:
            storage.write(self.data_path, self.model.get_json_state())
        except OSError:
            logger.exception('no se pudo guardar %s', self.data_path)

    # cualquier cambio en el modelo se guarda
    def on_model_event(self, event_name):
        self.save_state()

    def on_close(self):
        self.save_state()
        self.destroy()


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    app = App()
    app.mainloop()
