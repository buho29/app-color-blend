import logging
import queue
import sys
import tkinter as tk
from typing import Callable, Union

import customtkinter as ctk
import pyscreeze
from CTkToolTip import CTkToolTip
from pynput.mouse import Listener

from .color import color_distance, describe_delta_e

logger = logging.getLogger(__name__)

# colores de fondo (modo claro, modo oscuro)
BG_LIST = ('gray94', 'gray17')
BG_PANEL = ('gray92', 'gray14')
BG_TITLE = ('gray82', 'gray25')
BG_EMPTY = ('white', 'gray30')
FG_TEXT = ('black', 'white')


###################################
#            tools
###################################

def get_color_label(color):
    if color.get_bright() < 128:
        return "white"
    else:
        return "black"


def color_tooltip(color, d=None):
    text = f'{color.rgb}\n{color.get_hex()}'
    if d is not None:
        text += f'\nΔE {d:.2f}'
    return text


###################################
#        generic widgets
###################################

class CTkListbox(ctk.CTkScrollableFrame):

    def __init__(self, master, command=None, **kwargs):
        kwargs.setdefault('fg_color', BG_LIST)
        super().__init__(master, **kwargs)
        self.index = None
        self.grid_columnconfigure(0, weight=1)
        self.command = command
        self.widgets = list()

    def remove_item(self, index):
        if index < len(self.widgets):
            widget = self.widgets.pop(index)
            widget.destroy()
            if self.index is not None and self.index >= len(self.widgets):
                self.index = None
            # update widget row position
            for i in range(index, len(self.widgets)):
                self.widgets[i].grid(row=i)

    def remove_items(self):
        for widget in self.widgets:
            widget.destroy()

        self.widgets.clear()
        self.index = None

    def find_index(self, events):
        for index, widget in enumerate(self.widgets):
            if events.widget.master is widget:
                return index
        return None

    def onclick(self, events):
        index = self.find_index(events)
        if index is None:
            return

        self.set(index)

        if self.command is not None:
            self.command(index)

    def get(self):
        return self.index

    def set(self, index):
        if index < len(self.widgets):
            self.index = index

    def add_item(self, container):
        self.widgets.append(container)


class CTKWinBox(ctk.CTkToplevel):

    def __init__(self,
                 master: any = None,
                 width: int = 500,
                 height: int = 300,
                 title: str = "CTkMessagebox",
                 **kwargs):
        super().__init__(master, **kwargs)
        self.attributes("-topmost", True)
        self.configure(corner_radius=0)
        self.width = 200 if width < 200 else width
        self.height = 300 if height < 300 else height
        self.event = None
        self.oldx = self.oldy = 0

        self.title(title)
        self.resizable(width=False, height=False)

        self.overrideredirect(True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.x = self.winfo_x()
        self.y = self.winfo_y()
        self._title = title

        self.frame_top = ctk.CTkFrame(
            self, width=self.width,
            fg_color=BG_TITLE, corner_radius=0
        )
        self.frame_top.grid_rowconfigure((1, 2, 3), weight=1)
        self.frame_top.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.frame_top.grid(row=0, column=0, sticky="nswe")

        self.frame_top.bind("<B1-Motion>", self.move_window)
        self.frame_top.bind("<ButtonPress-1>", self.oldxyset)

        self.button_close = ctk.CTkButton(self.frame_top, corner_radius=10, width=0, height=0,
                                          hover=False, border_width=0,
                                          text_color=FG_TEXT,
                                          text="✕", fg_color="transparent", command=self.onclick)
        self.button_close.grid(row=0, column=5, sticky="ne", padx=5, pady=5)

        self.title_label = ctk.CTkLabel(self.frame_top, text=self._title, text_color=FG_TEXT)
        self.title_label.grid(row=0, column=0, columnspan=6, sticky="nw", padx=(15, 30), pady=5)
        self.title_label.bind("<B1-Motion>", self.move_window)
        self.title_label.bind("<ButtonPress-1>", self.oldxyset)

        self.container = ctk.CTkFrame(self.frame_top)
        self.container.grid(row=1, column=0, columnspan=6, sticky="nwes", padx=0)
        self.container.columnconfigure(0, weight=1)

        self.buttons = ctk.CTkFrame(self.frame_top, fg_color='transparent')
        self.buttons.grid(row=2, column=0, columnspan=6, )

        self.button_close = ctk.CTkButton(self.buttons, text='Cerrar', width=50, command=self.onclick)
        self.button_close.grid(row=0, column=0, padx=5, pady=5)

        self.bind("<Escape>", lambda e: self.onclick())

        self.lift()

    def get(self):
        if self.winfo_exists():
            self.master.wait_window(self)
        return self.event

    def oldxyset(self, event):
        self.oldx = event.x
        self.oldy = event.y

    def move_window(self, event):
        self.y = event.y_root - self.oldy
        self.x = event.x_root - self.oldx
        self.geometry(f'+{self.x}+{self.y}')

    def onclick(self, event=None):
        self.event = event
        self.destroy()


class CTkSpinbox(ctk.CTkFrame):
    def __init__(self, *args,
                 width: int = 100,
                 height: int = 32,
                 from_: int = 1, to: int = 99,
                 step_size: int = 1,
                 command: Callable = None,
                 **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)

        self._from = from_
        self._to = to

        self.step_size = step_size
        self.command = command

        self.configure(fg_color=("gray78", "gray28"))  # set frame color

        self.grid_columnconfigure((0, 2), weight=0)  # buttons don't expand
        self.grid_columnconfigure(1, weight=1)  # entry expands

        self.subtract_button = ctk.CTkButton(self, text="-", width=height - 6, height=height - 6,
                                             command=self.subtract_button_callback)
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)

        self.entry = ctk.CTkEntry(self, width=width - (2 * height), height=height - 6, border_width=0)
        self.entry.grid(row=0, column=1, columnspan=1, padx=3, pady=3, sticky="ew")

        self.add_button = ctk.CTkButton(self, text="+", width=height - 6, height=height - 6,
                                        command=self.add_button_callback)
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        # default value
        self.entry.insert(0, str(from_))

    def add_button_callback(self):
        self._step(self.step_size)

    def subtract_button_callback(self):
        self._step(-self.step_size)

    def _step(self, delta):
        value = self.get()
        if value is None:
            return
        self.set(value + delta)
        if self.command is not None:
            self.command()

    def get(self) -> Union[int, None]:
        """Valor actual limitado al rango, o None si no es un número."""
        try:
            value = int(self.entry.get())
        except ValueError:
            return None
        return min(max(value, self._from), self._to)

    def set(self, value: int):
        if self._from <= value <= self._to:
            self.entry.delete(0, "end")
            self.entry.insert(0, str(value))


class CTKEyeDropper(ctk.CTkToplevel):
    """Cuentagotas: sigue al ratón y devuelve el color del píxel donde se hace clic.

    pynput avisa desde su propio hilo; los eventos se pasan por una cola y se
    procesan en el hilo de Tk, que es el único que puede tocar la ventana.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.configure(corner_radius=0, cursor="none")
        self.attributes("-topmost", True)

        self.color = None
        self.dia = 60
        self.center = int(self.dia / 2)

        self.geometry(f"{self.dia}x{self.dia}")
        self.resizable(width=False, height=False)

        self.overrideredirect(True)

        self.transparent_color = 'grey99'
        self.attributes("-transparentcolor", self.transparent_color)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bg=self.transparent_color,
            width=self.dia,
            height=self.dia
        )
        self.canvas.grid(row=0, column=0, sticky="nswe")

        # draw
        self.out_shape = self.canvas.create_oval(
            0, 0,
            self.dia - 1, self.dia - 1,
            fill="white"
        )
        w = 20
        self.canvas.create_oval(
            w, w,
            self.dia - w, self.dia - w,
            fill=self.transparent_color
        )

        self.bind("<Escape>", lambda e: self.cancel())
        self.focus_force()

        self._events = queue.Queue()
        self.listener = Listener(on_move=self._on_move,
                                 on_click=self._on_click)
        self.listener.start()
        self.after(15, self._poll)

    def get(self):
        if self.winfo_exists():
            self.master.wait_window(self)
        return self.color

    # hilo de pynput
    def _on_move(self, x, y):
        self._events.put(('move', x, y))

    # hilo de pynput
    def _on_click(self, x, y, button, pressed):
        if pressed:
            self._events.put(('click', x, y))
            return False  # Stop listener

    @staticmethod
    def _pixel(x, y):
        try:
            return tuple(pyscreeze.pixel(x, y)[:3])
        except Exception:
            logger.debug('no se pudo leer el píxel %d,%d', x, y, exc_info=True)
            return None

    def _poll(self):
        if not self.winfo_exists():
            return

        move = None
        while True:
            try:
                kind, x, y = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == 'click':
                self.color = self._pixel(x, y) or self.color
                self._close()
                return
            move = (x, y)

        if move is not None:
            x, y = move
            color = self._pixel(x, y)
            if color is not None:
                self.color = color
                self.canvas.itemconfigure(self.out_shape, fill='#%02x%02x%02x' % color)
            self.geometry(f'+{x - self.center}+{y - self.center}')

        self.after(15, self._poll)

    def cancel(self):
        self.color = None
        self._close()

    def _close(self):
        self.listener.stop()
        self.destroy()


###################################
#         Widgets App
###################################

class GalleryColor(CTkListbox):

    def __init__(self, master, command=None, columns=2, **kwargs):
        super().__init__(master, command, **kwargs)

        self.col = columns

    def add_item(self, color=None):
        txt, fg_color, color_text = '', '#ffffff', 'black'

        if color is not None:
            color_text = get_color_label(color)
            fg_color = color.get_hex()
            txt = color.name

        button = ctk.CTkButton(self, text=txt, fg_color=fg_color,
                               border_width=0, border_color=('#3B8ED0', '#1F6AA5'),
                               text_color=color_text,
                               width=120, height=100, hover=False)
        button.bind("<Button-1>", self.onclick)

        if color is not None:
            CTkToolTip(button, message=color_tooltip(color))

        i = len(self.widgets)
        row = i // self.col
        col = i % self.col

        button.grid(row=row, column=col, pady=(0, 10), padx=5)

        super().add_item(button)

    def set(self, index):
        if index < len(self.widgets):
            if self.index is not None:
                self.widgets[self.index].configure(border_width=0)
            self.index = index
            item = self.widgets[index]
            item.configure(border_width=4)


class ListBlend(CTkListbox):

    def __init__(self, master, command=None, command_removed=None, edit=True, **kwargs):
        super().__init__(master, command, **kwargs)
        self.edit = edit
        self.command_removed = command_removed

    def add_item(self, blend=None, color=None):
        if blend is not None:
            color = blend['color']
            cant = blend['amount']
            txt = f'{color.name} + {cant}'
        else:
            txt = f'{color.get_hex()}'

        color_text = get_color_label(color)
        str_color = color.get_hex()

        row = len(self.widgets)

        container = ctk.CTkFrame(master=self, fg_color=str_color)
        container.bind("<Button-1>", self.onclick)
        container.grid_columnconfigure(0, weight=1)
        container.grid(row=row, column=0, pady=(0, 10), padx=5, sticky="nsew")

        label = ctk.CTkLabel(container, text=txt, text_color=color_text)
        label.bind("<Button-1>", self.onclick)
        label.grid(row=0, column=0)

        CTkToolTip(container, message=color_tooltip(color))

        if self.edit:
            button = ctk.CTkButton(container, text='Borrar', width=100)
            button.bind("<Button-1>", self.onclick)
            button.grid(row=0, column=1, pady=10, padx=10)

        super().add_item(container)

    def onclick(self, events):
        # el clic puede venir del contenedor, de la etiqueta o del botón borrar
        widget = events.widget
        for index, item in enumerate(self.widgets):
            if widget.master is item:
                if self.command is not None:
                    self.command(index)
                return
            if widget.master.master is item:
                if self.edit and isinstance(widget.master, ctk.CTkButton):
                    self.remove_item(index)
                    if self.command_removed is not None:
                        self.command_removed(index)
                elif self.command is not None:
                    self.command(index)
                return


class WinResult(CTKWinBox):
    def __init__(self,
                 width: int = 200,
                 height: int = 400,
                 title: str = "Resultado",
                 model=None,
                 target=True,
                 **kwargs):
        super().__init__(width=width, height=height, title=title, **kwargs)

        self.model = model
        self.blends = None
        self.target = None

        self.list_blend = ListBlend(master=self.container, edit=False)
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.result = ctk.CTkLabel(master=self.container, text='',
                                   height=50, fg_color=BG_EMPTY)
        self.result.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.result_ttip = CTkToolTip(self.result)
        if target:
            self.target = ctk.CTkLabel(master=self.container, text='',
                                       height=50, fg_color=BG_EMPTY)
            self.target.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
            self.target_ttip = CTkToolTip(self.target)

            self.distance = ctk.CTkLabel(master=self.container, text='')
            self.distance.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")

            save = ctk.CTkButton(self.buttons, text='Guardar fav.', command=self.onsave)
            save.grid(row=0, column=1, padx=5, pady=5)

    def set_data(self, blends, target_color=None):
        self.blends = blends
        self.list_blend.remove_items()

        for blend in blends['colors']:
            self.list_blend.add_item(blend)

        color = blends['new']

        self.result.configure(text=color.get_hex(),
                              text_color=get_color_label(color),
                              fg_color=color.get_hex())
        self.result_ttip.configure(message=color_tooltip(color))

        if self.target is not None and target_color is not None:
            self.target.configure(text=target_color.get_hex(),
                                  text_color=get_color_label(target_color),
                                  fg_color=target_color.get_hex())
            self.target_ttip.configure(message=color_tooltip(target_color))
            d = color_distance(color, target_color)
            self.distance.configure(text=f'ΔE {d:.2f}\n{describe_delta_e(d)}')

    def onsave(self, event=None):
        self.event = event
        self.model.add_favorite(self.blends['colors'])


def open_result_window(current, **kwargs):
    """Reutiliza la ventana de resultado en Windows; en el resto la recrea."""
    if current is not None and current.winfo_exists():
        if sys.platform.startswith("win"):
            return current
        current.destroy()
    return WinResult(**kwargs)
